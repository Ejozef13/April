"""Temporary-folder and API fixtures; no real files, search account or mailbox accessed."""
import base64
import json
import os
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from april.config import Config
from april.documents import build_index,search_documents
from april.errors import BackendError
from april.gmail import SCOPES,message_excerpt,save_credentials,search_gmail,google_endpoint
from april.integrations import configure_documents
from april.knowledge import route_knowledge


class DocumentTests(unittest.TestCase):
    def test_only_approved_text_is_indexed_and_scope_changes_require_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);approved=root/'aprilfiles';approved.mkdir()
            (approved/'project.md').write_text('APRIL uses a purple collar. The mascot is a terrier.')
            (approved/'.env').write_text('SECRET_MARKER')
            (approved/'credentials.txt').write_text('SECRET_MARKER')
            (approved/'ordinary.json').write_text('{"client_secret":"SECRET_MARKER"}')
            outside=root/'outside.txt';outside.write_text('OUTSIDE_MARKER')
            (approved/'linked.txt').symlink_to(outside)
            (approved/'binary.txt').write_bytes(b'\x00BINARY_MARKER')
            config=Config(document_roots=[str(approved)],documents_index_path=str(root/'index.sqlite3'))
            counts=build_index(config)
            self.assertEqual(counts['files'],1)
            sources=search_documents(config,'purple collar')
            self.assertEqual(len(sources),1)
            self.assertIn('project.md',sources[0]['title'])
            self.assertFalse(search_documents(config,'SECRET_MARKER OUTSIDE_MARKER BINARY_MARKER'))
            self.assertEqual(os.stat(config.documents_index_path).st_mode & 0o777,0o600)
            build_index(config) # Repeatable replacement, not duplicate chunks.
            self.assertEqual(len(search_documents(config,'purple')),1)
            other=root/'other';other.mkdir()
            with self.assertRaises(BackendError):
                search_documents(replace(config,document_roots=[str(other)]),'purple')
            with self.assertRaises(BackendError):
                search_documents(replace(config,document_roots=[]),'purple')

    def test_sqlite_query_syntax_is_not_executed_and_unknown_database_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);folder=root/'files';folder.mkdir()
            (folder/'notes.txt').write_text('Remember the purple collar')
            target=root/'index.sqlite3'
            with sqlite3.connect(target) as db:db.execute('CREATE TABLE unrelated(value TEXT)')
            original=target.read_bytes()
            config=Config(document_roots=[str(folder)],documents_index_path=str(target))
            with self.assertRaises(BackendError):build_index(config)
            self.assertEqual(target.read_bytes(),original)
            config=replace(config,documents_index_path=str(root/'new.sqlite3'))
            build_index(config)
            search_documents(config,'"; DROP TABLE chunks; -- purple')
            self.assertTrue(search_documents(config,'purple'))

    def test_document_configuration_preserves_existing_settings_and_will_not_broaden(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=root/'settings.toml';config.write_text('model = "existing"\n')
            self.assertTrue(configure_documents(config,root/'aprilfiles'))
            content=config.read_text()
            self.assertIn('model = "existing"',content)
            self.assertFalse(configure_documents(config,root/'aprilfiles'))
            with self.assertRaises(ValueError):configure_documents(config,root/'other')
            self.assertEqual(config.read_text(),content)


class RetrievalTests(unittest.IsolatedAsyncioTestCase):
    async def test_simulation_cannot_access_real_retrieval(self):
        import asyncio
        from unittest.mock import AsyncMock
        from april.session import Session
        from april.backends import SimulationBackends
        messages=[]
        async def send(message):messages.append(message)
        session=Session(Config(mode='simulation'),SimulationBackends(),send,asyncio.Lock())
        with patch('april.session.retrieve',AsyncMock(side_effect=AssertionError('Must not retrieve in simulation'))):
            await session.handle({'type':'web','text':'news'})
            await session.task
        self.assertEqual(messages[-1]['code'],'simulation_search_disabled')
        await session.cancel()

    async def test_fresh_fact_router_and_private_intents(self):
        self.assertEqual(route_knowledge('April, who is the current president?')[0],'web')
        self.assertEqual(route_knowledge('search my files for current president')[0],'documents')
        self.assertEqual(route_knowledge('search my emails for invoice')[0],'gmail')
        self.assertIsNone(route_knowledge('Who is the president mentioned in my emails?')[0])

    async def test_gmail_performs_only_bounded_read_requests_and_preserves_no_auth(self):
        observed=[]
        encoded=base64.urlsafe_b64encode(b'The meeting is at noon.').decode()
        def handler(request):
            observed.append((request.method,request.url.path))
            self.assertEqual(request.url.host,'gmail.googleapis.com')
            self.assertEqual(request.headers['Authorization'],'Bearer fixture-token')
            if request.url.path.endswith('/messages'):
                return httpx.Response(200,json={'messages':[{'id':'abc123'}]})
            return httpx.Response(200,json={'payload':{'mimeType':'text/plain','body':{'data':encoded},
                'headers':[{'name':'Subject','value':'Meeting'}]}})
        result=await search_gmail(Config(),'meeting',credentials=SimpleNamespace(token='fixture-token'),transport=httpx.MockTransport(handler))
        self.assertEqual(len(observed),2)
        self.assertTrue(all(method=='GET' for method,path in observed))
        self.assertIn('noon',result[0]['excerpt'])
        self.assertNotIn('fixture-token',json.dumps(result))


class GmailCredentialTests(unittest.TestCase):
    def test_google_credentials_never_refresh_against_other_origins(self):
        allowed={'oauth2.googleapis.com','accounts.google.com'}
        self.assertTrue(google_endpoint('https://oauth2.googleapis.com/token',allowed))
        for url in ['http://oauth2.googleapis.com/token','https://evil.example/token',
                    'https://oauth2.googleapis.com.evil.example/token','https://user@oauth2.googleapis.com/token',
                    'https://oauth2.googleapis.com/token?redirect=elsewhere']:
            self.assertFalse(google_endpoint(url,allowed))
        self.assertFalse(google_endpoint('https://accounts.google.com/redirect',allowed,{'/token','/o/oauth2/token'}))
    def test_private_token_file_and_scope_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'token.json'
            credentials=SimpleNamespace(scopes=SCOPES,granted_scopes=SCOPES,to_json=lambda:'{"fixture":true}')
            save_credentials(path,credentials)
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            bad=SimpleNamespace(scopes=SCOPES+['https://www.googleapis.com/auth/gmail.send'],granted_scopes=None)
            with self.assertRaises(BackendError):save_credentials(path,bad)
            self.assertEqual(path.read_text(),'{"fixture":true}')

    def test_attachments_not_read(self):
        data=base64.urlsafe_b64encode(b'attachment contents').decode()
        self.assertEqual(message_excerpt({'mimeType':'text/plain','filename':'attachment.txt','body':{'data':data}}),'')
