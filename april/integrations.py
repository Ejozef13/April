"""Explicit local setup. Secrets stay outside Git and never enter command history."""
import argparse
import json
import os
import tempfile
import stat
import tomllib
import re
from pathlib import Path

from .config import Config


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


def configure_search(config_path,url):
    path=Path(config_path)
    if path.is_symlink():raise ValueError('Refusing to replace symlinked settings')
    previous=path.read_text();data=tomllib.loads(previous)
    changes={'web_provider':'searxng','searxng_url':url}
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
    search=sub.add_parser('search', help='Configure the local SearXNG endpoint')
    search.add_argument('--url', default='http://127.0.0.1:8888', help='Loopback SearXNG base URL')
    args=parser.parse_args()
    if args.action=='search':
        try:
            configure_search(os.environ.get('APRIL_CONFIG','april.local.toml'),args.url)
        except (ValueError,TypeError,OSError):
            parser.exit(1,'Cannot update search safely. Check april.local.toml and the loopback URL. Existing settings were preserved.\n')
        print('Local search configured. Restart APRIL and verify a query; this command does not start services.')
        return
    if args.action=='documents':
        try:
            changed=configure_documents(os.environ.get('APRIL_CONFIG','april.local.toml'),args.folder)
        except (ValueError,TypeError,OSError):
            parser.exit(1,'Cannot update settings safely. Ensure april.local.toml exists and review any existing document_roots; nothing is intentionally overwritten.\n')
        print('Folder approved.' if changed else 'That folder was already approved.')
        print('Copy only files you want searchable into it, then run python -m april.documents index.')
        return


if __name__=='__main__':main()
