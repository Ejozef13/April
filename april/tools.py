"""One deterministic, read-only tool. No model-generated command execution."""
from datetime import datetime
from zoneinfo import ZoneInfo
import re


def normalize_request(text):
    text = text.casefold().strip().replace('’', "'")
    text = re.sub(r'^(?:hey\s+)?april\b[\s,:!.-]*', '', text)
    text = re.sub(r'^please\s+', '', text)
    text = re.sub(r'^(?:can|could|would) you\s+', '', text)
    return text.strip(' ?.!,')


def is_time_request(text):
    """Route only explicit clock/date requests; never guess inside documents."""
    return bool(re.fullmatch(
        r"(?:what time is it|what(?:'s| is) (?:the )?(?:current |local )?time|"
        r"tell me (?:the )?time|tell me what time it is|what(?:'s| is) (?:today's date|the date today)|"
        r"what day is it)(?: right now)?(?: please)?", normalize_request(text)))


def current_time(arguments: dict, timezone: str) -> str:
    if not isinstance(arguments, dict) or arguments:
        raise ValueError("current_time accepts an empty object only")
    return datetime.now(ZoneInfo(timezone)).strftime("It is %I:%M %p on %B %d, %Y (%Z).")
