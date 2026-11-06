"""Real authenticated loopback Radicale; temporary public events only."""
import asyncio
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from zoneinfo import ZoneInfo

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from passlib.hash import sha512_crypt
from april.calendar import request, proposal, commit, events
from april.config import Config
from april.calendar_setup import ensure_collection,bootstrap
from april.errors import BackendError


async def main():
    with tempfile.TemporaryDirectory(prefix='april-caldav-fixture-') as directory:
        root=Path(directory)
        with socket.socket() as socket_probe:
            socket_probe.bind(('127.0.0.1',0));port=socket_probe.getsockname()[1]
        password=root/'users'
        password.write_text('april:'+sha512_crypt.hash('public-fixture-password')+'\n')
        config_file=root/'radicale.ini'
        config_file.write_text(f'''[server]
hosts = 127.0.0.1:{port}
[auth]
type = htpasswd
htpasswd_filename = {password}
htpasswd_encryption = sha512
[rights]
type = owner_only
[storage]
filesystem_folder = {root/'data'}
[logging]
level = warning
''')
        creds=root/'credentials.json'
        creds.write_text(json.dumps({'username':'april','password':'public-fixture-password'}));creds.chmod(0o600)
        config=Config(caldav_url=f'http://127.0.0.1:{port}/april/assistant/',caldav_credentials=str(creds),caldav_server_config=str(config_file))
        with (root/'log').open('w') as log:
            server=subprocess.Popen([sys.executable,'-m','radicale','--config',str(config_file)],stdout=log,stderr=subprocess.STDOUT)
            try:
                for _ in range(60):
                    if server.poll() is not None:raise AssertionError((root/'log').read_text()[-1500:])
                    try:
                        if httpx.get(f'http://127.0.0.1:{port}/april/assistant/',timeout=2,trust_env=False).status_code==401:break
                    except httpx.HTTPError:pass
                    await asyncio.sleep(.1)
                else:raise AssertionError('Authenticated fixture server did not start')
                assert await ensure_collection(config) is True
                assert await ensure_collection(config) is False
                start=datetime.now(ZoneInfo("America/New_York"))+timedelta(hours=1)
                item=proposal({'title':'Public test event','start':start.isoformat(),'end':(start+timedelta(hours=1)).isoformat()})
                etag=await commit(config,item)
                listed=await events(config)
                assert listed[0]['title']=='Public test event',listed
                assert listed[0]['uid']==item['uid']
                change=proposal({'title':'Updated public event','start':item['start'],'end':item['end'],'uid':item['uid'],'etag':etag})
                await commit(config,change)
                assert (await events(config))[0]['title']=='Updated public event'
                try:await commit(config,change)
                except BackendError as exc:assert exc.code=='calendar_conflict'
                else:raise AssertionError('Stale update was accepted')
                count,temporary=await bootstrap(config)
                assert count==1 and not temporary
                assert server.poll() is None,'Existing server was not preserved'
                print('Real Radicale: unauthenticated denial, authenticated create/read/update and stale-ETag rejection passed.')
            finally:
                server.terminate()
                try:server.wait(timeout=5)
                except subprocess.TimeoutExpired:server.kill();server.wait()
        count,temporary=await bootstrap(config)
        assert count==1 and temporary
        with socket.socket() as check:
            assert check.connect_ex(('127.0.0.1',port))!=0,'Temporary setup server remained running'
        print('Real CalDAV setup: idempotent discovery, existing-server preservation, temporary startup/read/shutdown passed.')


if __name__=='__main__':asyncio.run(main())
