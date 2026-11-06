"""Explicit desktop setup; reuse a verified existing model store, never download one."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import shlex
import tomllib

import httpx

from .config import Config, load_config
from .integrations import write_settings


def update_settings(path, changes):
    path=Path(path)
    if path.is_symlink():raise ValueError('Refusing symlinked local configuration.')
    previous=path.read_text()
    data=tomllib.loads(previous)
    candidate=previous
    for key,value in changes.items():
        assignment=key+' = '+json.dumps(value)
        if key in data:
            pattern=re.compile(r'^\s*'+re.escape(key)+r'\s*=.*$',re.M)
            matches=list(pattern.finditer(candidate))
            if len(matches)!=1 or tomllib.loads(matches[0][0]).get(key)!=data[key]:
                raise ValueError('Please edit ambiguous/multiline '+key+' manually.')
            candidate=pattern.sub(lambda match:assignment,candidate,count=1)
        else:candidate=candidate.rstrip()+'\n'+assignment+'\n'
    if tomllib.loads(candidate)!={**data,**changes}:raise ValueError('Unrelated settings would change.')
    write_settings(path,previous,candidate)


def validate_store(path, model_blob=None):
    store=Path(path).expanduser().resolve()
    if not (store/'blobs').is_dir() or not (store/'manifests').is_dir():
        raise ValueError('Model store must contain readable blobs/ and manifests/ directories.')
    if not os.access(store,os.R_OK|os.X_OK):raise ValueError('Existing model store is not readable by your desktop user.')
    if model_blob and (not model_blob.is_file() or not os.access(model_blob,os.R_OK)):
        raise ValueError('The existing model blob is not readable by your desktop user; no permissions were changed.')
    return str(store)


async def discover_store(config, *, transport=None):
    """Read public local model metadata, not system credentials or service ownership."""
    async with httpx.AsyncClient(trust_env=False,timeout=10,transport=transport) as client:
        for attempt in range(24):
            try:
                response=await client.post(config.ollama_url+'/api/show',json={'model':config.model})
                break
            except (httpx.ConnectError,httpx.ConnectTimeout):
                if attempt==23:raise
                await asyncio.sleep(.25)
        response.raise_for_status()
        if len(response.content)>256_000:raise ValueError('Oversized model metadata.')
        modelfile=response.json().get('modelfile','')
    if not isinstance(modelfile,str):raise ValueError('Invalid model metadata.')
    for line in modelfile.splitlines():
        if not line.startswith('FROM '):continue
        values=shlex.split(line)
        if len(values)!=2:continue
        blob=Path(values[1])
        if blob.is_absolute() and blob.parent.name=='blobs':
            return validate_store(blob.parent.parent,blob)
    raise ValueError('Ollama did not report a readable existing blob path; use --model-store with the actual store.')


async def configure(path, *, model_store=None, transport=None):
    path=Path(path)
    if not path.exists():
        profile=Path('april.desktop.example.toml')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as file:file.write(profile.read_text())
    config=Config(**tomllib.loads(path.read_text()))
    existing=model_store or config.private_ollama_models
    store=validate_store(existing) if existing else await discover_store(config,transport=transport)
    changes={'private_ollama_models':store,'memory_enabled':True,
             'conversation_history_turns':12,'conversation_context_turns':6,
             'conversation_idle_minutes':30,'memory_max_notes':500,
             'private_ollama_keep_alive_seconds':300,'max_record_seconds':25,'wake_silence_seconds':1.4}
    # Keep the existing bounded local-model context and all account/device settings.
    if config.context_tokens<4096:changes['context_tokens']=4096
    update_settings(path,changes)
    return Config(**tomllib.loads(path.read_text()))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-store',help='Optional existing readable model store, containing blobs and manifests')
    parser.add_argument('--login',action='store_true',help='Register managed startup after desktop login')
    args=parser.parse_args()
    path=Path(os.environ.get('APRIL_CONFIG','april.local.toml'))
    try:
        config=asyncio.run(configure(path,model_store=args.model_store))
        if args.login:
            from .autostart import install
            directory=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'autostart'
            install(Path.cwd(),directory,config_path=path.resolve())
    except (OSError,ValueError,TypeError,httpx.HTTPError):
        parser.exit(1,'Setup stopped. Start your existing Ollama with sudo systemctl start ollama, then retry. '
                    'If needed, pass --model-store /actual/readable/models. Existing models were not downloaded or permissions changed.\n')
    print('Managed desktop settings prepared. Existing local device, voice and account settings were preserved.')
    print('Login entry installed.' if args.login else 'Login entry not changed; add --login to register it.')
    print('Stop the old foreground widget with Ctrl+C, then run: bash april.sh start --wait')
    print('Docker must be available at login: sudo systemctl enable --now docker')
    print('Check status: bash april.sh status. Off/Goodbye pauses login launch until manual start.')

if __name__=='__main__':main()
