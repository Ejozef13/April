"""April-owned service supervisor. Never stop shared AM/Ollama/Docker services."""
import argparse
import fcntl
from dataclasses import asdict
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import tomllib

import httpx

from .config import load_config, Config

STATE = Path('artifacts/power.json')
DISABLED = Path('artifacts/power.disabled')


def process_identity(pid):
    try:
        cmd = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0')
        stat = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()
        return b'april.power' in cmd and stat[19]
    except (OSError, ValueError, IndexError):
        return False


def owner():
    try:
        data=json.loads(STATE.read_text())
        pid=data['pid']
        if isinstance(pid,int) and pid>1 and process_identity(pid)==data['started']:
            return pid
    except (OSError,ValueError,KeyError,TypeError):
        pass
    return None


def stop():
    DISABLED.parent.mkdir(exist_ok=True)
    DISABLED.touch(mode=0o600)
    pid=owner()
    if pid:
        try:os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:pass
    return bool(pid)


def runtime_config():
    config=load_config()
    data=asdict(config)
    data['ollama_url']=f'http://127.0.0.1:{config.private_ollama_port}'
    Config(**data)
    path=Path('artifacts/power.local.toml')
    path.parent.mkdir(exist_ok=True)
    path.write_text('\n'.join(key+' = '+json.dumps(value) for key,value in data.items())+'\n')
    path.chmod(0o600)
    return config,path


def supervise():
    if owner():
        raise SystemExit('April is already running.')
    STATE.parent.mkdir(exist_ok=True)
    lock=Path('artifacts/power.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('April is starting or already running.')
    config,runtime=runtime_config()
    port=config.private_ollama_port
    family=socket.AF_INET6 if ':' in config.host else socket.AF_INET
    with socket.socket(family) as app_probe:
        app_probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:app_probe.bind((config.host,config.port))
        except OSError:raise SystemExit('An APRIL app is already using the port. Stop it before managed startup; no services were changed.')
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try:probe.bind(('127.0.0.1',port))
        except OSError:raise SystemExit('Private Ollama port is occupied; no existing process was stopped.')
    if DISABLED.exists():return
    STATE.write_text(json.dumps({'pid':os.getpid(),'started':process_identity(os.getpid())}))
    STATE.chmod(0o600)
    interrupted=False
    def shutdown(signum,frame):
        nonlocal interrupted
        interrupted=True
    previous={s:signal.signal(s,shutdown) for s in (signal.SIGTERM,signal.SIGINT)}
    ollama=widget=calendar=search_job=None
    search_started=False
    try:
        environment=dict(os.environ)
        environment['OLLAMA_HOST']=f'127.0.0.1:{port}'
        environment['OLLAMA_NUM_PARALLEL']='1'
        environment['OLLAMA_MAX_QUEUE']='1'
        environment['OLLAMA_MAX_LOADED_MODELS']='1'
        environment['OLLAMA_KEEP_ALIVE']='0'
        if config.private_ollama_models:
            store=Path(config.private_ollama_models).expanduser()
            if not store.is_dir():
                raise ValueError('Configured private_ollama_models directory is unavailable')
            environment['OLLAMA_MODELS']=str(store)
        ollama=subprocess.Popen(['ollama','serve'],env=environment,start_new_session=True)
        with httpx.Client(trust_env=False,timeout=1) as client:
            for _ in range(60):
                if interrupted:return
                if ollama.poll() is not None:raise ValueError('Private Ollama exited')
                try:
                    response=client.get(f'http://127.0.0.1:{port}/api/tags')
                    response.raise_for_status()
                    names={m.get('name') for m in response.json().get('models',[])}
                    if config.model not in names:
                        raise ValueError('Model is not visible to private Ollama. Set private_ollama_models to your existing readable model store; no duplicate was downloaded.')
                    break
                except httpx.HTTPError:
                    time.sleep(.25)
            else:raise ValueError('Private Ollama startup timed out')
        if interrupted:return
        search_started=True
        search_job=subprocess.Popen(['bash','scripts/searxng.sh','up'],start_new_session=True)
        deadline=time.monotonic()+65
        while search_job.poll() is None:
            if interrupted:return
            if time.monotonic()>deadline:raise ValueError('Search startup timed out')
            time.sleep(.1)
        if search_job.returncode:raise ValueError('APRIL Search startup failed')
        calendar_config=Path(config.caldav_server_config).expanduser()
        if calendar_config.is_file():
            calendar=subprocess.Popen([sys.executable,'-m','radicale','--config',str(calendar_config)],start_new_session=True)
        environment=dict(os.environ)
        environment['APRIL_CONFIG']=str(runtime.absolute())
        widget=subprocess.Popen([sys.executable,'-m','april.launch','--widget','--hidden'],env=environment,start_new_session=True)
        while not interrupted and widget.poll() is None:
            log=Path('artifacts/power.log')
            if log.exists() and log.stat().st_size>2_000_000:
                log.write_text('')  # Child FDs use append mode; bounded local diagnostics.
            time.sleep(.2)
    except (OSError,ValueError,subprocess.CalledProcessError) as exc:
        print('April startup stopped:',str(exc),file=sys.stderr)
        raise SystemExit(1)
    finally:
        for process in (widget,calendar,ollama,search_job):
            if process and process.poll() is None:
                # Only these Popen-created sessions are targets; shared services
                # never enter this list. Signal runners/helpers with their owner.
                try:os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    process.wait()
        if search_started:
            try:subprocess.run(['bash','scripts/searxng.sh','stop'],check=False,timeout=30)
            except (OSError,subprocess.TimeoutExpired):pass
        if owner()==os.getpid():
            STATE.unlink(missing_ok=True)
        for signum,handler in previous.items():signal.signal(signum,handler)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['start','stop','status'])
    parser.add_argument('--foreground',action='store_true')
    parser.add_argument('--login',action='store_true')
    parser.add_argument('--child',action='store_true',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.action=='stop':
        stop();print('April off. Login startup is paused until a manual start.')
    elif args.action=='status':
        current=owner()
        print('Stopping' if current and DISABLED.exists() else 'Running' if current else 'Off')
        print('Login startup paused' if DISABLED.exists() else 'Login startup enabled if installed')
    elif (args.login or args.child) and DISABLED.exists():
        print('April remains off; start manually to resume.')
    elif owner():
        print('April is already running.')
    else:
        if not args.login and not args.child:DISABLED.unlink(missing_ok=True)
        if args.foreground:supervise()
        else:
            STATE.parent.mkdir(exist_ok=True)
            log=Path('artifacts/power.log')
            # Bound startup logs by truncating each launch; no prompt/audio logs.
            log.write_text('')
            with log.open('a') as output:
                subprocess.Popen([sys.executable,'-m','april.power','start','--foreground','--child'],
                                 stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
            log.chmod(0o600)
            print('Starting April. Check python -m april.power status and artifacts/power.log.')


if __name__=='__main__':main()
