"""Pure settings helpers (no UI)."""
from flowvoice.config import Config

_RESTART_FIELDS = ("ptt_key", "tts_key", "model", "mic_device", "start_with_windows")


def parse_phrases(text: str) -> list[str]:
    """One phrase per line; trimmed, lowercased, de-duplicated, blanks dropped."""
    seen: list[str] = []
    for line in text.splitlines():
        p = line.strip().lower()
        if p and p not in seen:
            seen.append(p)
    return seen


def needs_restart(old: Config, new: Config) -> bool:
    return any(getattr(old, f) != getattr(new, f) for f in _RESTART_FIELDS)
