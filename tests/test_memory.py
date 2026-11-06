"""Real private Markdown/SQLite and session lifecycle, deterministic model fixtures."""
import asyncio
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from april.config import Config
from april.memory import MemoryStore, PERSONALITY
from april.session import Session
from test_core import wav_bytes


class MemoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config=Config(memory_vault=self.tmp.name+'/vault',automatic_web_search=True)
        self.store=MemoryStore(self.config)

    async def asyncTearDown(self):
        await self.store.close()

    async def test_markdown_edit_reindex_delete_and_private_modes(self):
        item=self.store.save('I prefer hints before full solutions.',category='preferences')
        path=self.store.root/'preferences'/(item['id']+'.md')
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertEqual(self.store.root.stat().st_mode & 0o777,0o700)
        path.write_text(path.read_text().replace('hints before full solutions','concise examples'))
        self.assertIn('concise examples',self.store.context('coding')['memories'][0]['content'])
        self.assertEqual(len(MemoryStore(self.config).list()),1)
        path.unlink()
        self.assertEqual(self.store.list(),[])
        with sqlite3.connect(self.store.root/'.index.sqlite3') as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM memories').fetchone()[0],0)
        self.assertFalse(MemoryStore(Config(mode='simulation',memory_vault=self.tmp.name+'/sim')).enabled)
        self.assertFalse((Path(self.tmp.name)/'sim').exists())

    async def test_credentials_traversal_and_symlink_rejected(self):
        for text in ['my password is hunter2','api_key = abc','Bearer abc','123-45-6789']:
            with self.assertRaises(ValueError):self.store.save(text)
        with self.assertRaises(ValueError):self.store.save('A normal note',key='../escape')
        outside=Path(self.tmp.name)/'outside';outside.mkdir()
        self.store._prepare()
        (self.store.root/'projects').rmdir()
        (self.store.root/'projects').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(ValueError):self.store.save('A project note',category='projects')
        self.assertEqual(list(outside.iterdir()),[])
        unsafe=MemoryStore(Config(memory_vault=str(Path.cwd()/'private-memory-test')))
        with self.assertRaises(ValueError):unsafe.list()

    async def test_supported_extraction_pending_inference_and_no_assistant_fact(self):
        class Backend:
            async def extract_memories(_,text):
                return {'memories':[
                    {'key':'coding-style','category':'preferences','content':'Prefers coding hints.','evidence':'I prefer hints','certainty':'stated'},
                    {'key':'inference','category':'profile','content':'May enjoy puzzles.','evidence':'I prefer hints','certainty':'inferred'},
                    {'key':'hallucination','category':'profile','content':'Lives on Mars.','evidence':'I live on Mars','certainty':'stated'}], 'summary':True}
        self.store.completed('I prefer hints when coding.','Okay.',Backend(),conversation_id='one')
        await asyncio.gather(*self.store.tasks)
        items=self.store.list()
        self.assertEqual({i['id'] for i in items},{'coding-style','pending-inference','recent-context'})
        context=self.store.context('hints')
        self.assertNotIn('May enjoy puzzles',json.dumps(context))
        self.assertEqual(next(i for i in items if i['id']=='coding-style')['conversation_id'],'one')
        self.assertNotIn('Okay.', '\n'.join(p.read_text() for p in self.store.root.rglob('*.md')))

    async def test_forget_cancels_inflight_extraction_and_removes_index_and_history(self):
        started=asyncio.Event()
        class Backend:
            async def extract_memories(_,text):
                started.set();await asyncio.sleep(30)
        self.store.save('I prefer hints.',key='coding-style')
        self.store.completed('I prefer hints.', 'Okay.',Backend())
        tasks=list(self.store.tasks)
        await started.wait()
        self.assertEqual(self.store.forget('coding-style'),1)
        await asyncio.gather(*tasks,return_exceptions=True)
        self.assertEqual(self.store.list(),[])
        self.assertEqual(self.store.history,[])

    async def test_explicit_notes_protected_and_topic_update_deduplicated(self):
        self.store.save('I prefer tea.',key='drink',origin='conversation')
        self.store.save('I prefer coffee.',key='drink',origin='conversation')
        self.assertEqual(len(self.store.list()),1)
        self.store.save('I prefer water.',key='drink')
        self.store.save('I prefer coffee.',key='drink',origin='conversation')
        self.assertEqual(self.store.list()[0]['content'],'I prefer water.')
        self.store.save('I prefer water.')
        self.assertEqual(len(self.store.list()),1)

    async def test_opt_in_daily_and_due_notifications_once_across_restart(self):
        config=Config(memory_vault=self.config.memory_vault,proactive_briefings=True)
        store=MemoryStore(config)
        now=datetime(2026,11,5,15,tzinfo=timezone.utc)
        store.save('Review internship application.',category='projects',due_at=(now-timedelta(minutes=1)).isoformat())
        self.assertEqual(len(self.store.notifications(now)),1)
        notices=store.notifications(now)
        self.assertEqual(len(notices),2)
        for notice in notices:store.delivered(notice['id'])
        self.assertEqual(MemoryStore(config).notifications(now),[])
        with self.assertRaises(ValueError):store.save('A reminder',due_at='2026-11-05T10:00')

    async def test_context_bounded_no_pending_and_deleted_note_not_recalled(self):
        for i in range(20):self.store.save('Coding preference '+str(i)+' '+'short hints '*15)
        self.store.save('Unconfirmed private guess',category='pending')
        context=self.store.context('coding')
        self.assertLess(len(json.dumps(context)),self.config.context_tokens*3//2+100)
        self.assertNotIn('Unconfirmed',json.dumps(context))
        self.store.history=[{'user':'What did I just ask?','assistant':'An earlier answer.'}]
        self.assertIn('What did I just ask?',json.dumps(self.store.context('coding')))
        self.store.clear()
        self.assertIsNone(self.store.context('coding'))

    async def test_session_commands_private_mode_and_context_never_go_to_web(self):
        observed=[];messages=[]
        class Backend:
            async def respond_with_context(_,text,**kwargs):
                observed.append(kwargs);return 'A cheerful fixture answer.'
            async def synthesize(_,text,output):output.write_bytes(wav_bytes())
        async def send(message):messages.append(message)
        session=Session(self.config,Backend(),send,asyncio.Lock(),memory=self.store)
        async def ask(text):
            await session.handle({'type':'text','text':text})
            task=session.task
            await task
            await session.cancel(invalidate_review=False)
        with patch('april.session.retrieve',side_effect=AssertionError('Personal memory must not go to web')):
            await ask('April, remember this: I prefer coding hints.')
            self.assertEqual(len(self.store.list()),1)
            await ask('What do you remember about me?')
            self.assertTrue(any(m['type']=='memory_view' for m in messages))
            await ask('I like coding.')
            self.assertIn('I prefer coding hints.',json.dumps(observed[-1]))
            await ask("Don't remember this conversation")
            self.assertEqual(self.store.list(),[])
            await ask('I like puzzles.')
            self.assertIsNone(observed[-1]['context'])
            self.assertEqual(self.store.history,[])
            await ask('Start a new conversation')
            self.assertFalse(session.private_conversation)
            await ask('Remind me in 20 minutes to review an application')
            reminder=self.store.list()[0]
            self.assertTrue(reminder['due_at'])
            self.assertIn('review an application',reminder['content'])
            self.store.save('Parser prototype is ready.',category='projects',key='audino-status')
            await ask('What do you know about my Audino project?')
            self.assertIn('Parser prototype',json.dumps(observed[-1]['context']))
        await session.cancel()

    async def test_retrieved_content_not_extracted_and_failure_is_visible(self):
        class Backend:
            async def extract_memories(_,text):raise ValueError('fixture failure')
        self.store.completed('I like tea.','Okay.',Backend(),allow_extract=False)
        self.assertFalse(self.store.tasks)
        self.store.completed('I like tea.','Okay.',Backend())
        await asyncio.gather(*self.store.tasks)
        self.assertIn('did not complete',self.store.notice)
        self.assertEqual(self.store.list(),[])

    async def test_personality_honest_loyal_and_local_only_model_boundary(self):
        self.assertIn('female Jack Russell',PERSONALITY)
        self.assertIn('honest',PERSONALITY)
        from april.backends import LocalBackends
        import httpx
        payloads=[]
        async def handler(request):
            payloads.append(json.loads(request.content))
            if payloads[-1].get('format')=='json':
                return httpx.Response(200,json={'message':{'content':'{"memories":[],"summary":false}'}})
            return httpx.Response(200,text=json.dumps({'message':{'content':'Hello!'}})+'\n')
        original=httpx.AsyncClient
        with patch('april.backends.httpx.AsyncClient',side_effect=lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs)):
            backend=LocalBackends(self.config)
            await backend.respond_with_context('Hello',context={'memories':[{'content':'Likes Python.'}]})
            await backend.extract_memories('I like Python.')
        self.assertIn('UNTRUSTED_PERSONAL_CONTEXT_JSON',payloads[0]['messages'][1]['content'])
        self.assertEqual(payloads[1]['format'],'json')
        self.assertNotIn('Hello!',json.dumps(payloads[1]))

    async def test_project_export_is_scoped_private_and_never_overwrites(self):
        self.store.save('Audino status: parser prototype.',category='projects',key='audino-status')
        self.store.save('April status: memory preview.',category='projects',key='april-status')
        self.store.save('I prefer short answers.',category='preferences')
        output=Path(self.tmp.name)/'audino-context.md'
        self.store.export_project('audino',output)
        text=output.read_text()
        self.assertIn('Audino status',text)
        self.assertNotIn('April status',text)
        self.assertNotIn('short answers',text)
        self.assertEqual(output.stat().st_mode & 0o777,0o600)
        with self.assertRaises(FileExistsError):self.store.export_project('audino',output)
        with self.assertRaises(ValueError):self.store.export_project('../profile',Path(self.tmp.name)/'other.md')
        with self.assertRaises(ValueError):self.store.export_project('audino',Path.cwd()/'context.md')

    async def test_simultaneous_agents_use_versions_and_preserve_other_notes(self):
        import subprocess
        import sys
        code='''import sys
from april.config import Config
from april.memory import MemoryStore
s=MemoryStore(Config(memory_vault=sys.argv[1]))
s.save('Independent agent note '+sys.argv[2],category='projects',key='agent-'+sys.argv[2])
try:
 s.save('Competing status '+sys.argv[2],category='projects',key='audino-status',expected_version='new')
except ValueError:
 sys.exit(3)
'''
        processes=[subprocess.Popen([sys.executable,'-c',code,str(self.store.root),str(i)],
                                    stdout=subprocess.PIPE,stderr=subprocess.PIPE) for i in range(5)]
        results=[]
        for process in processes:
            _,stderr=process.communicate(timeout=10)
            self.assertFalse(stderr,stderr.decode())
            results.append(process.returncode)
        self.assertEqual(results.count(0),1)
        self.assertEqual(results.count(3),4)
        items=self.store.list()
        self.assertEqual(len(items),6)
        old=next(i for i in items if i['id']=='audino-status')
        changed=self.store.save('Reviewed new status',category='projects',key='audino-status',expected_version=old['updated_at'])
        self.assertEqual(changed['content'],'Reviewed new status')
        with self.assertRaises(ValueError):
            self.store.save('Stale write',category='projects',key='audino-status',expected_version=old['updated_at'])
