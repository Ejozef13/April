"""Public fixtures: no personal inbox, desktop screen, model inference or code execution."""
import asyncio
import base64
from datetime import datetime,timedelta,timezone
import io
import importlib.util
import shutil
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, AsyncMock

import httpx
from april.config import Config
from april.tools import is_goodbye_request
from april.debugging import review_file, screen_text
from april import power
from april.session import Session
from types import SimpleNamespace


class UpgradeTests(unittest.TestCase):
    def test_goodbye_is_exact_not_a_retrieved_instruction(self):
        self.assertTrue(is_goodbye_request('Goodbye April!'))
        for text in ['write a poem saying goodbye april','hello april','do not say goodbye april']:
            self.assertFalse(is_goodbye_request(text))

    def test_file_review_has_real_syntax_line_and_rejects_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'bug.py').write_text('def broken(:\n    pass\n')
            config=Config(debug_project_root=str(root))
            source,item=review_file(config,'bug.py')
            self.assertIn('bug.py:1:',source['excerpt'])
            self.assertIn('1: def broken',source['excerpt'])
            self.assertIn('sha256',item)
            with self.assertRaises(ValueError):review_file(config,'../outside.py')
            (root/'.hidden.py').write_text('print(1)')
            with self.assertRaises(ValueError):review_file(config,'.hidden.py')

    def test_off_persists_and_does_not_signal_recycled_pid(self):
        with tempfile.TemporaryDirectory() as directory:
            state=Path(directory)/'power.json';disabled=Path(directory)/'disabled'
            state.write_text(json.dumps({'pid':98765,'started':'old'}))
            with patch.object(power,'STATE',state),patch.object(power,'DISABLED',disabled), \
                 patch.object(power,'process_identity',return_value='new'),patch.object(power.os,'kill') as kill:
                self.assertFalse(power.stop())
                self.assertTrue(disabled.exists())
                kill.assert_not_called()
                with patch('sys.argv',['power','start','--login']),patch.object(power.subprocess,'Popen') as spawn:
                    power.main();spawn.assert_not_called()


class PowerRaceTests(unittest.TestCase):
    def test_stop_marker_is_not_cleared_by_an_already_spawned_start_child(self):
        with tempfile.TemporaryDirectory() as directory:
            disabled=Path(directory)/'disabled';disabled.touch()
            state=Path(directory)/'state.json'
            with patch.object(power,'DISABLED',disabled),patch.object(power,'STATE',state), \
                 patch('sys.argv',['power','start','--foreground','--child']), \
                 patch.object(power,'supervise') as start:
                power.main()
                start.assert_not_called()
                self.assertTrue(disabled.exists())


