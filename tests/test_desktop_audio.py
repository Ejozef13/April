"""Native worker fixtures: fake PortAudio/Vosk, no actual microphone."""
import base64
import tempfile
import threading
import time
import unittest
from array import array
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    from PySide6.QtCore import Qt
    from april.desktop_audio import Microphone
except ImportError:
    Microphone = None

from april.config import Config


@unittest.skipIf(Microphone is None, 'Optional desktop dependencies not installed')
class WorkerTests(unittest.TestCase):
    def test_half_duplex_wake_capture_and_cancel(self):
        opened = []
        wake = threading.Event()
        delivered = threading.Event()
        results = []
        class Stream:
            def __init__(self, **kwargs):
                opened.append(kwargs)
                self.count = 0
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, count):
                time.sleep(.01)
                self.count += 1
                return (array('h', [2000] * count).tobytes() if self.count <= 4 else bytes(count * 2)), False
        class Recognizer:
            def __init__(self, *args):
                pass
            def AcceptWaveform(self, frame):
                return True
            def Result(self):
                return '{"text":"hey april"}'
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory)
            (model / 'am').mkdir()
            (model / 'am/final.mdl').touch()
            worker = Microphone(Config(wake_model=str(model), wake_silence_seconds=.4))
            worker.wake.connect(wake.set, Qt.ConnectionType.DirectConnection)
            def audio(encoded, epoch):
                results.append((base64.b64decode(encoded), epoch))
                delivered.set()
            worker.audio.connect(audio, Qt.ConnectionType.DirectConnection)
            with patch.dict('sys.modules', {
                'sounddevice':SimpleNamespace(RawInputStream=Stream),
                'vosk':SimpleNamespace(SetLogLevel=lambda value:None,
                                       Model=lambda path:object(), KaldiRecognizer=Recognizer)}):
                worker.start()
                try:
                    time.sleep(.1)
                    self.assertEqual(opened, [])  # Idle permission defaults closed.
                    worker.ready(True)
                    self.assertTrue(wake.wait(2))
                    time.sleep(.15)
                    self.assertEqual(len(opened), 1)  # No listening again until UI accepts.
                    worker.capture(7)
                    self.assertTrue(delivered.wait(2))
                    self.assertEqual(results[0][1], 7)
                    self.assertTrue(results[0][0].startswith(b'RIFF'))
                    count = len(opened)
                    time.sleep(.15)
                    self.assertEqual(len(opened), count)  # Paused during model/playback.
                    worker.capture(8)
                    worker.cancel()
                    time.sleep(.15)
                    self.assertEqual(len(results), 1)  # Cancelled audio never submitted.
                finally:
                    worker.requestInterruption()
                    worker.wait(3000)
