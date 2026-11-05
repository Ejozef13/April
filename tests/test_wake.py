"""Deterministic PCM/routing/autostart fixtures, not wake accuracy measurements."""
import io
import tempfile
import unittest
import wave
from array import array
from pathlib import Path
import zipfile

from april.autostart import install
from april.config import Config
from april.wake import Utterance, matches_wake
from april.wake_setup import MODEL, extract


class WakeTests(unittest.TestCase):
    def test_only_complete_configured_phrase_matches(self):
        for phrase in ['Hey April!', 'OKAY APRIL']:
            self.assertTrue(matches_wake(phrase, Config().wake_phrases))
        for phrase in ['', '[unk]', 'april', 'hey apple', 'they said hey april today']:
            self.assertFalse(matches_wake(phrase, Config().wake_phrases))

    def test_endpoint_waits_for_speech_then_silence_and_wav_is_bounded(self):
        detector = Utterance(max_seconds=3, silence_seconds=.5)
        quiet = bytes(3200)
        speech = array('h', [2000] * 1600).tobytes()
        for _ in range(5):
            self.assertIsNone(detector.feed(quiet))
        for _ in range(4):
            self.assertIsNone(detector.feed(speech))
        for _ in range(4):
            self.assertIsNone(detector.feed(quiet))
        self.assertEqual(detector.feed(quiet), 'ready')
        with wave.open(io.BytesIO(detector.wav()), 'rb') as wav:
            self.assertEqual(wav.getframerate(), 16000)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertLessEqual(wav.getnframes(), 48000)

    def test_empty_room_and_continuous_noise_both_end(self):
        quiet = Utterance(speech_wait_seconds=2)
        for _ in range(19):
            self.assertIsNone(quiet.feed(bytes(3200)))
        self.assertEqual(quiet.feed(bytes(3200)), 'empty')
        noisy = Utterance(max_seconds=2)
        frame = array('h', [2000] * 1600).tobytes()
        for _ in range(19):
            self.assertIsNone(noisy.feed(frame))
        self.assertEqual(noisy.feed(frame), 'ready')

    def test_bad_configuration_and_incomplete_sample_rejected(self):
        for overrides in [{'wake_phrases':['april']}, {'wake_phrases':['Hey April']},
                          {'wake_rms_threshold':0}, {'widget_width':50},
                          {'wake_silence_seconds':10}, {'wake_cooldown_seconds':0}]:
            with self.assertRaises(ValueError):
                Config(**overrides)
        with self.assertRaises(ValueError):
            Utterance().feed(b'\0')

    def test_autostart_is_opt_in_scoped_and_quotes_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'April project % $'
            root.mkdir()
            (root / 'april.sh').write_text('# fixture')
            output = Path(directory) / 'autostart'
            entry = install(root, output)
            text = entry.read_text()
            self.assertIn('april.power', text)
            self.assertIn('--login', text)
            self.assertIn('start', text)
            self.assertIn('%%', text)
            self.assertIn('\\$', text)
            install(root, output)  # Managed replacement only.
            install(root, output, remove=True)
            self.assertFalse(entry.exists())
            entry.write_text('unrelated')
            with self.assertRaises(ValueError):
                install(root, output)
            with self.assertRaises(ValueError):
                install(root, output, remove=True)
            self.assertEqual(entry.read_text(), 'unrelated')

    def test_model_zip_does_not_escape_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root / 'model.zip'
            for name in ['../escape', MODEL + '/../escape', '/absolute', 'unrelated/file']:
                with zipfile.ZipFile(archive, 'w') as zipped:
                    zipped.writestr(name, 'fixture')
                with self.assertRaises(ValueError):
                    extract(archive, root / 'out')
            with zipfile.ZipFile(archive, 'w') as zipped:
                zipped.writestr(MODEL + '/am/final.mdl', 'fixture')
            extract(archive, root / 'out')
            self.assertTrue((root / 'out' / MODEL / 'am/final.mdl').is_file())
