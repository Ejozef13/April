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


def is_goodbye_request(text):
    cleaned=' '.join(re.findall(r'[a-z]+', text.casefold()))
    return cleaned in {'goodbye april', 'good bye april', 'hey april goodbye', 'april goodbye'}


def is_calendar_read_request(text):
    """Recognize personal agenda questions without depending on one exact sentence."""
    period=r'(?:today|tomorrow|this week)'
    return bool(re.fullmatch(
        r'(?:what do i have planned(?: (?:for )?'+period+r')?|'
        r"what(?:'s| is) on my (?:calendar|schedule|agenda)(?: (?:for )?"+period+r')?|'
        r'what am i doing(?: '+period+r')?|'
        r'(?:show|read|tell me) my (?:calendar|schedule|agenda)(?: (?:for )?'+period+r')?)',
        normalize_request(text)))


def calendar_period(text):
    request=normalize_request(text)
    if re.search(r'\btomorrow\b',request):return 'tomorrow'
    if re.search(r'\btoday\b',request):return 'today'
    return None
