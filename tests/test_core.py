"""Deterministic tests use fixtures, not physical devices or pretrained models."""
import asyncio
import base64
import io
import sys
import unittest
import wave

from fastapi.testclient import TestClient

from april.audio import validate_wav, validate_speech_wav
from april.backends import SimulationBackends, run_process
from april.config import Config
from april.server import create_app
from april.session import Session
from april.state import State, StateMachine
from april.tools import current_time


def wav_bytes(seconds=.2):
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b'\0\0' * int(seconds * 16000))
    return stream.getvalue()


class CoreTests(unittest.TestCase):
    def test_transitions(self):
        machine = StateMachine()
        for state in [State.LISTENING, State.TRANSCRIBING, State.THINKING, State.SPEAKING, State.IDLE]:
            machine.move(state)
        with self.assertRaises(ValueError):
            machine.move(State.SPEAKING)
        machine.move(State.ERROR)
        machine.move(State.IDLE)

    def test_tool_validation_and_observed_result(self):
        self.assertIn('It is ', current_time({}, 'America/New_York'))
        for arguments in [{'command': 'date'}, {'timezone': 'UTC'}, [], None]:
            with self.assertRaises(ValueError):
                current_time(arguments, 'UTC')

    def test_audio_bounds(self):
        validate_wav(wav_bytes(), 15)
        for bad in [b'not wav', wav_bytes(1)[:-8], wav_bytes(16)]:
            with self.assertRaises(ValueError):
                validate_wav(bad, 15)

    def test_generated_audio_is_validated_before_playback(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'reply.wav'
            output.write_bytes(wav_bytes())
            validate_speech_wav(output,60)
            for data in [b'not audio',wav_bytes(0),wav_bytes()[:-8]]:
                output.write_bytes(data)
                with self.assertRaises(ValueError):
                    validate_speech_wav(output,60)

    def test_local_configuration_only(self):
        for overrides in [{'host':'0.0.0.0'}, {'ollama_url':'https://example.com'}, {'max_record_seconds':31}]:
            with self.assertRaises(ValueError):
                Config(**overrides)

    def test_reasoning_configuration_and_desktop_profile(self):
        import tomllib
        from pathlib import Path
        profile = Path(__file__).resolve().parents[1] / 'april.desktop.example.toml'
        config = Config(**tomllib.loads(profile.read_text()))
        self.assertEqual(config.model, 'gpt-oss:20b')
        self.assertEqual(config.max_response_tokens, 512)
        for overrides in [{'max_response_tokens':1025}, {'context_tokens':8193}, {'reasoning_effort':'unbounded'}]:
            with self.assertRaises(ValueError):
                Config(**overrides)

    def test_http_and_websocket_origins(self):
        with TestClient(create_app(Config(mode='simulation')), base_url='http://localhost') as client:
            self.assertEqual(client.get('/').status_code, 200)
            self.assertEqual(client.get('/health').json()['mode'], 'simulation')
            self.assertEqual(client.get('/', headers={'host':'evil.example'}).status_code, 403)
            with self.assertRaises(Exception):
                with client.websocket_connect('ws://localhost/ws', headers={'origin':'http://evil.example'}):
                    pass
            with client.websocket_connect('ws://localhost/ws', headers={'origin':'http://localhost'}) as socket:
                self.assertEqual(socket.receive_json()['state'], 'idle')
                socket.send_json({'type':'text','text':'Hello'})
                messages = []
                while True:
                    item = socket.receive_json()
                    messages.append(item)
                    if item.get('type') == 'state' and item.get('state') == 'idle':
                        break
                self.assertTrue(any(m.get('type') == 'reply' and '[Simulated' in m['text'] for m in messages))
                self.assertFalse(any(m.get('type') == 'audio' for m in messages))


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.messages = []
        async def send(message):
            self.messages.append(message)
        self.gate = asyncio.Lock()
        self.session = Session(Config(mode='simulation'), SimulationBackends(), send, self.gate)

    async def asyncTearDown(self):
        await self.session.cancel()

    async def test_voice_simulation_state_sequence(self):
        await self.session.handle({'type':'record'})
        await self.session.handle({'type':'audio', 'audio':base64.b64encode(wav_bytes()).decode()})
        await self.session.task
        self.assertEqual([m['state'] for m in self.messages if m['type']=='state'],
                         ['listening','transcribing','thinking','idle'])
        self.assertFalse(self.gate.locked())

    async def test_cancel_releases_gate_and_recovers(self):
        await self.session.handle({'type':'text','text':'Hello'})
        await asyncio.sleep(.02)
        await self.session.cancel()
        await asyncio.sleep(.4)
        self.assertFalse(any(m['type']=='reply' for m in self.messages))
        self.assertFalse(self.gate.locked())
        await self.session.handle({'type':'time','arguments':{}})
        await self.session.task
        self.assertTrue(any(m.get('source')=='current_time' for m in self.messages))

    async def test_failure_then_success_without_restart(self):
        class Failing(SimulationBackends):
            async def respond(self, text):
                raise RuntimeError('secret prompt must not leak')
        self.session.backends = Failing()
        await self.session.handle({'type':'text','text':'fail'})
        await self.session.task
        self.assertEqual(self.session.machine.state, State.ERROR)
        self.assertNotIn('secret prompt', str(self.messages))
        self.session.backends = SimulationBackends()
        await self.session.handle({'type':'text','text':'retry'})
        await self.session.task
        self.assertEqual(self.session.machine.state, State.IDLE)

    async def test_bounded_timeout(self):
        class Slow(SimulationBackends):
            async def respond(self, text):
                await asyncio.sleep(10)
        self.session.config = Config(mode='simulation', timeout_seconds=1)
        self.session.backends = Slow()
        await self.session.handle({'type':'text','text':'hello'})
        await self.session.task
        self.assertEqual(self.session.machine.state, State.ERROR)
        self.assertFalse(self.gate.locked())

    async def test_no_concurrent_queue(self):
        await self.session.handle({'type':'record'})
        await self.session.handle({'type':'text','text':'overlap'})
        self.assertIsNone(self.session.task)
        self.assertIn('busy', self.messages[-1]['message'])

    async def test_invalid_audio_recovery(self):
        await self.session.handle({'type':'record'})
        await self.session.handle({'type':'audio','audio':'invalid!'})
        self.assertEqual(self.session.machine.state, State.ERROR)
        self.assertFalse(self.gate.locked())

    async def test_invalid_tool_arguments_rejected(self):
        await self.session.handle({'type':'time','arguments':{'shell':'date'}})
        await self.session.task
        self.assertEqual(self.session.machine.state, State.ERROR)
        self.assertFalse(any(m['type']=='reply' for m in self.messages))

    async def test_spoken_and_typed_time_use_actual_clock_without_model(self):
        from unittest.mock import AsyncMock,patch
        from april.tools import is_time_request
        for text in ['Tell me the time','April, what time is it?']:
            self.assertTrue(is_time_request(text))
            self.messages.clear()
            with patch.object(self.session.backends,'respond',AsyncMock(side_effect=AssertionError('Clock must not call the LLM'))):
                await self.session.handle({'type':'text','text':text})
                await self.session.task
            self.assertTrue(any(m.get('source')=='current_time' for m in self.messages))
            self.assertTrue(any(m.get('type')=='transcript' and m['text']==text for m in self.messages))
        self.assertFalse(is_time_request('Explain how time travel works'))
        self.assertTrue(is_time_request('April, can you tell me the time please?'))
        self.messages.clear()
        with patch.object(self.session.backends,'transcribe',AsyncMock(return_value='April, tell me the time')), \
             patch.object(self.session.backends,'respond',AsyncMock(side_effect=AssertionError('Clock must not call the LLM'))):
            await self.session.handle({'type':'record'})
            await self.session.handle({'type':'audio','audio':base64.b64encode(wav_bytes()).decode()})
            await self.session.task
        self.assertTrue(any(m.get('source')=='current_time' for m in self.messages))
        self.assertTrue(any(m.get('type')=='transcript' and m['text']=='April, tell me the time' for m in self.messages))

    async def test_cancel_terminates_owned_subprocess(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'completed'
            task = asyncio.create_task(run_process(sys.executable, '-c',
                'import time,pathlib,sys; time.sleep(1); pathlib.Path(sys.argv[1]).touch()', str(marker)))
            await asyncio.sleep(.1)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            await asyncio.sleep(1.1)
            self.assertFalse(marker.exists())
