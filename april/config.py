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
    document_roots: tuple[str, ...] = ()
    documents_index_path: str = 'artifacts/documents.sqlite3'
    web_provider: str = 'searxng'
    automatic_web_search: bool = True
    searxng_url: str = 'http://127.0.0.1:8888'
    gmail_token_path: str = '~/.local/share/april/gmail-token.json'

    caldav_url: str = "http://127.0.0.1:5232/april/assistant/"
    caldav_credentials: str = "~/.config/april/caldav.json"
    caldav_server_config: str = "~/.config/april/radicale.ini"
    debug_runner_image: str = "python:3.12-slim@sha256:e695ab189fa2d082b1c61c69a6b888a5adeca61ceeccad107b1ed2a125721a9e"
    debug_project_root: str = "~/Documents/aprilfiles"
    avatar_3d: bool = True
    avatar_model_url: str = "/static/assets/april-prototype.glb"
    private_ollama_port: int = 11435
    private_ollama_models: str = ""
    wake_model: str = "models/vosk-model-small-en-us-0.15"
    wake_phrases: tuple[str, ...] = ("hey april", "okay april")
    desktop_input_device: str = "default"  # PortAudio name; browser IDs are different.
    wake_silence_seconds: float = 1.0
    wake_rms_threshold: float = .015
    wake_cooldown_seconds: float = 1.2
    wake_speech_wait_seconds: float = 5
    widget_hide_seconds: float = 5
    widget_width: int = 420
    widget_height: int = 600

    def __post_init__(self):
        import re
        if not re.fullmatch(r"(?:docker.io/library/)?python:3\.12-slim@sha256:[a-f0-9]{64}", self.debug_runner_image):
            raise ValueError("Use a reviewed digest-pinned Python 3.12 slim execution image")
        if not isinstance(self.avatar_3d,bool):raise ValueError("avatar_3d must be true or false")
        calendar=urlparse(self.caldav_url)
        if (calendar.scheme not in {"http","https"} or not calendar.hostname or calendar.username
                or calendar.password or calendar.query or calendar.fragment
                or (calendar.scheme=="http" and calendar.hostname not in {"localhost","127.0.0.1","::1"})):
            raise ValueError("CalDAV must use authenticated HTTPS or a loopback HTTP URL")
        if not re.fullmatch(r"/static/assets/[A-Za-z0-9_.-]+\.glb", self.avatar_model_url):
            raise ValueError("Use a local GLB in april/web/assets")
        if not 1024 <= self.private_ollama_port <= 65535:
            raise ValueError("Invalid private Ollama port")
        if (not isinstance(self.wake_phrases, (list, tuple)) or not 1 <= len(self.wake_phrases) <= 5
                or any(not isinstance(p, str) or not re.fullmatch(r"[a-z]+(?: [a-z]+){1,3}", p) for p in self.wake_phrases)):
            raise ValueError("Use 1–5 lowercase wake phrases of 2–4 words")
        if not .4 <= self.wake_silence_seconds <= 3 or not .001 <= self.wake_rms_threshold <= .2:
            raise ValueError("Invalid wake silence or microphone energy threshold")
        if not isinstance(self.desktop_input_device, str) or not self.desktop_input_device.strip():
            raise ValueError("desktop_input_device must be default or a PortAudio device name")
        if not 0.5 <= self.wake_cooldown_seconds <= 5 or not 2 <= self.wake_speech_wait_seconds <= 10:
            raise ValueError("Invalid wake cooldown or speech wait")
        if not 0 <= self.widget_hide_seconds <= 60:
            raise ValueError("Invalid widget hide delay")
        if not 340 <= self.widget_width <= 1000 or not 480 <= self.widget_height <= 1200:
            raise ValueError("Invalid widget dimensions")
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
        if not isinstance(self.document_roots, (list, tuple)) or any(not isinstance(root, str) or not root.strip() for root in self.document_roots):
            raise ValueError('document_roots must be a list of explicitly approved folders')
        if self.web_provider != 'searxng':
            raise ValueError('web_provider must be searxng')
        if not isinstance(self.automatic_web_search,bool):
            raise ValueError('automatic_web_search must be true or false')
        search=urlparse(self.searxng_url)
        if (search.scheme not in {'http','https'} or search.hostname not in {'localhost','127.0.0.1','::1'}
                or search.username or search.password or search.query or search.fragment or search.path not in {'','/'}):
            raise ValueError('SearXNG must use a loopback URL (or a local authenticated tunnel), without credentials or a path')
        if search.port is not None and not 1<=search.port<=65535:
            raise ValueError('Invalid SearXNG port')


def load_config() -> Config:
    path = Path(os.environ.get("APRIL_CONFIG", "april.local.toml"))
    data = tomllib.loads(path.read_text()) if path.exists() else {}
    unknown = set(data) - {f.name for f in fields(Config)}
    if unknown:
        raise ValueError(f"Unknown configuration keys: {', '.join(sorted(unknown))}")
    if os.environ.get("APRIL_MODE"):
        data["mode"] = os.environ["APRIL_MODE"]
    return Config(**data)
