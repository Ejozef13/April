"""Exercise real adapter boundaries with local protocol/process fixtures.

These are integration checks of our code, not real pretrained model inference.
"""
import asyncio
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from april.backends import LocalBackends
from april.config import Config
from april.session import Session
from april.state import State
from test_core import wav_bytes


class BackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_http_stream_contract_and_character_bound(self):
        observed = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                observed.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-ndjson')
                self.end_headers()
                self.wfile.write((json.dumps({'message':{'thinking':'Private fixture reasoning','content':''},'done':False})+'\n').encode())
                self.wfile.write((json.dumps({'message':{'content':'Useful response. '*20},'done':True})+'\n').encode())
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            backend = LocalBackends(Config(ollama_url=f'http://127.0.0.1:{server.server_port}', max_response_chars=80))
            reply = await backend.respond('Help me')
            self.assertEqual(len(reply), 80)
            path, body = observed[0]
            self.assertEqual(path, '/api/chat')
            self.assertTrue(body['stream'])
            self.assertEqual(body['options']['num_predict'], 120)
            self.assertNotIn('think', body)
            self.assertNotIn('Private fixture', reply)
            self.assertNotIn('tools', body)
            self.assertNotIn('keep_alive', body) # Never force-unload a shared model.
            gpt = LocalBackends(Config(
                ollama_url=f'http://127.0.0.1:{server.server_port}',
                model='gpt-oss:20b', reasoning_effort='low',
                context_tokens=4096, max_response_tokens=512))
            final = await gpt.respond('Hello')
            gpt_body = observed[1][1]
            self.assertEqual(gpt_body['think'], 'low')
            self.assertEqual(gpt_body['options'], {'num_predict':512,'num_ctx':4096})
            self.assertTrue(final.startswith('Useful response.'))
            self.assertNotIn('Private fixture', final)
            await gpt.respond('What does this source say?',sources=[{
                'title':'Approved source','excerpt':'PRIVATE_REFERENCE_FIXTURE: April wears purple.',
                'kind':'document','url':None}])
            grounded=observed[2][1]
            self.assertIn('untrusted data',grounded['messages'][0]['content'])
            self.assertIn('PRIVATE_REFERENCE_FIXTURE',grounded['messages'][1]['content'])
            self.assertEqual(grounded['messages'][2]['content'],'What does this source say?')
        finally:
            await asyncio.to_thread(server.shutdown)
            server.server_close()
            thread.join()

    async def test_speech_cli_file_and_stdin_contracts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stt = root / 'fake-whisper'
            stt.write_text('#!/usr/bin/env python3\nimport pathlib,sys\na=sys.argv; pathlib.Path(a[a.index("-of")+1]+".txt").write_text("Hello April")\n')
            tts = root / 'fake-piper'
            tts.write_text('#!/usr/bin/env python3\nimport pathlib,sys,wave\na=sys.argv; text=sys.stdin.read(); assert text=="Hello Enrique"\nw=wave.open(a[a.index("--output_file")+1],"wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(22050); w.writeframes(b"\\0\\0"*2205); w.close()\n')
            stt.chmod(0o700)
            tts.chmod(0o700)
            source = root / 'input.wav'
            source.write_bytes(wav_bytes())
            backend = LocalBackends(Config(whisper_cli=str(stt),piper_cli=str(tts)))
            self.assertEqual(await backend.transcribe(source), 'Hello April')
            output = root / 'response.wav'
            await backend.synthesize('Hello Enrique', output)
            self.assertTrue(output.read_bytes().startswith(b'RIFF'))

    async def test_speaking_only_after_playback_ack_and_played_releases_job(self):
        messages = []
        async def send(message):
            messages.append(message)
        class Backend:
            async def respond(self,text):
                return 'A fixture response'
            async def synthesize(self,text,output):
                output.write_bytes(wav_bytes())
        gate = asyncio.Lock()
        session = Session(Config(),Backend(),send,gate)
        try:
            await session.handle({'type':'text','text':'hello'})
            job = session.task
            await job
            self.assertEqual(session.machine.state, State.THINKING)
            self.assertTrue(any(m['type']=='audio' for m in messages))
            self.assertTrue(gate.locked())
            await session.playback_started()
            self.assertEqual(session.machine.state, State.SPEAKING)
            await session.handle({'type':'played'})
            self.assertEqual(session.machine.state, State.IDLE)
            self.assertFalse(gate.locked())
        finally:
            await session.cancel()
