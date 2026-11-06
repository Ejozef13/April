"""Explicit Gmail OAuth and bounded read-only search. No send/delete APIs."""
import argparse
import asyncio
import base64
import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .config import load_config
from .errors import BackendError
from .knowledge import clean_text

SCOPES=['https://www.googleapis.com/auth/gmail.readonly']
API='https://gmail.googleapis.com/gmail/v1/users/me'


def google_endpoint(value,hosts,paths=None):
    try:
        url=urlparse(value)
        return (url.scheme=='https' and url.hostname in hosts and not url.username and not url.password
                and url.port in {None,443} and not url.query and not url.fragment
                and (paths is None or url.path in paths))
    except (ValueError,TypeError,AttributeError):return False


def save_credentials(path,credentials):
    if set(credentials.scopes or []) != set(SCOPES) or (credentials.granted_scopes is not None and set(credentials.granted_scopes)!=set(SCOPES)):
        raise BackendError('gmail_scope_invalid','Only the dedicated Gmail read-only grant is accepted. Use a dedicated Desktop OAuth client.')
    path=Path(path).expanduser()
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if path.is_symlink():
        raise BackendError('gmail_token_invalid','Refusing to write a symlinked Gmail token file.')
    fd,name=tempfile.mkstemp(prefix='.april-gmail-',dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as file:file.write(credentials.to_json())
        os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def credentials_for(config):
    path=Path(config.gmail_token_path).expanduser()
    if not path.is_file() or path.is_symlink():
        raise BackendError('gmail_not_connected','Gmail is not connected. Use the local OAuth setup in docs/INTEGRATIONS.md; never paste tokens into chat.')
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google.auth.exceptions import RefreshError,TransportError
    except ImportError as exc:
        raise BackendError('gmail_library_missing','Install the optional Gmail dependencies with pip install -e ".[gmail]" in APRIL’s virtual environment.') from exc
    try:
        original=path.read_text()
        info=json.loads(original)
        if not google_endpoint(info.get('token_uri',''),{'oauth2.googleapis.com','accounts.google.com'},{'/token','/o/oauth2/token'}):
            raise BackendError('gmail_token_invalid','The saved token metadata is invalid. Reconnect using your local Google Desktop client.')
        if set(info.get('scopes',[])) != set(SCOPES):
            raise BackendError('gmail_scope_invalid','The saved grant is not the dedicated Gmail read-only scope. Reconnect with the APRIL Desktop client; do not add broader permissions.')
        credentials=Credentials.from_authorized_user_info(info,SCOPES)
        if not credentials.has_scopes(SCOPES):
            raise ValueError('Missing read scope')
        # Do not adopt a token created for sending/modifying mail.
        if set(credentials.scopes or []) != set(SCOPES):
            raise ValueError('Unexpected scopes')
        if not credentials.valid:
            if not credentials.refresh_token:raise ValueError('Missing refresh token')
            request=Request()
            def bounded_request(*args,**kwargs):
                kwargs['timeout']=10
                return request(*args,**kwargs)
            credentials.refresh(bounded_request)
            if not path.is_file() or path.read_text()!=original:
                raise ValueError('Local grant was changed or disconnected during refresh')
            save_credentials(path,credentials)
        return credentials
    except BackendError:
        raise
    except TransportError as exc:
        raise BackendError('gmail_network_failed','Google token refresh could not reach the authentication service. Check your network, VPN, proxy and TLS configuration; consent may already be valid.') from exc
    except RefreshError as exc:
        raise BackendError('gmail_refresh_failed','Google rejected the token refresh. Reconnect using the existing Desktop client and your approved test account.') from exc
    except Exception as exc:
        raise BackendError('gmail_auth_failed','Gmail authentication failed. Reconnect locally; do not share credentials or raw authentication errors.') from exc


def message_excerpt(payload,depth=0):
    if depth>4 or payload.get('filename'):return ''
    mime=payload.get('mimeType','')
    body=payload.get('body',{}).get('data','')
    if mime in {'text/plain','text/html'} and isinstance(body,str) and len(body)<=80000:
        try:
            text=base64.urlsafe_b64decode(body+'='*((-len(body))%4)).decode('utf-8',errors='replace')
            return clean_text(text,1800)
        except (ValueError,TypeError):return ''
    for part in payload.get('parts',[])[:20]:
        text=message_excerpt(part,depth+1)
        if text:return text
    return ''


def require_gmail_success(response):
    """Map allowlisted Google error reasons to static messages; never echo bodies."""
    if response.is_success:return
    reasons=set()
    try:
        if len(response.content)<=32_000:
            error=response.json().get('error',{})
            for item in error.get('errors',[])[:10]+error.get('details',[])[:10]:
                if isinstance(item,dict) and isinstance(item.get('reason'),str):reasons.add(item['reason'])
    except (ValueError,TypeError,AttributeError):pass
    if reasons & {'accessNotConfigured','SERVICE_DISABLED','API_DISABLED'}:
        raise BackendError('gmail_api_disabled','Gmail API is disabled or not yet available in the OAuth client project. Enable Gmail API in that same Google Cloud project, allow time for propagation, then retry. Your consent does not need to be repeated for this error.')
    if reasons & {'insufficientPermissions','ACCESS_TOKEN_SCOPE_INSUFFICIENT','insufficient_scope'}:
        raise BackendError('gmail_scope_rejected','Google rejected the granted scopes. Confirm gmail.readonly for this Desktop client and reconnect; broader permissions are not needed.')
    if response.status_code==401:
        raise BackendError('gmail_token_rejected','Google rejected the access token. Reconnect with your existing Desktop client and approved test account.')
    if response.status_code==429 or reasons & {'rateLimitExceeded','userRateLimitExceeded','quotaExceeded','RATE_LIMIT_EXCEEDED'}:
        raise BackendError('gmail_rate_limited','Google temporarily limited Gmail requests. Wait and retry; do not repeat consent.')
    if response.status_code>=500:
        raise BackendError('gmail_service_unavailable','Google Gmail is temporarily unavailable. Retry later; no consent change is indicated.')
    if response.status_code==403:
        raise BackendError('gmail_access_denied','Google denied Gmail API access (HTTP 403). Check Gmail API enablement in the client project and Google account or Workspace policies. This check cannot determine which policy denied access.')
    raise BackendError('gmail_request_rejected','Google rejected the Gmail API request (HTTP '+str(response.status_code)+'). Verify Gmail API enablement and the Desktop client configuration.')


async def search_gmail(config,query,*,credentials=None,transport=None):
    if credentials is None:
        credentials=await asyncio.to_thread(credentials_for,config)
    try:
        async with httpx.AsyncClient(timeout=12,transport=transport) as client:
            headers={'Authorization':'Bearer '+credentials.token}
            listing=await client.get(API+'/messages',params={'q':query[:500],'maxResults':3},headers=headers)
            require_gmail_success(listing)
            sources=[]
            for item in listing.json().get('messages',[])[:3]:
                message_id=item.get('id','')
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',message_id):continue
                response=await client.get(API+'/messages/'+message_id,params={'format':'full'},headers=headers)
                require_gmail_success(response)
                message=response.json();payload=message.get('payload',{})
                fields={h.get('name','').casefold():h.get('value','') for h in payload.get('headers',[])[:80]}
                title=clean_text(fields.get('subject','(No subject)'),180)
                text=message_excerpt(payload) or clean_text(message.get('snippet',''),1800)
                source={'title':title,'excerpt':clean_text('From: '+fields.get('from','')+'\nDate: '+fields.get('date','')+'\n'+text,2200),
                        'url':None,'kind':'gmail'}
                sources.append(source)
    except httpx.TimeoutException as exc:
        raise BackendError('gmail_network_timeout','Gmail search timed out. Check your network or VPN and retry; consent may already be valid.') from exc
    except httpx.RequestError as exc:
        raise BackendError('gmail_network_failed','Could not reach Gmail. Check network, VPN, proxy and TLS settings; consent may already be valid.') from exc
    except (httpx.HTTPError,ValueError,TypeError,AttributeError) as exc:
        raise BackendError('gmail_search_failed','Gmail search failed. Check local OAuth access, Gmail API settings and network; no email was sent or modified.') from exc
    return sources


async def check_gmail(config, *, credentials=None, transport=None):
    """Verify a read-only grant using profile metadata; do not fetch message bodies."""
    if credentials is None:credentials=await asyncio.to_thread(credentials_for,config)
    try:
        async with httpx.AsyncClient(timeout=12,transport=transport) as client:
            response=await client.get(API+'/profile',headers={'Authorization':'Bearer '+credentials.token})
            require_gmail_success(response)
            if not isinstance(response.json().get('emailAddress'),str):raise ValueError('Invalid profile')
        return True
    except httpx.TimeoutException as exc:
        raise BackendError('gmail_network_timeout','Gmail connection check timed out. Check your network or VPN and retry; consent may already be valid.') from exc
    except httpx.RequestError as exc:
        raise BackendError('gmail_network_failed','Could not reach Gmail. Check network, VPN, proxy and TLS settings; consent may already be valid.') from exc
    except (httpx.HTTPError,ValueError,TypeError,AttributeError) as exc:
        raise BackendError('gmail_check_failed','Google returned an unexpected Gmail response. Check API availability; no message bodies were read by this check.') from exc


def main():
    parser=argparse.ArgumentParser(description='Connect Gmail using local read-only OAuth; never upload client files or tokens to Git.')
    parser.add_argument('action',choices=['connect','disconnect','check'])
    parser.add_argument('--client',type=Path,help='Google Desktop OAuth client JSON stored outside the repository')
    args=parser.parse_args()
    config=load_config()
    path=Path(config.gmail_token_path).expanduser()
    if args.action=='check':
        try:asyncio.run(check_gmail(config))
        except BackendError as exc:parser.exit(1,'Gmail check failed ['+exc.code+']: '+str(exc)+'\n')
        print('Authenticated Gmail connection verified. No message bodies were read by this check.')
        return
    if args.action=='disconnect':
        if path.is_symlink():parser.exit(1,'Refusing to remove a symlinked token file.\n')
        path.unlink(missing_ok=True)
        print('Local token removed. Revoke APRIL access in your Google account to invalidate the grant too.')
        return
    if not args.client or not args.client.is_file():parser.error('--client must point to your local Google Desktop OAuth client JSON')
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        info=json.loads(args.client.read_text())
        installed=info.get('installed',{})
        if not installed or not google_endpoint(installed.get('auth_uri',''),{'accounts.google.com'},{'/o/oauth2/auth','/o/oauth2/v2/auth'}) or not google_endpoint(installed.get('token_uri',''),{'oauth2.googleapis.com','accounts.google.com'},{'/token','/o/oauth2/token'}):
            raise ValueError('A Google Desktop OAuth client with official HTTPS endpoints is required')
        flow=InstalledAppFlow.from_client_config(info,SCOPES,autogenerate_code_verifier=True)
        credentials=flow.run_local_server(host='127.0.0.1',port=0,open_browser=True,
            access_type='offline',prompt='consent',timeout_seconds=180,
            authorization_prompt_message='Authorize APRIL in the browser. If it did not open, run this command in your desktop session.',
            success_message='APRIL read-only Gmail authorization received. You may close this tab.')
        save_credentials(path,credentials)
    except ImportError:parser.exit(1,'Install optional Gmail dependencies in APRIL’s virtual environment first.\n')
    except Exception:parser.exit(1,'OAuth connection failed or timed out. Check Desktop client settings and your test-user access; do not share tokens or raw errors.\n')
    print('Gmail connected with read-only scope. No message content was downloaded during setup.')


if __name__=='__main__':main()
