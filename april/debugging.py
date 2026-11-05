"""Explicit screen snapshots and approved Python-file review; no silent capture."""
import ast
import base64
import hashlib
import io
import os
from pathlib import Path
import secrets
import tempfile
import asyncio

from .errors import BackendError


def project_file(config, relative):
    if not isinstance(relative,str) or len(relative)>300:
        raise ValueError('Choose a relative Python file')
    if not config.debug_project_root or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Choose a file relative to the approved project folder')
    root=Path(config.debug_project_root).expanduser().resolve(strict=True)
    path=(root/relative).resolve()
    inside=path.relative_to(root)
    if any(part.startswith('.') for part in inside.parts) or path.suffix!='.py' or path.stat().st_size>64_000:
        raise ValueError('Use a non-hidden Python file under 64 KB inside aprilfiles')
    text=path.read_text(encoding='utf-8')
    return root,path,text


def review_file(config, relative):
    root,path,text=project_file(config,relative)
    name=str(path.relative_to(root))
    diagnostic=None
    finding='Syntax parse passed. This does not establish runtime correctness.'
    try:ast.parse(text,filename=name)
    except SyntaxError as exc:
        finding=f'Python syntax error at {name}:{exc.lineno}:{exc.offset}: {exc.msg}'
        diagnostic={'line':exc.lineno or 1,'column':exc.offset or 1,'message':exc.msg}
    lines='\n'.join(f'{i}: {line}' for i,line in enumerate(text.splitlines(),1))
    source={'title':name,'excerpt':finding+'\n'+lines[:12000],'kind':'code','diagnostic':diagnostic}
    return source,{'file':name,'sha256':hashlib.sha256(text.encode()).hexdigest(),'id':secrets.token_urlsafe(24)}


async def screen_text(encoded):
    from PIL import Image
    from .backends import run_process
    if not isinstance(encoded,str) or len(encoded)>1_000_000:
        raise ValueError('Screen snapshot exceeds the size limit')
    raw=base64.b64decode(encoded,validate=True)
    image=Image.open(io.BytesIO(raw))
    if image.width*image.height>2_000_000 or image.format not in {'JPEG','PNG'}:
        raise ValueError('Share a PNG/JPEG snapshot under two megapixels')
    image.load()
    with tempfile.TemporaryDirectory(prefix='april-screen-') as directory:
        path=Path(directory)/'screen.png';image.convert('RGB').save(path)
        output=Path(directory)/'ocr'
        try:
            async with asyncio.timeout(10):
                await run_process('tesseract',str(path),str(output),'--psm','6')
        except (BackendError,FileNotFoundError):
            raise BackendError('screen_ocr_failed','Local OCR failed. Install Tesseract and English language data; no screen was sent to web search.')
        result=output.with_suffix('.txt')
        if result.stat().st_size>1_000_000:
            raise ValueError('OCR output exceeds the local limit')
        text=result.read_text(errors='replace')
    return {'title':'Shared screen OCR','excerpt':str(text)[:12000],
            'kind':'screen','notice':'OCR can misread code and line numbers. File contents are authoritative.'}


async def execute(config,item):
    """Only a user-confirmed Python file in a constrained, networkless container."""
    root,path,text=project_file(config,item['file'])
    if hashlib.sha256(text.encode()).hexdigest()!=item['sha256']:
        raise ValueError('File changed since review. Review and approve it again.')
    if os.getuid()==0:
        raise ValueError('Run APRIL as your normal user')
    temporary=tempfile.TemporaryDirectory(prefix='april-exec-')
    snapshot=Path(temporary.name)/'entry.py'
    snapshot.write_text(text);snapshot.chmod(0o600)
    cidfile=Path(temporary.name)/'container-id'
    name='april-debug-'+secrets.token_hex(8)
    docker=['env','-u','DOCKER_HOST','-u','DOCKER_CONTEXT','-u','DOCKER_TLS','-u','DOCKER_TLS_VERIFY',
            '-u','DOCKER_CERT_PATH','docker','--host=unix:///var/run/docker.sock']
    argv=[*docker,'run','--rm','--pull=never','--name',name,'--cidfile',str(cidfile),'--label','april.debug=true',
          '--network','none','-e','HTTP_PROXY=','-e','HTTPS_PROXY=','-e','ALL_PROXY=','-e','NO_PROXY=',
          '-e','http_proxy=','-e','https_proxy=','-e','all_proxy=','-e','no_proxy=','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
          '--cpus','1','--memory','256m','--pids-limit','64','--user',f'{os.getuid()}:{os.getgid()}',
          '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=64m',
          '--mount',f'type=bind,src={root},dst=/project,readonly',
          '--mount',f'type=bind,src={snapshot},dst=/project/{item["file"]},readonly','--workdir','/project',
          config.debug_runner_image,'python','-E','-s','-B','/project/'+item['file']]
    if ',' in str(root) or ',' in item['file']:
        temporary.cleanup()
        raise ValueError('Docker bind paths containing commas are unsupported')
    process=None
    try:
        process=await asyncio.create_subprocess_exec(*argv,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.STDOUT)
        output=bytearray()
        async with asyncio.timeout(10):
            while chunk:=await process.stdout.read(1024):
                output.extend(chunk)
                if len(output)>16_000:
                    raise ValueError('Execution output exceeded 16 KB')
            await process.wait()
        confirmed=cidfile.is_file() and process.returncode not in {125,126,127}
        return {'exit_code':process.returncode,'execution_started':confirmed,'output':output.decode(errors='replace').replace('/project/',''),
                'notice':('Executed in a limited container, not your IDE. Project is read-only; use /tmp for temporary writes. Network and third-party dependencies are unavailable. These environment limits are not automatically code bugs.' if confirmed else 'Container execution was not confirmed. Inspect the runner error; do not assume the program ran.')}
    finally:
        if process and process.returncode is None:
            process.kill();await process.wait()
        try:
            cleanup=await asyncio.create_subprocess_exec(*docker,'rm','-f',name,stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            try:await asyncio.wait_for(cleanup.wait(),5)
            except asyncio.TimeoutError:cleanup.kill();await cleanup.wait()
        finally:
            temporary.cleanup()