class ApprovalTests(unittest.IsolatedAsyncioTestCase):
    @unittest.skipUnless(importlib.util.find_spec('icalendar') and importlib.util.find_spec('defusedxml'),'Optional assistant dependencies not installed')
    async def test_review_is_required_and_confirmation_is_single_use(self):
        from april.calendar import proposal
        messages=[]
        async def send(message):messages.append(message)
        backend=SimpleNamespace()
        session=Session(Config(),backend,send,asyncio.Lock())
        start=datetime.now(timezone.utc)+timedelta(days=1)
        event={'title':'Public fixture','start':start.isoformat(),'end':(start+timedelta(hours=1)).isoformat()}
        with patch('april.calendar.commit',AsyncMock(return_value='"v1"')) as commit:
            await session.handle({'type':'calendar_propose','event':event});await session.task
            commit.assert_not_awaited()
            review=next(m for m in messages if m['type']=='review')
            await session.handle({'type':'calendar_confirm','id':review['id']});await session.task
            commit.assert_awaited_once()
            await session.handle({'type':'calendar_confirm','id':review['id']});await session.task
            self.assertEqual(commit.await_count,1)
            self.assertFalse(session.gate.locked())
        await session.cancel()

    @unittest.skipUnless(importlib.util.find_spec('icalendar') and importlib.util.find_spec('defusedxml'),'Optional assistant dependencies not installed')
    async def test_briefing_combines_private_sources_without_web(self):
        from test_core import wav_bytes
        messages=[]
        async def send(message):messages.append(message)
        async def synthesize(reply,output):output.write_bytes(wav_bytes())
        backend=SimpleNamespace(respond=AsyncMock(return_value='Fixture briefing'),synthesize=synthesize)
        session=Session(Config(),backend,send,asyncio.Lock())
        calendar=[{'title':'Calendar fixture','excerpt':'Meeting tomorrow','kind':'calendar'}]
        mail=[{'title':'Mail fixture','excerpt':'Interview invitation','kind':'gmail'}]
        with patch('april.calendar.events',AsyncMock(return_value=calendar)), \
             patch('april.gmail.search_gmail',AsyncMock(return_value=mail)), \
             patch('april.session.retrieve',AsyncMock()) as web:
            await session.handle({'type':'briefing'});job=session.task;await job
            backend.respond.assert_awaited_once()
            self.assertEqual(len(backend.respond.call_args.kwargs['sources']),2)
            web.assert_not_awaited()
        await session.cancel()

    async def test_playback_completion_preserves_review_but_stop_revokes(self):
        from april.state import State
        async def send(message):pass
        session=Session(Config(),SimpleNamespace(),send,asyncio.Lock())
        await session.begin()
        await session.state(State.THINKING)
        session.pending_review={'id':'fixture-review'}
        await session.playback_started()
        await session.handle({'type':'played'})
        self.assertEqual(session.pending_review,{'id':'fixture-review'})
        self.assertFalse(session.gate.locked())
        await session.cancel()
        self.assertIsNone(session.pending_review)

    async def test_runner_failure_does_not_claim_program_executed(self):
        from april.debugging import execute
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'main.py').write_text('print(1)')
            config=Config(debug_project_root=str(root));_,item=review_file(config,'main.py')
            output=SimpleNamespace(read=AsyncMock(side_effect=[b'fixture image unavailable',b'']))
            failed=SimpleNamespace(stdout=output,returncode=125,wait=AsyncMock(return_value=125))
            cleanup=SimpleNamespace(wait=AsyncMock(return_value=0))
            with patch('april.debugging.asyncio.create_subprocess_exec',AsyncMock(side_effect=[failed,cleanup])):
                result=await execute(config,item)
            self.assertFalse(result['execution_started'])
            self.assertIn('not confirmed',result['notice'])

    @unittest.skipUnless(importlib.util.find_spec('icalendar') and importlib.util.find_spec('defusedxml'),'Optional assistant dependencies not installed')
    async def test_accepted_calendar_write_is_not_reported_as_complete(self):
        from april.calendar import commit,proposal
        from april.errors import BackendError
        with tempfile.TemporaryDirectory() as directory:
            credentials=Path(directory)/'creds.json'
            credentials.write_text('{"username":"fixture","password":"public-fixture"}');credentials.chmod(0o600)
            config=Config(caldav_credentials=str(credentials))
            start=datetime.now(timezone.utc)
            item=proposal({'title':'Fixture','start':start.isoformat(),'end':(start+timedelta(hours=1)).isoformat()})
            with self.assertRaises(BackendError) as error:
                await commit(config,item,transport=httpx.MockTransport(lambda request:httpx.Response(202)))
            self.assertEqual(error.exception.code,'calendar_write_unconfirmed')

    async def test_goodbye_never_calls_model_or_web(self):
        messages=[]
        async def send(message):messages.append(message)
        backend=SimpleNamespace(respond=AsyncMock())
        session=Session(Config(),backend,send,asyncio.Lock())
        with patch('april.session.retrieve',AsyncMock()) as retrieval:
            await session.handle({'type':'text','text':'Goodbye April'});await session.task
            retrieval.assert_not_awaited();backend.respond.assert_not_awaited()
        self.assertTrue(any(m.get('action')=='shutdown' for m in messages))
        self.assertFalse(session.gate.locked())
        await session.cancel()

    @unittest.skipUnless(importlib.util.find_spec('PIL') and shutil.which('tesseract'),'Optional OCR dependencies not installed')
    async def test_real_local_ocr_on_public_fixture(self):
        from PIL import Image,ImageDraw,ImageFont
        image=Image.new('RGB',(1000,200),'white')
        fonts=[Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'),Path('/usr/share/fonts/TTF/DejaVuSansMono.ttf')]
        chosen=next((font for font in fonts if font.is_file()),None)
        font=ImageFont.truetype(str(chosen),40) if chosen else ImageFont.load_default(size=40)
        ImageDraw.Draw(image).text((30,50),'print(123)',font=font,fill='black')
        output=io.BytesIO();image.save(output,format='PNG')
        result=await screen_text(base64.b64encode(output.getvalue()).decode())
        self.assertIn('123',result['excerpt'])
        self.assertIn('OCR',result['notice'])


class CrossClientTests(unittest.TestCase):
    def test_only_busy_status_is_shared_across_clients(self):
        from fastapi.testclient import TestClient
        from april.server import create_app
        config=Config(mode='simulation')
        with TestClient(create_app(config),base_url='http://127.0.0.1:8765') as client:
            with client.websocket_connect('ws://127.0.0.1:8765/ws',headers={'Origin':'http://127.0.0.1:8765'}) as first:
                first.receive_json()
                with client.websocket_connect('ws://127.0.0.1:8765/ws',headers={'Origin':'http://127.0.0.1:8765'}) as second:
                    second.receive_json()
                    first.send_json({'type':'record'})
                    self.assertEqual(first.receive_json()['state'],'listening')
                    self.assertEqual(second.receive_json(),{'type':'availability','busy':True})
                    first.send_json({'type':'cancel'})
                    self.assertEqual(first.receive_json()['state'],'idle')
                    self.assertEqual(second.receive_json(),{'type':'availability','busy':False})


class DebugBoundaryTests(unittest.TestCase):
    def test_editor_endpoint_rejects_foreign_origin_and_path_escape(self):
        from fastapi.testclient import TestClient
        from april.server import create_app
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'bug.py').write_text('def broken(:\n pass')
            config=Config(debug_project_root=str(root))
            with TestClient(create_app(config),base_url='http://127.0.0.1:8765') as client:
                response=client.post('/api/debug/check',json={'file':'bug.py'})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['diagnostics'][0]['line'],1)
                self.assertEqual(client.post('/api/debug/check',json={'file':'../private.py'}).status_code,400)
                self.assertEqual(client.post('/api/debug/check',json={'file':'bug.py'},
                                            headers={'Origin':'https://foreign.example'}).status_code,403)
