"""Create private SearXNG settings without overwriting existing configuration."""
import argparse
import json
import os
import secrets
from pathlib import Path


def initialize(root=Path('artifacts/searxng')):
    root=Path(root)
    for folder in [root,root/'config',root/'cache']:
        if folder.is_symlink():raise ValueError('Refusing a symlinked service folder')
        folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    settings=root/'config/settings.yml'
    if settings.is_symlink():raise ValueError('Refusing symlinked settings')
    if not settings.exists():
        secret=json.dumps(secrets.token_hex(32))
        text=f'''use_default_settings:
  engines:
    keep_only: [duckduckgo, brave, wikipedia]
engines:
  - name: wikipedia
    display_type: [infobox, list]
general:
  instance_name: "APRIL Search"
search:
  safe_search: 1
  autocomplete: ""
  formats: [html, json]
server:
  secret_key: {secret}
  limiter: false
  public_instance: false
  image_proxy: false
  method: "POST"
outgoing:
  request_timeout: 5.0
  max_request_timeout: 8.0
'''
        fd=os.open(settings,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as file:file.write(text)
    env=root/'compose.env'
    if env.is_symlink():raise ValueError('Refusing symlinked service environment')
    if not env.exists():
        fd=os.open(env,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as file:
            file.write(f'APRIL_SEARCH_UID={os.getuid()}\nAPRIL_SEARCH_GID={os.getgid()}\nAPRIL_SEARCH_PORT=8888\n')
    values=dict(line.split('=',1) for line in env.read_text().splitlines() if line and not line.startswith('#'))
    if int(values['APRIL_SEARCH_UID'])!=os.getuid() or int(values['APRIL_SEARCH_GID'])!=os.getgid():
        raise ValueError('Service files belong to another user; do not run this helper with sudo')
    port=int(values['APRIL_SEARCH_PORT'])
    if not 1024<=port<=65535:raise ValueError('Invalid local search port')
    return f'http://127.0.0.1:{port}'


def main():
    parser=argparse.ArgumentParser(description='Initialize private APRIL SearXNG files; preserve existing settings.')
    parser.parse_args()
    try:url=initialize()
    except (OSError,ValueError,KeyError):parser.exit(1,'Cannot prepare search files safely. Check ownership and artifacts/searxng; existing settings are not overwritten.\n')
    print('Private SearXNG settings prepared; existing settings preserved.')
    print('Loopback address: '+url)
    print('Query/engine availability still requires an actual search test.')


if __name__=='__main__':main()
