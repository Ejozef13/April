"""Existing-model discovery, managed setup and conversation-context fixtures."""
import asyncio
from dataclasses import replace
import json
import importlib.util
from pathlib import Path
import tempfile
import time
import tomllib
import unittest
from unittest.mock import AsyncMock,patch
from types import SimpleNamespace

import httpx
from april.config import Config
from april.onboarding import configure,update_settings
from april.memory import MemoryStore,local_conversation
from april.session import Session
from test_core import wav_bytes


class DesktopSetupTests(unittest.IsolatedAsyncioTestCase):
    async def test_model_discovery_preserves_existing_settings_without_download(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);store=root/'models';(store/'blobs').mkdir(parents=True);(store/'manifests').mkdir()
            blob=store/'blobs'/'sha256-public-fixture';blob.write_text('fixture')
            config=root/'local.toml';config.write_text('model = "gpt-oss:20b"\ntimezone = "America/New_York"\ndesktop_input_device = "A private device name"\n')
            seen=[]
            def handler(request):
                seen.append(request)
                if len(seen)<3:raise httpx.ConnectError('Fixture service starting',request=request)
                return httpx.Response(200,json={'modelfile':'FROM '+str(blob)+'\nPARAMETER num_ctx 4096'})
            updated=await configure(config,transport=httpx.MockTransport(handler))
            self.assertEqual(updated.private_ollama_models,str(store))
            self.assertEqual(updated.desktop_input_device,'A private device name')
            self.assertEqual(updated.context_tokens,4096)
            self.assertEqual([request.url.path for request in seen],['/api/show']*3)
            self.assertTrue(updated.memory_enabled)
            self.assertEqual(updated.memory_max_notes,500)

    async def test_missing_store_and_ambiguous_config_preserve_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=root/'local.toml'
            original='model = "gpt-oss:20b"\n';config.write_text(original)
            with self.assertRaises(ValueError):await configure(config,model_store=root/'absent')
            self.assertEqual(config.read_text(),original)
            multiline='private_ollama_models = """\n/a/model/path\n"""\n';config.write_text(multiline)
            with self.assertRaises(ValueError):update_settings(config,{'private_ollama_models':'/other'})
            self.assertEqual(config.read_text(),multiline)

    async def test_followup_keeps_retrieved_answer_in_ram_without_durable_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            config=Config(memory_vault=directory+'/memory',context_tokens=4096)
            memory=MemoryStore(config);observed=[];messages=[]
            class Backend:
                async def respond_with_context(_,text,**values):
                    observed.append(values);return 'A terrier is an energetic dog.'
                extract_memories=AsyncMock()
                async def synthesize(_,text,output):output.write_bytes(wav_bytes())
            async def send(message):messages.append(message)
            session=Session(config,Backend(),send,asyncio.Lock(),memory=memory)
            source={'title':'Terrier source','excerpt':'Energetic dog','kind':'web'}
            try:
                with patch('april.session.retrieve',AsyncMock(return_value=[source])) as retrieval:
                    await session.handle({'type':'text','text':'What is a terrier?'})
                    await session.task
                    await session.cancel(invalidate_review=False)
                    await session.handle({'type':'text','text':'Tell me more'})
                    await session.task
                    retrieval.assert_awaited_once()
                self.assertIn('energetic dog',json.dumps(observed[-1]['context']))
                await session.cancel(invalidate_review=False)
                with patch('april.session.retrieve',side_effect=AssertionError('Social greeting went to web')):
                    await session.handle({'type':'text','text':'April, how are you doing?'})
                    await session.task
                Backend.extract_memories.assert_not_awaited()
                self.assertFalse(memory.list())
                self.assertTrue(any(m['type']=='memory_status' for m in messages))
            finally:
                await session.cancel();await memory.close()

    async def test_recent_context_expiry_and_conversation_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            config=Config(memory_vault=directory+'/memory',conversation_history_turns=12,conversation_context_turns=6,context_tokens=4096)
            memory=MemoryStore(config)
            for i in range(20):memory.completed('User turn '+str(i),'Reply '+str(i),object(),allow_extract=False)
            self.assertEqual(len(memory.history),12)
            self.assertEqual(len(memory.context('continue')['recent_turns']),6)
            memory.history_at=time.monotonic()-31*60
            self.assertIsNone(memory.context('continue'))
            self.assertTrue(local_conversation('How was your day?'))
            self.assertTrue(local_conversation("Let's talk"))
            self.assertTrue(local_conversation("Let's talk about Python"))
            self.assertTrue(local_conversation('I feel nervous about my interview.'))
            await memory.close()

    @unittest.skipUnless(importlib.util.find_spec('defusedxml'),'Optional calendar dependencies unavailable')
    async def test_idempotent_calendar_discovery_never_replaces_existing_collection(self):
        from april.calendar_setup import ensure_collection
        xml='<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav"><d:response><d:propstat><d:prop><d:resourcetype><c:calendar/></d:resourcetype></d:prop></d:propstat></d:response></d:multistatus>'
        with tempfile.TemporaryDirectory() as directory:
            credentials=Path(directory)/'credentials.json';credentials.write_text('{"username":"fixture","password":"fixture"}');credentials.chmod(0o600)
            config=Config(caldav_credentials=str(credentials))
            calls=[]
            def existing(request):calls.append(request.method);return httpx.Response(207,text=xml)
            self.assertFalse(await ensure_collection(config,transport=httpx.MockTransport(existing)))
            self.assertEqual(calls,['PROPFIND'])
            calls.clear()
            def missing(request):
                calls.append(request.method)
                return httpx.Response(404 if request.method=='PROPFIND' else 201)
            self.assertTrue(await ensure_collection(config,transport=httpx.MockTransport(missing)))
            self.assertEqual(calls,['PROPFIND','MKCALENDAR'])

    async def test_gmail_check_reads_only_profile_and_does_not_return_address(self):
        from april.gmail import check_gmail
        calls=[]
        def handler(request):
            calls.append(request.url.path)
            return httpx.Response(200,json={'emailAddress':'fixture@example.test','messagesTotal':42})
        self.assertIs(await check_gmail(Config(),credentials=SimpleNamespace(token='fixture'),transport=httpx.MockTransport(handler)),True)
        self.assertEqual(calls,['/gmail/v1/users/me/profile'])

    async def test_false_process_identity_cannot_stop_unrelated_process(self):
        from april import power
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);state=root/'state.json';state.write_text('{"pid":12345,"started":false}')
            with patch.object(power,'STATE',state),patch.object(power,'DISABLED',root/'disabled'), \
                 patch.object(power,'process_identity',return_value=False),patch.object(power.os,'kill') as kill:
                self.assertFalse(power.stop());kill.assert_not_called()

    @unittest.skipUnless(importlib.util.find_spec('passlib'),'Optional calendar dependencies unavailable')
    async def test_calendar_initialization_is_private_and_preserves_existing_files(self):
        from april.calendar_setup import initialize
        import os
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            config=Config(caldav_credentials=str(root/'private/caldav.json'),caldav_server_config=str(root/'private/radicale.ini'))
            with patch.dict(os.environ,{'HOME':str(root/'home')}):initialize(config)
            for path in [root/'private/caldav.json',root/'private/radicale.ini',root/'private/calendar-users']:
                self.assertEqual(path.stat().st_mode & 0o777,0o600)
            original=(root/'private/caldav.json').read_bytes()
            with self.assertRaises(ValueError):initialize(config)
            self.assertEqual((root/'private/caldav.json').read_bytes(),original)

    async def test_ordinary_statement_auto_saves_then_private_mode_cancels_recall(self):
        with tempfile.TemporaryDirectory() as directory:
            config=Config(memory_vault=directory+'/memory')
            memory=MemoryStore(config);messages=[]
            extraction=AsyncMock(return_value={'memories':[{'key':'study-routine','category':'preferences',
                'content':'Usually studies Python in the evenings.','evidence':'I usually study Python in the evenings',
                'certainty':'stated'}],'summary':True})
            class Backend:
                extract_memories=extraction
                async def respond_with_context(_,text,**values):return 'Happy to help with a small practice problem.'
                async def synthesize(_,text,output):output.write_bytes(wav_bytes())
            async def send(message):messages.append(message)
            session=Session(config,Backend(),send,asyncio.Lock(),memory=memory)
            async def ask(text):
                await session.handle({'type':'text','text':text});await session.task
                await session.cancel(invalidate_review=False)
            try:
                with patch('april.session.retrieve',side_effect=AssertionError('Personal statement went to web')):
                    await ask('I usually study Python in the evenings.')
                    if memory.tasks:await asyncio.gather(*memory.tasks)
                    self.assertTrue(any(i['id']=='study-routine' for i in memory.list()))
                    extraction.assert_awaited_once()
                    await ask("Don't remember this conversation")
                    self.assertEqual(memory.list(),[])
                    await ask('I usually study Python in the evenings.')
                    extraction.assert_awaited_once()
                    self.assertEqual(memory.history,[])
            finally:await session.cancel();await memory.close()
