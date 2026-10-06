"""Pure settings helpers (no UI)."""
from flowvoice.config import Config

_RESTART_FIELDS = ("ptt_key", "tts_key", "model", "mic_device", "start_with_windows")
_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\"}


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


def escape_text(s: str) -> str:
    """Make breaks visible for a one-line cell: backslash doubled, newline -> \\n, tab -> \\t."""
    return s.replace("\\", "\\\\").replace("\n", "\\n").replace("\t", "\\t")


def unescape_text(s: str) -> str:
    """Inverse of escape_text; unknown escapes and a trailing backslash are kept as typed."""
    out: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s) and s[i + 1] in _ESCAPES:
            out.append(_ESCAPES[s[i + 1]])
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def rows_to_commands(rows: list[tuple[str, str]]) -> dict[str, str]:
    """Table rows -> command mapping: phrases normalized, blanks dropped, later rows win."""
    commands: dict[str, str] = {}
    for phrase, output in rows:
        key = " ".join(phrase.lower().split())
        if key:
            commands[key] = unescape_text(output)
    return commands


def mic_choices() -> list[tuple[str, int | None]]:
    """("System default", None) then every input device as "index: name"; never raises."""
    choices: list[tuple[str, int | None]] = [("System default", None)]
    try:
        import sounddevice
        for i, d in enumerate(sounddevice.query_devices()):
            if d["max_input_channels"] > 0:
                choices.append((f"{i}: {d['name']}", i))
    except Exception:
        pass
    return choices
