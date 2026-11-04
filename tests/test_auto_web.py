"""Routing fixtures: no actual search engines, private accounts or models."""
import asyncio
import base64
import unittest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

from april.config import Config
from april.errors import BackendError
from april.knowledge import route_knowledge
from april.session import Session
from test_core import wav_bytes


class AutomaticSearchTests(unittest.IsolatedAsyncioTestCase):
    async def run_turn(self, text, *, sources=None, failure=None, audio=False, **settings):
        messages = []
        async def send(message):
            messages.append(message)
        async def synthesize(reply, output):
            output.write_bytes(wav_bytes())
        backend = SimpleNamespace(respond=AsyncMock(return_value='Fixture answer [1].'),
                                  synthesize=synthesize, transcribe=AsyncMock(return_value=text))
        session = Session(Config(**settings), backend, send, asyncio.Lock())
        retrieval = AsyncMock(side_effect=failure, return_value=sources or [])
        try:
            with patch('april.session.retrieve', retrieval):
                if audio:
                    await session.handle({'type':'record'})
                    await session.handle({'type':'audio', 'audio':base64.b64encode(wav_bytes()).decode()})
                else:
                    await session.handle({'type':'text', 'text':text})
                job = session.task
                await job
            return messages, backend, retrieval
        finally:
            await session.cancel()

    async def test_normal_question_automatically_retrieves_before_model(self):
        source = {'title':'Fixture', 'excerpt':'A game', 'kind':'web'}
        events, backend, retrieval = await self.run_turn(
            'April, what is League of Legends?', sources=[source])
        retrieval.assert_awaited_once_with(unittest.mock.ANY, 'web', 'what is league of legends')
        backend.respond.assert_awaited_once_with(
            'April, what is League of Legends?', sources=[source])
        self.assertIn('searching', [e.get('state') for e in events if e['type']=='lookup'])
        self.assertTrue(any(e['type']=='sources' for e in events))

    async def test_failed_and_empty_search_never_fall_back_to_model(self):
        for failure in [None, BackendError('searxng_unavailable','Fixture unavailable')]:
            events, backend, retrieval = await self.run_turn('What is a terrier?', failure=failure)
            retrieval.assert_awaited_once()
            backend.respond.assert_not_awaited()
            if failure:
                self.assertTrue(any(e.get('code')=='searxng_unavailable' for e in events))
            else:
                timing = next(e['values'] for e in events if e['type']=='timings')
                self.assertNotIn('llm_ms', timing)

    async def test_clock_and_private_requests_never_automatically_search(self):
        for text in ['What time is it?', 'What is in my emails?', 'Read ~/Documents/aprilfiles/test.txt',
                     'Summarize mail for enrique@example.org']:
            events, backend, retrieval = await self.run_turn(text)
            retrieval.assert_not_awaited()
            if text=='What time is it?':
                backend.respond.assert_not_awaited()
                self.assertTrue(any(e.get('source')=='current_time' for e in events))

    async def test_manual_and_simulation_modes_do_not_auto_search(self):
        for settings in [{'automatic_web_search':False}, {'mode':'simulation'}]:
            _, backend, retrieval = await self.run_turn('What is a terrier?', **settings)
            retrieval.assert_not_awaited()
            backend.respond.assert_awaited_once()

    def test_explicit_alias_and_private_tool_priority(self):
        self.assertEqual(route_knowledge(
            'April, check on the internet. What is League of Legends?')[0], 'web')
        for text, kind in [('Search my files for collar','documents'),
                           ('Search my emails for invoice','gmail')]:
            self.assertEqual(route_knowledge(text, automatic_web_search=True)[0], kind)


    async def test_transcribed_audio_uses_same_automatic_search_path(self):
        source = {'title':'Fixture', 'excerpt':'A game', 'kind':'web'}
        events, backend, retrieval = await self.run_turn('What is a terrier?', audio=True, sources=[source])
        backend.transcribe.assert_awaited_once()
        retrieval.assert_awaited_once_with(unittest.mock.ANY, 'web', 'what is a terrier')
        self.assertTrue(any(e['type']=='transcript' and e['text']=='What is a terrier?' for e in events))
