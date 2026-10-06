import re


def _unique_terms(terms: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for term in terms:
        term = term.strip()
        if term and term.lower() not in seen:
            seen.add(term.lower())
            out.append(term)
    return out


def glossary_prompt(terms: list[str], limit: int = 400) -> str | None:
    """Whisper initial prompt "Glossary: A, B, C." capped at `limit` characters."""
    chosen: list[str] = []
    for term in _unique_terms(terms):
        candidate = "Glossary: " + ", ".join(chosen + [term]) + "."
        if len(candidate) > limit:
            break
        chosen.append(term)
    return "Glossary: " + ", ".join(chosen) + "." if chosen else None


def apply_dictionary(text: str, terms: list[str], fixes: dict[str, str]) -> str:
    """Rewrite whole-word fixes and fix the casing of known terms in one pass.

    Matching is case-insensitive and the write-as text is exact. Every match comes
    from the original text, so replacements are never re-scanned (no chaining).
    A fix wins over a term with the same heard-as; longer matches win over shorter.
    """
    targets: dict[str, str] = {}
    for term in _unique_terms(terms):
        targets[term.lower()] = term
    for heard, write_as in fixes.items():
        if heard.strip():
            targets[heard.strip().lower()] = write_as
    if not targets:
        return text
    alts = "|".join(re.escape(k) for k in sorted(targets, key=len, reverse=True))
    pattern = re.compile(rf"(?<!\w)(?:{alts})(?!\w)", re.IGNORECASE)
    return pattern.sub(lambda m: targets[m.group(0).lower()], text)


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def is_glossary_echo(text: str, terms: list[str]) -> bool:
    """True when a transcript is only the glossary prompt echoed back (silence)."""
    allowed = {w for term in terms for w in _words(term)}
    words = [w for w in _words(text) if w != "glossary"]
    return bool(words) and all(w in allowed for w in words)
