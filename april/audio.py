"""Bounded WAV validation. Audio exists only in memory and temporary job files."""
import io
import re
import wave


def validate_speech_wav(path, max_seconds):
    """Reject empty/truncated/unsupported Piper output before browser handoff."""
    try:
        with wave.open(str(path), 'rb') as wav:
            rate, frames = wav.getframerate(), wav.getnframes()
            if (wav.getnchannels(), wav.getsampwidth(), wav.getcomptype()) != (1, 2, 'NONE'):
                raise ValueError('Speech output must be mono PCM16')
            if not 8000 <= rate <= 48000 or not 0 < frames <= rate * max_seconds:
                raise ValueError('Speech output duration/rate outside playback limits')
            if len(wav.readframes(frames)) != frames * 2:
                raise ValueError('Truncated speech output')
    except (wave.Error, EOFError) as exc:
        raise ValueError('Invalid speech WAV') from exc


def validate_wav(data: bytes, seconds: int):
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (1, 2, 16000, "NONE"):
                raise ValueError("Audio must be mono PCM16 at 16000 Hz")
            frames = wav.getnframes()
            if not 1600 <= frames <= seconds * 16000:
                raise ValueError("Recording must be 0.1 seconds to the configured limit")
            if len(wav.readframes(frames)) != frames * 2:
                raise ValueError("Truncated audio")
    except (wave.Error, EOFError) as exc:
        raise ValueError("Invalid WAV recording") from exc


def spoken_answer(text, source_count=0):
    """Omit known numeric citations from TTS, keeping the displayed answer intact."""
    if not source_count:
        return text

    def citation(match):
        ids = [int(value) for value in re.findall(r"\d+", match[1])]
        return "" if all(1 <= value <= source_count for value in ids) else match[0]

    # Avoid changing code such as values[1], and leave non-citation brackets alone.
    text = re.sub(r"(?<![\w])\[(\d+(?:\s*[,;]\s*\d+)*)\]", citation, text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([.,!?;:])", r"\1", text).strip()
    return text or "The response contained only source citations."
