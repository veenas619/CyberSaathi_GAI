"""Safety nets for text the model wrote.

1. guard_text: remove invented links and phone numbers. Allowed: the verified official sites, URLs that appear
   in retrieved sources, and anything the user themselves said (e.g. the caller's number).
2. script_matches: check the reply is actually written in the language/script that was requested, so a model
   that answers in English (or the wrong script) is never spoken by a Marathi/Tamil/Gujarati voice.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

ALLOWED_HOSTS = {"cybercrime.gov.in", "sancharsaathi.gov.in"}

URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s)>\]\"']+"
    r"|\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:gov\.in|nic\.in|co\.in|com|org|net|in)\b(?:/[^\s)>\]\"']*)?",
    re.IGNORECASE,
)
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)"
    r"|(?<!\d)1800[\s-]?\d{3}[\s-]?\d{3,4}(?!\d)"
)

SCRIPT_RANGES = {
    "hi": (0x0900, 0x097F), "mr": (0x0900, 0x097F), "bn": (0x0980, 0x09FF), "pa": (0x0A00, 0x0A7F),
    "gu": (0x0A80, 0x0AFF), "or": (0x0B00, 0x0B7F), "ta": (0x0B80, 0x0BFF), "te": (0x0C00, 0x0C7F),
    "kn": (0x0C80, 0x0CFF), "ml": (0x0D00, 0x0D7F),
}


def _host(url: str) -> str:
    candidate = url if "://" in url else "http://" + url
    return (urlparse(candidate).hostname or "").lower().removeprefix("www.")


def guard_text(text: str, narration: str, retrieved: list[dict]) -> tuple[str, int]:
    """Return (clean_text, number_of_removals)."""
    if not text:
        return text, 0
    allowed = set(ALLOWED_HOSTS) | {_host(item["url"]) for item in retrieved if item.get("url")}
    narration_lower = narration.lower()
    narration_digits = re.sub(r"\D", "", narration)
    removed = 0

    def fix_url(match: re.Match) -> str:
        nonlocal removed
        url = match.group(0).rstrip(".,;:")
        host = _host(url)
        if any(host == a or host.endswith("." + a) for a in allowed) or url.lower() in narration_lower or host in narration_lower:
            return match.group(0)
        removed += 1
        return "[link removed]"

    def fix_phone(match: re.Match) -> str:
        nonlocal removed
        digits = re.sub(r"\D", "", match.group(0))
        if digits[-10:] in narration_digits or digits in narration_digits:
            return match.group(0)
        removed += 1
        return "[number removed]"

    return PHONE_RE.sub(fix_phone, URL_RE.sub(fix_url, text)), removed


def script_matches(text: str, language_code: str) -> bool:
    """True if most letters in text are in the script of language_code (Latin for English)."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    base = (language_code or "en").split("-")[0].lower()
    if base == "en":
        return sum(1 for c in letters if c.isascii()) / len(letters) >= 0.8
    low_high = SCRIPT_RANGES.get(base)
    if not low_high:
        return True  # a language we have no script rule for: do not block it
    return sum(1 for c in letters if low_high[0] <= ord(c) <= low_high[1]) / len(letters) >= 0.5
