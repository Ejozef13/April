"""Safe Gmail failure classifications; no real account or network used."""
import asyncio
from contextlib import redirect_stderr
from datetime import datetime,timedelta,timezone
import importlib.util
import io
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch

import httpx
from april.config import Config
from april.errors import BackendError
from april.gmail import check_gmail,credentials_for,main,save_credentials,SCOPES


class GmailDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_google_failures_are_classified_without_echoing_response_data(self):
        cases=[(403,'accessNotConfigured','gmail_api_disabled'),
               (403,'SERVICE_DISABLED','gmail_api_disabled'),
               (403,'insufficientPermissions','gmail_scope_rejected'),
               (401,'authError','gmail_token_rejected'),
               (429,'rateLimitExceeded','gmail_rate_limited'),
               (503,'backendError','gmail_service_unavailable'),
               (403,'unknown-private-reason','gmail_access_denied')]
        for status,reason,code in cases:
            with self.subTest(code=code,reason=reason):
                def handler(request):
                    return httpx.Response(status,json={'error':{'message':'PRIVATE_RESPONSE_BODY_MARKER',
                        'errors':[{'reason':reason}],'details':[{'reason':reason}]}})
                with self.assertRaises(BackendError) as caught:
                    await check_gmail(Config(),credentials=SimpleNamespace(token='PRIVATE_TOKEN_MARKER'),
                                      transport=httpx.MockTransport(handler))
                self.assertEqual(caught.exception.code,code)
                self.assertNotIn('PRIVATE_',str(caught.exception))
                self.assertNotIn(reason,str(caught.exception))

    async def test_transport_failure_does_not_claim_consent_is_missing(self):
        for error,code in [(httpx.ConnectError,'gmail_network_failed'),(httpx.ReadTimeout,'gmail_network_timeout')]:
            def handler(request):raise error('PRIVATE_NETWORK_DETAIL',request=request)
            with self.assertRaises(BackendError) as caught:
                await check_gmail(Config(),credentials=SimpleNamespace(token='fixture'),transport=httpx.MockTransport(handler))
            self.assertEqual(caught.exception.code,code)
            self.assertNotIn('PRIVATE_',str(caught.exception))

    @unittest.skipUnless(importlib.util.find_spec('google') and importlib.util.find_spec('google.oauth2'),'Optional Google library unavailable')
    async def test_successful_credentials_roundtrip_needs_no_additional_scope(self):
        from google.oauth2.credentials import Credentials
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'grant.json'
            credentials=Credentials(token='fixture-access',refresh_token='fixture-refresh',
                token_uri='https://oauth2.googleapis.com/token',client_id='fixture-client',client_secret='fixture-secret',
                scopes=SCOPES,expiry=datetime.now(timezone.utc).replace(tzinfo=None)+timedelta(hours=1))
            save_credentials(path,credentials)
            restored=credentials_for(Config(gmail_token_path=str(path)))
            self.assertTrue(restored.valid)
            self.assertEqual(set(restored.scopes),set(SCOPES))
            self.assertEqual(path.stat().st_mode & 0o777,0o600)


class GmailDiagnosticCliTests(unittest.TestCase):
    def test_cli_preserves_the_safe_failure_reason_instead_of_blaming_consent(self):
        output=io.StringIO()
        failure=BackendError('gmail_api_disabled','Enable Gmail API in the client project.')
        with patch('sys.argv',['gmail','check']),patch('april.gmail.check_gmail',AsyncMock(side_effect=failure)),redirect_stderr(output):
            with self.assertRaises(SystemExit) as caught:main()
        self.assertEqual(caught.exception.code,1)
        self.assertIn('[gmail_api_disabled]',output.getvalue())
        self.assertNotIn('Complete local Google consent',output.getvalue())
