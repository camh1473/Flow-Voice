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


def _prompt_terms(terms: list[str], limit: int = 400) -> list[str]:
    chosen: list[str] = []
    for term in _unique_terms(terms):
        if len("Glossary: " + ", ".join(chosen + [term]) + ".") > limit:
            break
        chosen.append(term)
    return chosen


def glossary_prompt(terms: list[str], limit: int = 400) -> str | None:
    """Whisper initial prompt "Glossary: A, B, C." capped at `limit` characters."""
    chosen = _prompt_terms(terms, limit)
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
    """True when a transcript is the glossary prompt echoed back (Whisper on silence).

    Only the whole prompt, or the first 2+ terms in list order, count; a single term
    said alone is real dictation.
    """
    words = _words(text)
    chosen = _prompt_terms(terms)
    if not words or not chosen:
        return False
    parts = [_words(t) for t in chosen]
    if words == ["glossary"] + [w for p in parts for w in p]:
        return True
    return any(words == [w for p in parts[:k] for w in p] for k in range(2, len(parts) + 1))
