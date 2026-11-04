"""Bounded read-only retrieval; sources are data, never executable instructions."""
import os
import re
import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .errors import BackendError
from .tools import normalize_request


def route_knowledge(text):
    normalized=normalize_request(text)
    for action,pattern in [
        ('web',r'(?:search (?:the )?web|look (?:it )?up online)(?: for)?\s+(.+)'),
        ('documents',r'(?:search|find in) my (?:files|documents)(?: for)?\s+(.+)'),
        ('gmail',r'(?:search|find in) my (?:gmail|emails?|mail)(?: for)?\s+(.+)')]:
        match=re.fullmatch(pattern,normalized)
        if match:return action,match[1]
    # Specific current-fact intents must not quietly fall back to stale weights.
    if not re.search(r'\bmy (?:emails?|mail|files|documents)\b',normalized) and re.search(r'\bcurrent president\b|\bwho is (?:the )?president\b|\blatest news\b',normalized):
        return 'web',text
    return None,text


def clean_text(value,limit=1500):
    return re.sub(r'<[^>]*>',' ',str(value)).strip()[:limit]


async def search_web(config,query,*,transport=None):
    token=os.environ.get(config.web_api_key_env)
    if not token:
        try:
            path=Path(config.web_key_path).expanduser()
            if path.is_file() and not path.is_symlink() and path.stat().st_size<=4096:
                if path.stat().st_mode & 0o077:
                    raise BackendError('web_key_permissions','The local search key file must be private (mode 600). Use python -m april.integrations web-key.')
                token=path.read_text().strip()
        except OSError as exc:
            raise BackendError('web_key_unreadable','The local search key file could not be read. Check its private permissions; do not paste it into chat.') from exc
    if not token:
        raise BackendError('web_not_configured','This needs a current source, but web search is not configured. Set up Brave Search using python -m april.integrations web-key; I have not verified this answer online.')
    try:
        async with httpx.AsyncClient(timeout=12,transport=transport) as client:
            response=await client.get('https://api.search.brave.com/res/v1/web/search',
                params={'q':query[:500],'count':3},headers={'X-Subscription-Token':token,'Accept':'application/json'})
            response.raise_for_status()
            results=response.json().get('web',{}).get('results',[])[:3]
    except (httpx.HTTPError,ValueError,TypeError,AttributeError) as exc:
        raise BackendError('web_unavailable','Web search failed. Check the provider key, account/quota and network. No current answer has been verified.') from exc
    sources=[]
    for item in results:
        if not isinstance(item,dict):continue
        url=item.get('url','')
        if not isinstance(url,str):continue
        try:parsed=urlparse(url)
        except ValueError:continue
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username:continue
        sources.append({'title':clean_text(item.get('title','Web result'),180),
            'excerpt':clean_text(item.get('description','')),'url':url[:2000],'kind':'web',
            'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'provider_date':clean_text(item.get('page_age',item.get('age','')),80) or None})
    return sources


async def retrieve(config,action,query):
    if not isinstance(query,str) or not query.strip() or len(query)>2000:
        raise BackendError('search_query_invalid','Enter a search query of 1–2000 characters.')
    if action=='web':return await search_web(config,query)
    if action=='documents':
        import asyncio
        from .documents import search_documents
        return await asyncio.to_thread(search_documents,config,query)
    if action=='gmail':
        from .gmail import search_gmail
        return await search_gmail(config,query)
    raise BackendError('search_action_invalid','Unknown read-only search action.')
