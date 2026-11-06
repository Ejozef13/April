"""Create only APRIL's private loopback Radicale configuration and calendar."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from .config import load_config


def initialize(config):
    from passlib.hash import sha512_crypt
    credentials=Path(config.caldav_credentials).expanduser()
    server=Path(config.caldav_server_config).expanduser()
    password_file=server.parent/'calendar-users'
    if any(p.exists() or p.is_symlink() for p in (credentials,server,password_file)):
        raise ValueError('Calendar setup files already exist; nothing was replaced')
    if config.caldav_url!='http://127.0.0.1:5232/april/assistant/':
        raise ValueError('Initial local setup uses the default loopback collection URL')
    server.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    credentials.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    password=secrets.token_urlsafe(32)
    storage=Path('~/.local/share/april/calendar').expanduser()
    storage.mkdir(parents=True,exist_ok=True,mode=0o700)
    files={credentials:json.dumps({'username':'april','password':password}),
           password_file:'april:'+sha512_crypt.hash(password)+'\n',
           server:f'''[server]
hosts = 127.0.0.1:5232
[auth]
type = htpasswd
htpasswd_filename = {password_file}
htpasswd_encryption = sha512
[rights]
type = owner_only
[storage]
filesystem_folder = {storage}
[logging]
level = warning
'''}
    for path,text in files.items():
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as file:file.write(text)


async def ensure_collection(config, *, transport=None):
    """Create only a missing dedicated collection; never replace existing calendars."""
    import httpx
    from .calendar import credentials,request
    from defusedxml import ElementTree
    body=b'<d:propfind xmlns:d="DAV:"><d:prop><d:resourcetype/></d:prop></d:propfind>'
    async with httpx.AsyncClient(auth=credentials(config),trust_env=False,timeout=2,
                                 transport=transport,follow_redirects=False) as client:
        response=await client.request('PROPFIND',config.caldav_url,content=body,
                                      headers={'Depth':'0','Content-Type':'application/xml'})
    if response.status_code==404:
        await request(config,'MKCALENDAR',content=b'<c:mkcalendar xmlns:c="urn:ietf:params:xml:ns:caldav"/>',
                      headers={'Content-Type':'application/xml'},transport=transport)
        return True
    response.raise_for_status()
    if len(response.content)>64_000:raise ValueError('Oversized calendar discovery response')
    root=ElementTree.fromstring(response.content)
    if root.find('.//{urn:ietf:params:xml:ns:caldav}calendar') is None:
        raise ValueError('The configured URL is not a calendar collection; nothing was replaced')
    return False


async def bootstrap(config):
    """Initialize, temporarily serve, create/verify collection, then release our server."""
    files=[Path(config.caldav_credentials).expanduser(),Path(config.caldav_server_config).expanduser()]
    if not any(path.exists() for path in files):initialize(config)
    elif not all(path.is_file() and not path.is_symlink() for path in files):
        raise ValueError('Incomplete calendar configuration; existing files were preserved')
    from .calendar import events
    # Do not stop an existing server. If ours is already reachable, verify it in place.
    try:
        await ensure_collection(config)
        return len(await events(config)),False
    except Exception:pass
    process=subprocess.Popen([sys.executable,'-m','radicale','--config',str(files[1])],
                             stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        async with asyncio.timeout(20):
            while process.poll() is None:
                try:
                    await ensure_collection(config)
                    return len(await events(config)),True
                except Exception:
                    await asyncio.sleep(.2)
            raise ValueError('Calendar server exited. Check the configured port and optional dependencies.')
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['init','serve','create','setup','check'])
    args=parser.parse_args();config=load_config()
    if args.action=='setup':
        try:
            count,temporary=asyncio.run(bootstrap(config))
        except Exception:
            parser.exit(1,'Calendar setup did not complete. Check optional dependencies, existing private files and port 5232. No successful connection is claimed.\n')
        print('Private CalDAV collection verified; '+str(count)+' events returned for the next seven days.')
        print('Temporary setup server stopped; managed April will start it.' if temporary else
              'Existing server preserved. Stop a manual calendar server before managed April takes ownership.')
    elif args.action=='check':
        from .calendar import events
        try:count=len(asyncio.run(events(config)))
        except Exception:parser.exit(1,'Calendar check failed. Start managed April and verify private settings.\n')
        print('Authenticated CalDAV read passed; '+str(count)+' events in the bounded seven-day query.')
    elif args.action=='init':
        try:initialize(config)
        except (ValueError,OSError) as exc:parser.exit(1,str(exc)+'\n')
        print('Private local calendar settings created. No remote account was connected.')
    elif args.action=='serve':
        raise SystemExit(subprocess.call([sys.executable,'-m','radicale','--config',str(Path(config.caldav_server_config).expanduser())]))
    else:
        try:created=asyncio.run(ensure_collection(config))
        except Exception:parser.exit(1,'Calendar collection setup failed; inspect local configuration.\n')
        print('APRIL calendar collection created.' if created else 'APRIL calendar collection already exists; preserved.')



if __name__=='__main__':main()
