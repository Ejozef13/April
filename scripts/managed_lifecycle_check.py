"""Real owned-process start/stop/off-until-manual-start; fixture services, not hardware."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

REPO=Path(__file__).resolve().parents[1]

def port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));return listener.getsockname()[1]

def wait_ready(root,process):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if process.poll() is not None:raise AssertionError('Fixture supervisor exited before readiness')
        try:
            if json.loads((root/'artifacts/power.json').read_text()).get('phase')=='ready':return
        except (OSError,ValueError):pass
        time.sleep(.1)
    raise AssertionError('Fixture readiness timed out')

def main():
    with tempfile.TemporaryDirectory(prefix='april-managed-fixture-') as directory:
        root=Path(directory);app_port,model_port=port(),port()
        config=root/'local.toml'
        config.write_text(f'model="fixture-model"\nport={app_port}\nprivate_ollama_port={model_port}\ncaldav_server_config='+json.dumps(str(root/'absent.ini'))+'\n')
        child=root/'fixture_service.py'
        child.write_text('''import json,sys
from http.server import BaseHTTPRequestHandler,HTTPServer
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  self.send_response(200);self.end_headers()
  self.wfile.write(json.dumps({'models':[{'name':'fixture-model'}]} if sys.argv[2]=='model' else {'mode':'live'}).encode())
 def log_message(self,*args):pass
HTTPServer(('127.0.0.1',int(sys.argv[1])),Handler).serve_forever()
''')
        supervisor=root/'fixture_supervisor.py'
        supervisor.write_text('''import subprocess,sys
from april import power
real=subprocess.Popen
fixture_args=sys.argv[:]
def spawn(args,**kwargs):
 if args[:2]==['ollama','serve']:command=[sys.executable,fixture_args[1],fixture_args[2],'model']
 elif args[:2]==['bash','scripts/searxng.sh']:command=[sys.executable,'-c','pass']
 elif args[:3]==[sys.executable,'-m','april.launch']:command=[sys.executable,fixture_args[1],fixture_args[3],'widget']
 else:raise AssertionError('Unexpected process')
 return real(command,**kwargs)
power.subprocess.Popen=spawn
power.subprocess.run=lambda args,**kwargs:subprocess.CompletedProcess(args,0)
sys.argv=['april.power','start','--foreground']
power.main()
''')
        env={**os.environ,'APRIL_CONFIG':str(config),'PYTHONPATH':str(REPO)}
        sentinel=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
        running=None
        try:
            for attempt in range(2):
                with (root/'fixture.log').open('a') as log:
                    running=subprocess.Popen([sys.executable,str(supervisor),str(child),str(model_port),str(app_port),'april.power'],
                                             cwd=root,env=env,stdout=log,stderr=log)
                wait_ready(root,running)
                result=subprocess.run([sys.executable,'-m','april.power','stop','--wait'],cwd=root,env=env,
                                      capture_output=True,text=True,timeout=20)
                assert result.returncode==0,result.stderr
                running.wait(timeout=5)
                assert (root/'artifacts/power.disabled').exists()
                assert not (root/'artifacts/power.json').exists()
                assert sentinel.poll() is None,'Unrelated process was stopped'
                for value in (app_port,model_port):
                    with socket.socket() as connection:
                        assert connection.connect_ex(('127.0.0.1',value))!=0,'Owned service port remained open'
                login=subprocess.run([sys.executable,'-m','april.power','start','--login'],cwd=root,env=env,
                                     capture_output=True,text=True,timeout=5)
                assert 'remains off' in login.stdout,login.stdout
            print('Managed fixture: readiness, owned-service shutdown, unrelated process preservation, login-off persistence and manual restart passed.')
        finally:
            if running and running.poll() is None:
                running.terminate()
                try:running.wait(timeout=15)
                except subprocess.TimeoutExpired:running.kill();running.wait()
            sentinel.terminate();sentinel.wait()

if __name__=='__main__':main()
