"""Provider boundaries and private settings; no public search engine required."""
import json
import os
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs

import httpx

from april.config import Config
from april.errors import BackendError
from april.integrations import configure_search
from april.knowledge import search_web
from april.searxng_service import initialize


class SearxngTests(unittest.IsolatedAsyncioTestCase):
    async def test_local_post_json_without_forwarding_credentials(self):
        observed=[]
        def handler(request):
            observed.append(request)
            self.assertEqual(request.method,'POST')
            self.assertEqual(request.url.host,'127.0.0.1')
            self.assertEqual(request.url.path,'/search')
            fields=parse_qs(request.content.decode())
            self.assertEqual(fields['format'],['json'])
            self.assertEqual(fields['q'],['Linux kernel'])
            self.assertNotIn('X-Subscription-Token',request.headers)
            self.assertNotIn('Authorization',request.headers)
            return httpx.Response(200,json={'results':[
                {'title':'<b>Kernel</b>','content':'Official kernel &amp; source','url':'https://kernel.org','publishedDate':'2026-11-04'},
                {'title':'Bad','content':'ignore','url':'javascript:alert(1)'},
                {'title':'Docs','content':'<p>Reference text</p>','url':'https://docs.kernel.org'},
                {'title':'Source','content':'Repository','url':'https://git.kernel.org'},
                {'title':'Beyond limit','content':'unused','url':'https://example.org'}]})
        with patch.dict(os.environ,{'HTTP_PROXY':'http://unused.invalid:8080'}):
            results=await search_web(Config(),'Linux kernel',transport=httpx.MockTransport(handler))
        self.assertEqual(len(observed),1)
        self.assertEqual(len(results),3)
        self.assertTrue(all(s['provider']=='searxng' for s in results))
        self.assertEqual(results[0]['provider_date'],'2026-11-04')
        self.assertEqual(results[0]['excerpt'],'Official kernel & source')
        self.assertNotIn('unused.invalid',json.dumps(results))

    async def test_disabled_json_and_engine_failures_do_not_fall_back(self):
        for response,code in [
            (httpx.Response(403), 'searxng_json_disabled'),
            (httpx.Response(200,json={'results':[],'unresponsive_engines':[['bing','timeout']]}),'searxng_engines_unavailable')]:
            calls=[]
            def handler(request):calls.append(request.url.host);return response
            with patch.dict(os.environ,{'HTTP_PROXY':'http://unused.invalid:8080'}):
                with self.assertRaises(BackendError) as error:
                    await search_web(Config(),'query',transport=httpx.MockTransport(handler))
            self.assertEqual(error.exception.code,code)
            self.assertEqual(calls,['127.0.0.1'])

    async def test_unavailable_service_has_specific_repair(self):
        def offline(request):raise httpx.ConnectError('fixture private body',request=request)
        with self.assertRaises(BackendError) as error:
            await search_web(Config(),'query',transport=httpx.MockTransport(offline))
        self.assertEqual(error.exception.code,'searxng_unavailable')
        self.assertIn('scripts/searxng.sh up',str(error.exception))
        self.assertNotIn('private body',str(error.exception))


class ProviderConfigurationTests(unittest.TestCase):
    def test_search_url_update_preserves_model_folders_and_gmail_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'local.toml'
            path.write_text('model = "gpt-oss:20b"\ndocument_roots = ["/approved"]\ngmail_token_path = "/private/token.json"\n')
            configure_search(path,'http://127.0.0.1:8889')
            final=tomllib.loads(path.read_text())
            self.assertEqual(final['web_provider'],'searxng')
            self.assertEqual(final['searxng_url'],'http://127.0.0.1:8889')
            self.assertEqual(final['model'],'gpt-oss:20b')
            self.assertEqual(final['document_roots'],['/approved'])
            self.assertEqual(final['gmail_token_path'],'/private/token.json')
            before=path.read_text()
            with self.assertRaises(ValueError):configure_search(path,'http://0.0.0.0:8888')
            self.assertEqual(path.read_text(),before)

    def test_service_init_preserves_settings_and_secret_is_not_shared(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'search'
            url=initialize(root)
            self.assertEqual(url,'http://127.0.0.1:8888')
            settings=root/'config/settings.yml'
            first=settings.read_text()
            self.assertIn('formats: [html, json]',first)
            self.assertNotIn('ultrasecretkey',first)
            self.assertEqual(settings.stat().st_mode&0o777,0o600)
            settings.write_text(first+'\n# user customization\n')
            initialize(root)
            self.assertEqual(settings.read_text(),first+'\n# user customization\n')

    def test_remote_unauthenticated_search_url_is_rejected(self):
        for url in ['http://192.168.1.5:8888','http://user:password@localhost:8888',
                    'http://localhost:8888/?key=secret','http://localhost:8888/path']:
            with self.assertRaises(ValueError):Config(searxng_url=url)
