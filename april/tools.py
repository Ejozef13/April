"""One deterministic, read-only tool. No model-generated command execution."""
from datetime import datetime
from zoneinfo import ZoneInfo


def current_time(arguments: dict, timezone: str) -> str:
    if not isinstance(arguments, dict) or arguments:
        raise ValueError("current_time accepts an empty object only")
    return datetime.now(ZoneInfo(timezone)).strftime("It is %I:%M %p on %B %d, %Y (%Z).")
