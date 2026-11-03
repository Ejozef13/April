"""Bounded WAV validation. Audio exists only in memory and temporary job files."""
import io
import wave


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
