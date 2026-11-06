"""Calendar-only natural questions and local-day read bounds; no personal calendar."""
import asyncio
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch

import httpx
from april.config import Config
from april.session import Session
from april.tools import is_calendar_read_request
from test_core import wav_bytes

AVAILABLE=bool(importlib.util.find_spec('icalendar') and importlib.util.find_spec('defusedxml'))

@unittest.skipUnless(AVAILABLE,'Optional calendar dependencies unavailable')
class CalendarRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_spoken_variations_read_calendar_without_mail_or_web(self):
        phrases=['What do I have planned for tomorrow?','What do I have planned tomorrow?',
                 'April, what is on my schedule for tomorrow?','Show my calendar for tomorrow.']
        source={'title':'April Test','excerpt':'2026-11-07 20:00:00+00:00','kind':'calendar',
                'start':'2026-11-07T20:00:00+00:00','end':'2026-11-07T20:15:00+00:00'}
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                messages=[]
                async def send(message):messages.append(message)
                async def synthesize(text,output):output.write_bytes(wav_bytes())
                backend=SimpleNamespace(respond=AsyncMock(side_effect=AssertionError('Calendar facts must not depend on the model')),
                                        synthesize=AsyncMock(side_effect=synthesize))
                session=Session(Config(),backend,send,asyncio.Lock())
                try:
                    with patch('april.calendar.events',AsyncMock(return_value=[source])) as calendar, \
                         patch('april.gmail.search_gmail',AsyncMock(side_effect=AssertionError('Unexpected Gmail query'))) as mail, \
                         patch('april.session.retrieve',AsyncMock(side_effect=AssertionError('Unexpected web search'))) as web:
                        await session.handle({'type':'text','text':phrase});await session.task
                        calendar.assert_awaited_once_with(session.config,period='tomorrow')
                        mail.assert_not_awaited();web.assert_not_awaited()
                        backend.respond.assert_not_awaited()
                        reply=next(message for message in messages if message['type']=='reply')
                        self.assertIn('April Test',reply['text'])
                        self.assertIn('3:00 PM to 3:15 PM EST',reply['text'])
                        self.assertEqual(reply['source'],'calendar')
                        self.assertEqual(backend.synthesize.await_args.args[0],reply['text'])
                        timings=next(message['values'] for message in messages if message['type']=='timings')
                        self.assertNotIn('llm_ms',timings)
                        self.assertTrue(any(message['type']=='sources' and message['sources']==[source] for message in messages))
                finally:await session.cancel()
        self.assertFalse(is_calendar_read_request('Search my files for what do I have planned tomorrow'))
        self.assertFalse(is_calendar_read_request('Tell me how calendar software works'))

    async def test_tomorrow_report_uses_local_midnights_including_dst(self):
        from april.calendar import events
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'credentials.json';path.write_text('{"username":"fixture","password":"fixture"}');path.chmod(0o600)
            config=Config(caldav_credentials=str(path),timezone='America/New_York')
            cases=[(datetime(2026,11,6,12,tzinfo=timezone.utc),'20261107T050000Z','20261108T050000Z'),
                   (datetime(2026,3,7,12,tzinfo=timezone.utc),'20260308T050000Z','20260309T040000Z')]
            for now,start,end in cases:
                bodies=[]
                def handler(request):
                    bodies.append(request.content.decode())
                    return httpx.Response(207,text='<d:multistatus xmlns:d="DAV:"/>')
                self.assertEqual(await events(config,period='tomorrow',now=now,transport=httpx.MockTransport(handler)),[])
                self.assertIn('start="'+start+'" end="'+end+'"',bodies[0])

    def test_readback_handles_empty_all_day_overnight_and_long_lists(self):
        from april.calendar import readback
        from dataclasses import replace
        config=Config(timezone='America/New_York')
        self.assertEqual(readback(config,[],period='tomorrow'),'No calendar events were returned for tomorrow.')
        all_day={'title':'Study day','start':'2026-11-07','end':'2026-11-08'}
        self.assertIn('all day on Saturday, November 7',readback(config,[all_day],period='tomorrow'))
        overnight={'title':'Overnight','start':'2026-11-07T04:00:00+00:00','end':'2026-11-07T06:00:00+00:00'}
        text=readback(config,[overnight],period='tomorrow')
        self.assertIn('Friday, November 6',text)
        self.assertIn('Saturday, November 7',text)
        long=[{'title':'Long event title '+str(i)+' X'*45,'start':'2026-11-07T20:00:00+00:00','end':'2026-11-07T20:15:00+00:00'} for i in range(20)]
        text=readback(config,long,period='tomorrow')
        self.assertLessEqual(len(text),config.max_response_chars)
        self.assertIn('more returned events',text)
        self.assertLessEqual(len(readback(replace(config,max_response_chars=40),long)),40)
