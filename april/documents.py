"""Opt-in local lexical RAG index. No embeddings, background crawl, or writes to source files."""
import argparse
import json
import os
import re
import sqlite3
from pathlib import Path

from .config import load_config
from .errors import BackendError

EXTENSIONS = {'.txt', '.md', '.rst', '.csv', '.json', '.py'}
SKIP_DIRS = {'node_modules', '__pycache__', 'artifacts', 'models', 'venv', 'build', 'dist'}
SENSITIVE = re.compile(r'credential|password|secret|private[_-]?key|token', re.I)
SECRET_CONTENT = re.compile(r'"(?:client_secret|refresh_token|private_key|access_token)"\s*:|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
MAX_FILES, MAX_FILE_BYTES, MAX_CHUNKS = 1000, 1_000_000, 5000


def approved_roots(config):
    if not config.document_roots:
        raise BackendError('documents_not_configured', 'Document search is disabled. Approve document_roots in april.local.toml, then build the index.')
    roots=[]
    for value in config.document_roots:
        root=Path(value).expanduser()
        if root.is_symlink() or not root.is_dir():
            raise BackendError('documents_root_invalid', 'An approved document folder is missing or is a symlink. Check document_roots.')
        roots.append(root.resolve())
    return roots


def build_index(config):
    roots=approved_roots(config)
    target=Path(config.documents_index_path).expanduser()
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.is_symlink():
        raise BackendError('documents_index_invalid','Refusing to write a symlinked index.')
    # This file contains private excerpts. Existing arbitrary SQLite databases
    # are never adopted/overwritten just because they share the configured path.
    existed=target.exists()
    if not existed:
        fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        os.close(fd)
    with sqlite3.connect(target) as connection:
        if existed:
            tables={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'april_manifest' not in tables:
                raise BackendError('documents_index_invalid','The index path belongs to another database. Choose a new documents_index_path.')
        connection.execute('CREATE TABLE IF NOT EXISTS april_manifest (roots TEXT NOT NULL)')
        connection.execute('CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(source UNINDEXED, text)')
        connection.execute('DELETE FROM chunks')
        connection.execute('DELETE FROM april_manifest')
        connection.execute('INSERT INTO april_manifest VALUES (?)',(json.dumps([str(r) for r in roots]),))
        files=chunks=skipped=0
        limited=False
        for root_number,root in enumerate(roots,1):
            for directory,dirs,names in os.walk(root,followlinks=False):
                dirs[:]=sorted(d for d in dirs if not d.startswith('.') and d not in SKIP_DIRS
                               and not SENSITIVE.search(d) and not (Path(directory)/d).is_symlink())
                for name in sorted(names):
                    path=Path(directory)/name
                    if name.startswith('.') or path.suffix.lower() not in EXTENSIONS or SENSITIVE.search(name) or path.is_symlink():
                        skipped+=1; continue
                    if files >= MAX_FILES or chunks >= MAX_CHUNKS:
                        limited=True; break
                    try:
                        if not path.resolve().is_relative_to(root) or path.stat().st_size > MAX_FILE_BYTES:
                            skipped+=1;continue
                        # Read bound also covers a file that grows after stat().
                        with path.open('rb') as source:
                            raw=source.read(MAX_FILE_BYTES+1)
                        if len(raw)>MAX_FILE_BYTES or b'\x00' in raw:
                            skipped+=1;continue
                        text=raw.decode('utf-8')
                        if SECRET_CONTENT.search(text):
                            skipped+=1;continue
                    except (OSError,UnicodeError):
                        skipped+=1;continue
                    files+=1
                    for offset in range(0,len(text),1000):
                        if chunks >= MAX_CHUNKS:
                            limited=True;break
                        excerpt=text[offset:offset+1200].strip()
                        if excerpt:
                            source=f'Folder {root_number}/{path.relative_to(root).as_posix()} · chunk {offset//1000+1}'
                            connection.execute('INSERT INTO chunks VALUES (?,?)',(source,excerpt))
                            chunks+=1
                if limited:break
            if limited:break
    return {'files':files,'chunks':chunks,'skipped':skipped,'limited':limited}


def search_documents(config,query):
    roots=approved_roots(config)
    target=Path(config.documents_index_path).expanduser()
    if not target.is_file() or target.is_symlink():
        raise BackendError('documents_not_indexed','Build the approved folder index with python -m april.documents index first.')
    words=re.findall(r'[^\W_]+',query,flags=re.UNICODE)[:12]
    if not words:return []
    expression=' OR '.join('"'+word.replace('"','""')+'"' for word in words)
    try:
        with sqlite3.connect(target.resolve().as_uri()+'?mode=ro',uri=True) as connection:
            manifest=connection.execute('SELECT roots FROM april_manifest').fetchone()
            if not manifest or json.loads(manifest[0]) != [str(r) for r in roots]:
                raise BackendError('documents_index_stale','Approved folders changed. Rebuild the index before searching.')
            results=connection.execute('SELECT source,text FROM chunks WHERE chunks MATCH ? ORDER BY rank LIMIT 3',(expression,)).fetchall()
    except (sqlite3.Error,ValueError) as exc:
        raise BackendError('documents_index_invalid','The document index is unreadable. Check its path and rebuild it.') from exc
    return [{'title':source,'excerpt':text[:1200],'url':None,'kind':'document'} for source,text in results]


def main():
    parser=argparse.ArgumentParser(description='Explicitly index approved folders for local retrieval. Private excerpts persist locally.')
    parser.add_argument('action',choices=['index'])
    parser.parse_args()
    try:
        result=build_index(load_config())
    except BackendError as exc:
        parser.exit(1,str(exc)+'\n')
    except (OSError,sqlite3.Error,ValueError,TypeError):
        parser.exit(1,'Index setup failed. Check approved folder permissions, local configuration, and SQLite FTS5 support; source files were not modified.\n')
    print(json.dumps(result))
    print('Private excerpts are stored locally. Review approved files; filename exclusions cannot detect every secret inside ordinary text.')


if __name__=='__main__':main()
