"""CPU wake-phrase and bounded utterance helpers; no audio is persisted."""
from array import array
import io
import math
import re
import sys
import wave


def matches_wake(text, phrases):
    normalize = lambda value: ' '.join(re.findall(r"[a-z]+", value.casefold()))
    return normalize(text) in {normalize(phrase) for phrase in phrases}


class Utterance:
    """Simple energy endpointing, not a learned speech detector.

    Keep only a short preroll before speech. Quiet rooms need threshold tuning;
    hard deadlines guarantee noise cannot produce an unbounded recording.
    """
    def __init__(self, *, max_seconds=15, silence_seconds=1, threshold=.015,
                 speech_wait_seconds=5, sample_rate=16000):
        self.rate = sample_rate
        self.maximum = int(max_seconds * sample_rate)
        self.silence = int(silence_seconds * sample_rate)
        self.wait = int(speech_wait_seconds * sample_rate)
        self.threshold = threshold
        self.total = self.voiced = self.quiet = 0
        self.pcm = bytearray()
        self.started = False
        self.rms = 0.0

    def feed(self, pcm):
        if len(pcm) % 2:
            raise ValueError('PCM16 requires complete samples')
        values = array('h', pcm)
        if sys.byteorder != 'little':
            values.byteswap()
        count = len(values)
        if not count:
            return None
        rms = math.sqrt(sum(v * v for v in values) / count) / 32768
        self.rms = rms
        self.total += count
        if rms >= self.threshold:
            self.started = True
            self.voiced += count
            self.quiet = 0
        else:
            self.quiet += count
        self.pcm.extend(pcm)
        if not self.started:
            # Preroll prevents clipping the first consonant.
            del self.pcm[:-int(.3 * self.rate) * 2]
            if self.total >= self.wait:
                return 'empty'
        if self.total >= self.maximum or (self.started and self.quiet >= self.silence):
            return 'ready' if self.voiced >= int(.2 * self.rate) else 'empty'
        return None

    def wav(self):
        output = io.BytesIO()
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.rate)
            wav.writeframes(bytes(self.pcm[:self.maximum * 2]))
        return output.getvalue()
