"""Unavailable services must produce specific repair guidance, not guesses."""
import asyncio
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from april.backends import LocalBackends
from april.config import Config
from april.errors import BackendError
from april.launch import main
from april.readiness import check_readiness
from april.session import Session
from april.state import State


class ReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def test_offline_ollama_reports_exact_recovery_and_missing_files(self):
        def offline(request):
            raise httpx.ConnectError('private diagnostic must not leak', request=request)
        report = await check_readiness(Config(whisper_cli='missing-april-stt', piper_cli='missing-april-tts',
            stt_model='/nonexistent/april-model',voice='/nonexistent/april-voice'),
            transport=httpx.MockTransport(offline))
        self.assertFalse(report['ready'])
        self.assertIn('sudo systemctl start ollama', json.dumps(report))
        self.assertNotIn('private diagnostic', json.dumps(report))
        self.assertTrue(all(not c['ready'] for c in report['checks']))

    async def test_readiness_uses_only_model_listing_not_model_loading(self):
        requests = []
        def tags(request):
            requests.append((request.method,request.url.path))
            return httpx.Response(200,json={'models':[{'name':'gpt-oss:20b'}]})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root/'model'; voice = root/'voice.onnx'
            for file in [model,voice,Path(str(voice)+'.json')]:
                file.write_text('fixture')
            import sys
            config = Config(model='gpt-oss:20b',whisper_cli=sys.executable,piper_cli=sys.executable,
                            stt_model=str(model),voice=str(voice))
            report = await check_readiness(config,transport=httpx.MockTransport(tags))
            self.assertTrue(report['ready'])
            missing = await check_readiness(Config(**{**config.__dict__,'model':'absent:latest'}),transport=httpx.MockTransport(tags))
            self.assertFalse(missing['ready'])
            self.assertIn('not listed',missing['checks'][-1]['message'])
        self.assertEqual(requests,[('GET','/api/tags'),('GET','/api/tags')])

    async def test_runtime_error_is_actionable_and_session_can_retry(self):
        backend = LocalBackends(Config())
        messages=[]
        async def send(message):
            messages.append(message)
        session=Session(Config(automatic_web_search=False),backend,send,asyncio.Lock())
        with patch.object(backend,'_respond',AsyncMock(side_effect=httpx.ConnectError('private URL/secret'))):
            await session.handle({'type':'text','text':'hello'})
            await session.task
        self.assertEqual(session.machine.state,State.ERROR)
        self.assertEqual(messages[-1]['code'],'ollama_unavailable')
        self.assertNotIn('private URL',str(messages))
        self.assertFalse(session.gate.locked())
        from april.backends import SimulationBackends
        session.backends=SimulationBackends()
        session.config=Config(mode='simulation')
        await session.handle({'type':'text','text':'retry'})
        await session.task
        self.assertEqual(session.machine.state,State.IDLE)
        await session.cancel()

    async def test_http_404_has_model_guidance_without_body_leak(self):
        backend=LocalBackends(Config())
        response=httpx.Response(404,request=httpx.Request('POST','http://localhost/api/chat'),text='private body')
        with patch.object(backend,'_respond',AsyncMock(side_effect=httpx.HTTPStatusError('private body',request=response.request,response=response))):
            with self.assertRaises(BackendError) as error:
                await backend.respond('hello')
        self.assertIn('ollama list',str(error.exception))
        self.assertNotIn('private body',str(error.exception))


class LauncherTests(unittest.TestCase):
    def test_existing_local_configuration_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'settings.toml'
            config.write_text('model = "my-existing-model"\n')
            result={'ready':False,'checks':[{'component':'Ollama','ready':False,'message':'Not running'}]}
            with patch.dict(os.environ,{'APRIL_CONFIG':str(config),'APRIL_MODE':'simulation'}), \
                 patch('sys.argv',['april','--check']), \
                 patch('april.launch.check_readiness',AsyncMock(return_value=result)), \
                 contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    main()
                self.assertEqual(error.exception.code,1)
                self.assertEqual(os.environ['APRIL_MODE'],'live')
            self.assertEqual(config.read_text(),'model = "my-existing-model"\n')

    def test_simulation_check_does_not_create_local_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            config=Path(directory)/'settings.toml'
            with patch.dict(os.environ,{'APRIL_CONFIG':str(config)}), \
                 patch('sys.argv',['april','--simulation','--check']), \
                 contextlib.redirect_stdout(io.StringIO()):
                main()
            self.assertFalse(config.exists())

    def test_search_startup_runs_only_own_helper_then_app(self):
        from types import SimpleNamespace
        for exit_code in [0, 1]:
            with self.subTest(exit_code=exit_code), tempfile.TemporaryDirectory() as directory:
                config=Path(directory)/'settings.toml'
                config.write_text('model = "existing-model"\n')
                with patch.dict(os.environ,{'APRIL_CONFIG':str(config)}), \
                     patch('sys.argv',['april','--with-search']), \
                     patch('april.launch.check_readiness',AsyncMock(return_value={'ready':True,'checks':[]})), \
                     patch('april.launch.subprocess.run',return_value=SimpleNamespace(returncode=exit_code)) as run, \
                     patch('april.server.main') as serve, \
                     contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    if exit_code:
                        with self.assertRaises(SystemExit) as error:main()
                        self.assertEqual(error.exception.code,1)
                        serve.assert_not_called()
                    else:
                        main()
                        serve.assert_called_once_with()
                    run.assert_called_once_with(['bash','scripts/searxng.sh','up'],check=False)
                self.assertEqual(config.read_text(),'model = "existing-model"\n')

    def test_checks_and_simulation_never_start_search(self):
        for flags in [['--check'], ['--simulation','--check']]:
            with tempfile.TemporaryDirectory() as directory:
                config=Path(directory)/'settings.toml';config.write_text('model = "existing-model"\n')
                with patch.dict(os.environ,{'APRIL_CONFIG':str(config)}), \
                     patch('sys.argv',['april',*flags]), \
                     patch('april.launch.check_readiness',AsyncMock(return_value={'ready':True,'checks':[]})), \
                     patch('april.launch.subprocess.run') as run, \
                     contextlib.redirect_stdout(io.StringIO()):
                    main()
                    run.assert_not_called()

    def test_search_flag_cannot_mutate_read_only_or_simulation_startup(self):
        for flags in [['--check'], ['--simulation']]:
            with patch('sys.argv',['april','--with-search',*flags]), \
                 patch('april.launch.subprocess.run') as run, \
                 contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:main()
                self.assertEqual(error.exception.code,2)
                run.assert_not_called()
