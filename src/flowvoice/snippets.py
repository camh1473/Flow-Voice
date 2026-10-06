"""Snippets: spoken trigger phrases swapped for private-use placeholders, expanded last."""
import re

PLACEHOLDER_BASE = 0xE100

_TOUCH = "[.,;!?]"


def _key(trigger: str) -> str:
    return " ".join(trigger.split()).lower()


def protect_snippets(text: str, snippets: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Replace each trigger in text with a placeholder; return (text, placeholder -> snippet)."""
    table: dict[str, str] = {}
    for trigger, expansion in snippets.items():
        table.setdefault(_key(trigger), expansion)
    table.pop("", None)
    if not table:
        return text, {}
    alts = "|".join(
        r"[ \t]+".join(re.escape(w) for w in key.split())
        for key in sorted(table, key=len, reverse=True)
    )
    pattern = re.compile(
        rf"(?:(?<!\S){_TOUCH}+)?(?<!\w)(?:(?P<lit>literal)[ \t]+)?"
        rf"(?P<trig>{alts})(?!\w){_TOUCH}*",
        re.IGNORECASE,
    )
    placeholders: dict[str, str] = {}
    mapping: dict[str, str] = {}

    def replace(m: re.Match) -> str:
        if m.group("lit"):
            return m.string[m.start():m.start("lit")] + m.string[m.start("trig"):m.end()]
        key = _key(m.group("trig"))
        if key not in placeholders:
            ph = chr(PLACEHOLDER_BASE + len(placeholders))
            placeholders[key] = ph
            mapping[ph] = table[key]
        return placeholders[key]

    return pattern.sub(replace, text), mapping


def expand_snippets(text: str, mapping: dict[str, str]) -> str:
    """Replace each placeholder with its snippet text in one pass (no re-scanning)."""
    if not mapping:
        return text
    return "".join(mapping.get(c, c) for c in text)
