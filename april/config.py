"""Non-secret settings. Local overrides live in an ignored TOML file."""
import os
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Config:
    mode: str = "live"
    host: str = "127.0.0.1"
    port: int = 8765
    ollama_url: str = "http://127.0.0.1:11434"
    model: str = "qwen2.5:3b"
    whisper_cli: str = "whisper-cli"
    stt_model: str = "models/ggml-base.en.bin"
    piper_cli: str = "piper"
    voice: str = "models/en_US-lessac-medium.onnx"
    timeout_seconds: float = 90
    playback_timeout_seconds: float = 60
    max_record_seconds: int = 15
    max_response_chars: int = 600
    max_response_tokens: int = 120
    context_tokens: int = 2048
    reasoning_effort: str = "default"
    display_width: int = 640
    display_height: int = 480
    input_device_id: str = "default"
    output_device_id: str = "default"
    timezone: str = "America/New_York"

    def __post_init__(self):
        if self.mode not in {"live", "simulation"}:
            raise ValueError("mode must be live or simulation")
        if self.host not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Bind to loopback; use an SSH tunnel for a remote client")
        url = urlparse(self.ollama_url)
        if url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.username or url.password or url.query or url.fragment:
            raise ValueError("Ollama must use a local HTTP endpoint (or local SSH tunnel)")
        if not 1 <= self.max_record_seconds <= 30 or not 1 <= self.timeout_seconds <= 180:
            raise ValueError("Recording limit must be 1–30s; request timeout 1–180s")
        if not 1 <= self.port <= 65535 or not 1 <= self.max_response_tokens <= 1024:
            raise ValueError("Invalid port or response token bound")
        if not 512 <= self.context_tokens <= 8192:
            raise ValueError("Context token limit must be 512–8192")
        if self.reasoning_effort not in {"default", "low", "medium", "high"}:
            raise ValueError("Reasoning effort must be default, low, medium or high")
        if not 40 <= self.max_response_chars <= 2000:
            raise ValueError("Response character limit must be 40–2000")
        if not 1 <= self.playback_timeout_seconds <= 180:
            raise ValueError("Playback timeout must be 1–180s")
        if not 240 <= self.display_width <= 1920 or not 240 <= self.display_height <= 1080:
            raise ValueError("Display dimensions must be within 240–1920 by 240–1080")
        from zoneinfo import ZoneInfo
        ZoneInfo(self.timezone)


def load_config() -> Config:
    path = Path(os.environ.get("APRIL_CONFIG", "april.local.toml"))
    data = tomllib.loads(path.read_text()) if path.exists() else {}
    unknown = set(data) - {f.name for f in fields(Config)}
    if unknown:
        raise ValueError(f"Unknown configuration keys: {', '.join(sorted(unknown))}")
    if os.environ.get("APRIL_MODE"):
        data["mode"] = os.environ["APRIL_MODE"]
    return Config(**data)
