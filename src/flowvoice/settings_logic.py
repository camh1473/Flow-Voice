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


def _row_key(key: str, lower_keys: bool) -> str:
    key = key.strip()
    return key.lower() if lower_keys else key


def rows_to_dict(rows: list[tuple[str, str]], *, lower_keys: bool, limit: int) -> dict[str, str]:
    """Table rows -> mapping: keys trimmed (and lowercased if asked), blanks dropped, values
    unescaped but not trimmed, later rows win, first `limit` distinct keys kept."""
    out: dict[str, str] = {}
    for key, value in rows:
        k = _row_key(key, lower_keys)
        if not k:
            continue
        if k not in out and len(out) >= limit:
            continue
        out[k] = unescape_text(value)
    return out


def rows_duplicates(rows: list[tuple[str, str]], *, lower_keys: bool) -> list[str]:
    """Distinct keys used by more than one non-blank row, in first-seen order."""
    counts: dict[str, int] = {}
    for key, _ in rows:
        k = _row_key(key, lower_keys)
        if k:
            counts[k] = counts.get(k, 0) + 1
    return [k for k, n in counts.items() if n > 1]


def snippet_warnings(snippets: dict[str, str], command_phrases: dict[str, str]) -> list[str]:
    """One-line warnings for snippets that collide with a command, are too short, or are empty."""
    commands = {" ".join(p.lower().split()) for p in command_phrases}
    out: list[str] = []
    for trigger, text in snippets.items():
        if " ".join(trigger.lower().split()) in commands:
            out.append(f'"{trigger}" is also a spoken command; the snippet wins.')
        if len(trigger) < 3:
            out.append(f'"{trigger}" is shorter than 3 characters and may fire by accident.')
        if not text.strip():
            out.append(f'The snippet "{trigger}" is empty.')
    return out


def terms_from_text(text: str, limit: int = 200) -> list[str]:
    """One term per line; trimmed, blanks dropped, case-insensitive de-dupe keeping the first."""
    seen: set[str] = set()
    terms: list[str] = []
    for line in text.splitlines():
        term = line.strip()
        if term and term.lower() not in seen:
            seen.add(term.lower())
            terms.append(term)
    return terms[:limit]


def mic_choices()-> list[tuple[str, int | None]]:
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
