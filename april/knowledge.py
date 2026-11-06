"""Bounded read-only retrieval; sources are data, never executable instructions."""
import re
import datetime
from urllib.parse import urlparse
from html import unescape

import httpx

from .errors import BackendError
from .tools import normalize_request


def private_request(text):
    """Conservative routing cues, not a general-purpose personal-data detector."""
    normalized=normalize_request(text)
    return bool(re.search(
        r'\b(?:my|our)\s+(?:e-?mails?|gmail|inbox|mailbox|mail|files?|folders?|documents?|aprilfiles|'
        r'account|password|secret|token|private key|api key|desktop|computer|server|address|phone|calendar|contacts|name)\b'
        r'|\b(?:my|our)\s+(?:[\w-]+\s+){0,4}(?:projects?|notes|memories|preferences|tasks|plans)\b'
        r'|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|(?:/home/|~/|[A-Z]:\\)|-----BEGIN .*PRIVATE KEY-----',
        normalized,re.I))


def route_knowledge(text,automatic_web_search=False):
    normalized=normalize_request(text)
    for action,pattern in [
        ('web',r'(?:search (?:the )?(?:web|internet)|check (?:on )?(?:the )?(?:internet|web)|look (?:it )?up online)(?: for)?[\s,:.!?]+(.+)'),
        ('documents',r'(?:search|find in) my (?:files|documents)(?: for)?\s+(.+)'),
        ('gmail',r'(?:search|find in) my (?:gmail|emails?|mail)(?: for)?\s+(.+)')]:
        match=re.fullmatch(pattern,normalized)
        if match:return action,match[1]
    # Specific current-fact intents must not quietly fall back to stale weights.
    if private_request(text):return None,text
    if automatic_web_search or re.search(r'\bcurrent president\b|\bwho is (?:the )?president\b|\blatest news\b',normalized):
        return 'web',normalized
    return None,text


def clean_text(value,limit=1500):
    return unescape(re.sub(r'<[^>]*>',' ',str(value))).strip()[:limit]


def normalize_sources(results,provider):
    sources=[]
    if not isinstance(results,list):
        raise BackendError('web_invalid_response','The search provider returned an invalid result list; no current answer was verified.')
    for item in results:
        if not isinstance(item,dict):continue
        url=item.get('url','')
        if not isinstance(url,str):continue
        try:parsed=urlparse(url)
        except ValueError:continue
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username:continue
        sources.append({'title':clean_text(item.get('title','Web result'),180),
            'excerpt':clean_text(item.get('content','') or ''),
            'url':url[:2000],'kind':'web','provider':provider,
            'retrieved_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'provider_date':clean_text(item.get('publishedDate',item.get('page_age',item.get('age',''))) or '',80) or None})
        if len(sources)>=3:break
    return sources


async def search_searxng(config,query,*,transport=None):
    try:
        # Local only; never forward external proxy credentials.
        async with httpx.AsyncClient(trust_env=False,timeout=12,transport=transport) as client:
            response=await client.post(config.searxng_url.rstrip('/')+'/search',
                data={'q':query[:500],'format':'json','language':'en','safesearch':'1'},
                headers={'Accept':'application/json'})
            if response.status_code==403:
                raise BackendError('searxng_json_disabled','Your SearXNG instance refused JSON search. Enable search.formats: [html, json] in its private settings and restart only APRIL Search.')
            response.raise_for_status()
            data=response.json()
    except httpx.ConnectError as exc:
        raise BackendError('searxng_unavailable','Local SearXNG is not reachable. Run bash scripts/searxng.sh up and check searxng_url in april.local.toml. No current answer was verified.') from exc
    except (httpx.HTTPError,ValueError,TypeError,AttributeError) as exc:
        raise BackendError('searxng_request_failed','SearXNG search failed or returned non-JSON output. Check its local service, JSON API and upstream engine availability; no current answer was verified.') from exc
    if not isinstance(data,dict):
        raise BackendError('searxng_invalid_response','SearXNG returned an invalid JSON response.')
    sources=normalize_sources(data.get('results',[]),'searxng')
    if not sources and data.get('unresponsive_engines'):
        raise BackendError('searxng_engines_unavailable','SearXNG is running, but its upstream engines returned no usable results and reported failures. Check network/rate limits; do not bypass CAPTCHAs or engine restrictions.')
    return sources


async def search_web(config,query,*,transport=None):
    return await search_searxng(config,query,transport=transport)


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
