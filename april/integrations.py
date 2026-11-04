"""Explicit local setup. Secrets stay outside Git and never enter command history."""
import argparse
import getpass
import json
import os
import tempfile
import stat
import tomllib
import re
from pathlib import Path

from .config import Config,load_config


def write_settings(config_path,previous,candidate):
    """Validate and replace only a version we actually inspected."""
    Config(**tomllib.loads(candidate))
    fd,name=tempfile.mkstemp(prefix='.april-settings-',dir=config_path.parent)
    try:
        os.fchmod(fd,stat.S_IMODE(config_path.stat().st_mode))
        with os.fdopen(fd,'w') as file:file.write(candidate)
        if config_path.read_text()!=previous:raise ValueError('Settings changed while preparing update')
        os.replace(name,config_path)
    finally:
        if os.path.exists(name):os.unlink(name)


def configure_search(config_path,provider,url=None):
    path=Path(config_path)
    if path.is_symlink():raise ValueError('Refusing to replace symlinked settings')
    previous=path.read_text();data=tomllib.loads(previous)
    changes={'web_provider':provider}
    if url is not None:changes['searxng_url']=url
    candidate=previous
    for key,value in changes.items():
        assignment=key+' = '+json.dumps(value)
        if key in data:
            pattern=re.compile(r'^\s*'+re.escape(key)+r'\s*=.*$',re.M)
            matches=list(pattern.finditer(candidate))
            if len(matches)!=1 or tomllib.loads(matches[0][0]).get(key)!=data[key]:
                raise ValueError('Update this setting manually; multi-line/ambiguous settings were not changed')
            candidate=pattern.sub(lambda match:assignment,candidate,count=1)
        else:candidate=candidate.rstrip()+'\n'+assignment+'\n'
    if tomllib.loads(candidate)!={**data,**changes}:raise ValueError('Unrelated settings would change')
    write_settings(path,previous,candidate)


def configure_documents(config_path,folder):
    config_path=Path(config_path)
    if config_path.is_symlink():raise ValueError('Refusing to replace symlinked settings')
    previous=config_path.read_text()
    data=tomllib.loads(previous)
    approved=str(Path(folder).expanduser().absolute())
    if data.get('document_roots') and data['document_roots'] != [approved]:
        raise ValueError('Existing document_roots differ. Review them manually; no access was broadened.')
    additions={'document_roots':[approved]}
    if 'document_roots' in data:
        if data['document_roots'] == [approved]:return False
        raise ValueError('document_roots already exists. Set it explicitly in the local config; no file was overwritten.')
    candidate=previous.rstrip()+'\n\n# Explicitly approved local retrieval folder.\n'+''.join(
        key+' = '+json.dumps(value)+'\n' for key,value in additions.items())
    Config(**tomllib.loads(candidate))
    Path(approved).mkdir(parents=True,exist_ok=True,mode=0o700)
    write_settings(config_path,previous,candidate)
    return True


def main():
    parser=argparse.ArgumentParser(description='Set up opt-in retrieval with no hidden account connections.')
    sub=parser.add_subparsers(dest='action',required=True)
    documents=sub.add_parser('documents')
    documents.add_argument('--folder',required=True,type=Path)
    provider=sub.add_parser('search-provider')
    provider.add_argument('provider',choices=['searxng','brave'])
    provider.add_argument('--url',help='Loopback SearXNG base URL; defaults to http://127.0.0.1:8888')
    sub.add_parser('web-key')
    args=parser.parse_args()
    if args.action=='search-provider':
        if args.provider=='brave' and args.url:parser.error('--url applies only to searxng')
        try:
            configure_search(os.environ.get('APRIL_CONFIG','april.local.toml'),args.provider,
                args.url or 'http://127.0.0.1:8888' if args.provider=='searxng' else None)
        except (ValueError,TypeError,OSError):
            parser.exit(1,'Cannot update provider safely. Check april.local.toml and the loopback URL. Existing settings were preserved.\n')
        print('Selected '+args.provider+'. Restart APRIL and verify an actual search; this does not start services or validate a key.')
        return
    if args.action=='documents':
        try:
            changed=configure_documents(os.environ.get('APRIL_CONFIG','april.local.toml'),args.folder)
        except (ValueError,TypeError,OSError):
            parser.exit(1,'Cannot update settings safely. Ensure april.local.toml exists and review any existing document_roots; nothing is intentionally overwritten.\n')
        print('Folder approved.' if changed else 'That folder was already approved.')
        print('Copy only files you want searchable into it, then run python -m april.documents index.')
        return
    config=load_config()
    if os.environ.get(config.web_api_key_env):
        print('A search-key environment binding is already present. No key file was created; verify it with an actual query.')
        return
    path=Path(config.web_key_path).expanduser()
    if path.exists():parser.exit(1,'A key file already exists. Review/remove that specific file yourself before replacing it.\n')
    token=getpass.getpass('Brave Search API key (hidden; never paste into chat): ').strip()
    if not token or len(token)>4096 or '\n' in token or '\r' in token:
        parser.exit(1,'No valid key entered.\n')
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    try:
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as file:file.write(token)
    except OSError:parser.exit(1,'Could not create private key file. Existing files were not replaced.\n')
    print('Search key saved privately outside the repository. It has not been validated against the provider yet.')


if __name__=='__main__':main()
