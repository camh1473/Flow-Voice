import re

from flowvoice.commands import apply_commands

DEFAULT_BACKTRACK_PHRASES = ["scratch that", "never mind", "nevermind", "forget that",
                             "delete that", "cancel that", "strike that", "ignore that",
                             "excuse me"]
DEFAULT_FILLER_PHRASES = ["you know", "i mean", "basically", "well"]

_FILLER = re.compile(r"\b(?:um+|uh+|erm?|hmm+)\b,?[ \t]*", re.IGNORECASE)
_REPEAT = re.compile(r"\b(\w+)(?:[ \t]+\1\b)+", re.IGNORECASE)
_SENTENCE_START = re.compile(r"(^|[.!?][ \t]+|\n)([a-z]\S*)")
_ADDRESS_LIKE = re.compile(r"[@/]|\w\.(?:com|org|net|edu|gov|io|co|us|ai|dev|app|uk)\b")
_PUNCT = ".!?,;"


def _alternation(phrases) -> str:
    return "|".join(re.escape(p.strip()) for p in sorted(phrases, key=len, reverse=True) if p.strip())


def _apply_backtracks(text: str, phrases) -> str:
    """Delete the sentence before each backtrack phrase, plus the phrase itself.

    A phrase only counts when set off from the surrounding words: preceded by the
    start of the text or punctuation, or followed by punctuation or the end. That
    keeps "I never mind waiting" intact.
    """
    alts = _alternation(phrases)
    if not alts:
        return text
    pattern = re.compile(rf"\b(?:{alts})\b", re.IGNORECASE)
    while True:
        for m in pattern.finditer(text):
            before, after = text[:m.start()], text[m.end():]
            before_s, after_s = before.rstrip(), after.lstrip()
            if (before_s == "" or before_s[-1] in _PUNCT
                    or after_s == "" or after_s[0] in _PUNCT):
                break
        else:
            return text
        core = before_s.rstrip(_PUNCT + " ")
        cut = max(core.rfind(c) for c in ".!?")
        kept = core[:cut + 1] if cut >= 0 else ""
        rest = after.lstrip(_PUNCT + " ")
        text = (kept + " " + rest).strip()


def _drop_fillers(text: str, phrases) -> str:
    """Remove phrases set off by a trailing comma ("it's, you know, fine")."""
    alts = _alternation(phrases)
    if not alts:
        return text
    return re.sub(rf"(?:,[ \t]*)?\b(?:{alts})\b[ \t]*,[ \t]*", " ", text, flags=re.IGNORECASE)


def _capitalize(m: re.Match) -> str:
    token = m.group(2)
    if _ADDRESS_LIKE.search(token):
        return m.group(0)
    return m.group(1) + token[0].upper() + token[1:]


def clean(text: str, *, fillers=DEFAULT_FILLER_PHRASES,
          backtracks=DEFAULT_BACKTRACK_PHRASES,
          commands: dict[str, str] | None = None) -> str:
    text = _apply_backtracks(text, backtracks)
    if commands is not None:
        text = apply_commands(text, commands)
    text = _FILLER.sub("", text)
    text = _drop_fillers(text, fillers)
    text = _REPEAT.sub(r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text).strip()
    text = re.sub(r"[ \t]+([.,!?])", r"\1", text)
    return _SENTENCE_START.sub(_capitalize, text)
