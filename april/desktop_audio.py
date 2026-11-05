"""Native mic worker. Vosk only detects phrases; Whisper transcribes commands."""
import base64
import json
import threading
import time
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .wake import Utterance, matches_wake


class Microphone(QThread):
    wake = Signal()
    goodbye = Signal()
    audio = Signal(str, int)
    level = Signal(float, int)
    empty = Signal(int)
    failed = Signal(str)

    def __init__(self, config):
        super().__init__()
        self.config = config
        self._lock = threading.Lock()
        self._ready = False
        self._epoch = None
        self._finish = False
        self._fault = False
        self._wake_fault = False
        self._until = 0
        self._model = None
        self._stream = None

    def ready(self, value):
        with self._lock:
            self._ready = value

    def capture(self, epoch):
        with self._lock:
            self._epoch = epoch
            self._finish = False

    def finish(self):
        with self._lock:
            self._finish = True

    def cancel(self):
        with self._lock:
            self._epoch = None
            self._ready = False
            self._until = time.monotonic() + self.config.wake_cooldown_seconds

    def retry(self):
        with self._lock:
            self._fault = self._wake_fault = False

    def stop(self):
        self.requestInterruption()
        with self._lock:
            stream = self._stream
        if stream is not None:
            try:
                stream.abort()
            except Exception:
                pass  # The worker may already have closed its own stream.

    def _snapshot(self):
        with self._lock:
            return self._ready, self._epoch, self._finish, self._fault, self._wake_fault

    def run(self):
        try:
            import sounddevice as sd
        except (ImportError, OSError):
            self.failed.emit('Desktop audio unavailable. Install requirements-desktop.lock and Linux PortAudio.')
            return
        while not self.isInterruptionRequested():
            ready, epoch, _, fault, wake_fault = self._snapshot()
            if fault or (epoch is None and (not ready or wake_fault or time.monotonic() < self._until)):
                self.msleep(50)
                continue
            recognizer = None
            if epoch is None:
                try:
                    from vosk import Model, KaldiRecognizer, SetLogLevel
                    SetLogLevel(-1)  # Never log incidental speech or model internals.
                    path = Path(self.config.wake_model).expanduser()
                    if not (path / 'am/final.mdl').is_file():
                        raise ValueError('missing wake model')
                    if self._model is None:
                        self._model = Model(str(path))
                    grammar = json.dumps([*self.config.wake_phrases, 'goodbye april', '[unk]'])
                    recognizer = KaldiRecognizer(self._model, 16000, grammar)
                except Exception:
                    with self._lock:
                        self._wake_fault = True
                    self.failed.emit('Wake model unavailable. See docs/WIDGET.md. Tray Record still works.')
                    continue
            utterance = Utterance(max_seconds=self.config.max_record_seconds,
                                  silence_seconds=self.config.wake_silence_seconds,
                                  threshold=self.config.wake_rms_threshold,
                                  speech_wait_seconds=self.config.wake_speech_wait_seconds)
            try:
                device = self.config.desktop_input_device
                with sd.RawInputStream(samplerate=16000, channels=1, dtype='int16',
                                       device=None if device == 'default' else device,
                                       blocksize=1600) as stream:
                    with self._lock:
                        self._stream = stream
                    while not self.isInterruptionRequested():
                        current_ready, current_epoch, finish, _, _ = self._snapshot()
                        if epoch != current_epoch or (epoch is None and not current_ready):
                            break
                        frame, overflow = stream.read(1600)
                        if overflow:
                            raise RuntimeError('input overflow')
                        pcm = bytes(frame)
                        if epoch is None:
                            if recognizer.AcceptWaveform(pcm):
                                text = json.loads(recognizer.Result()).get('text', '')
                                if matches_wake(text, ['goodbye april']):
                                    self.ready(False)
                                    self.goodbye.emit()
                                    break
                                if matches_wake(text, self.config.wake_phrases):
                                    self.ready(False)
                                    self.wake.emit()
                                    break
                        else:
                            outcome = utterance.feed(pcm)
                            self.level.emit(utterance.rms, epoch)
                            if finish:
                                outcome = 'ready' if utterance.voiced >= 3200 else 'empty'
                            if outcome:
                                # Clear before emitting, so stale data cannot start another capture.
                                with self._lock:
                                    if self._epoch != epoch:
                                        break
                                    self._epoch = None
                                    self._ready = False
                                    self._until = time.monotonic() + self.config.wake_cooldown_seconds
                                if outcome == 'ready':
                                    self.audio.emit(base64.b64encode(utterance.wav()).decode(), epoch)
                                else:
                                    self.empty.emit(epoch)
                                break
            except Exception:
                if self.isInterruptionRequested():
                    break
                with self._lock:
                    self._fault = True
                    self._epoch = None
                self.failed.emit('Microphone unavailable/overflowed. Check the native input device, then choose Retry microphone.')
            finally:
                utterance.pcm.clear()
                with self._lock:
                    self._stream = None
        self._model = None
