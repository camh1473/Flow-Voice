import re

_FILLER = re.compile(r"\b(?:um+|uh+|erm?|hmm+)\b,?\s*", re.IGNORECASE)
_REPEAT = re.compile(r"\b(\w+)(?:\s+\1\b)+", re.IGNORECASE)
_SENTENCE_START = re.compile(r"(^|[.!?]\s+)([a-z])")


def clean(text: str) -> str:
    text = _FILLER.sub("", text)
    text = _REPEAT.sub(r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,!?])", r"\1", text)
    return _SENTENCE_START.sub(lambda m: m.group(1) + m.group(2).upper(), text)
