"""Spoken punctuation/formatting commands: phrase table and text transformer."""

DEFAULT_COMMANDS: dict[str, str] = {
    # always convert
    "new line": "\n",
    "new paragraph": "\n\n",
    "bullet point": "\n- ",
    "question mark": "?",
    "exclamation point": "!",
    "exclamation mark": "!",
    "full stop": ".",
    "comma": ",",
    "semicolon": ";",
    "ellipsis": "...",
    "open quote": '"',
    "close quote": '"',
    "open paren": "(",
    "close paren": ")",
    "open bracket": "[",
    "close bracket": "]",
    "at sign": "@",
    "underscore": "_",
    "ampersand": "&",
    "percent sign": "%",
    "dollar sign": "$",
    "plus sign": "+",
    "equals sign": "=",
    # guarded
    "period": ".",
    "colon": ":",
    "hyphen": "-",
    "dash": "\u2014",
    "em dash": "\u2014",
    "slash": "/",
    "dot": ".",
}

GUARDED = frozenset({"period", "colon", "hyphen", "dash", "slash", "dot"})

_TOUCH_PUNCT = ".,;!?"
_OPEN = frozenset({"open quote", "open paren", "open bracket"})
_CLOSE = frozenset({"close quote", "close paren", "close bracket"})
_JOIN = frozenset({"at sign", "underscore", "slash", "hyphen", "dash", "em dash", "dot"})
_PREFIX = frozenset({"dollar sign"})
_ATTACH_LEFT = frozenset({"percent sign"})

# role -> (no space before, no space after)
_ROLE_SPACING = {
    "word": (False, False),
    "normal": (False, False),
    "attach": (True, False),
    "open": (False, True),
    "close": (True, False),
    "join": (True, True),
    "prefix": (False, True),
    "break": (True, True),
}


def _bare(token: str) -> str:
    return token.strip(_TOUCH_PUNCT).lower()


def _role(phrase: str, output: str) -> str:
    if "\n" in output:
        return "break"
    if phrase in _OPEN:
        return "open"
    if phrase in _CLOSE:
        return "close"
    if phrase in _JOIN:
        return "join"
    if phrase in _PREFIX:
        return "prefix"
    if phrase in _ATTACH_LEFT or (output and (output == "..." or all(c in ".,;:!?" for c in output))):
        return "attach"
    return "normal"


def _match(bare: list[str], i: int, phrases: dict[tuple[str, ...], str], longest: int):
    """Longest phrase starting at word i, as (phrase, word count), or None."""
    for n in range(min(longest, len(bare) - i), 0, -1):
        phrase = phrases.get(tuple(bare[i:i + n]))
        if phrase is not None:
            return phrase, n
    return None


def _converts(phrase: str) -> bool:
    """Whether a matched phrase becomes its output here (guard rules hook)."""
    return phrase not in GUARDED


def _join(items: list[tuple[str, str]]) -> str:
    out = ""
    glue_next = True
    for role, text in items:
        no_before, no_after = _ROLE_SPACING[role]
        if role == "break":
            out = out.rstrip(" ")
            if not out:
                text = text.lstrip("\n")
        elif out and not glue_next and not no_before:
            out += " "
        out += text
        glue_next = no_after
    return out


def apply_commands(text: str, mapping: dict[str, str] = DEFAULT_COMMANDS) -> str:
    """Replace spoken command phrases in text with their symbols or breaks."""
    phrases = {tuple(k.lower().split()): k for k in mapping if k.split()}
    if not phrases:
        return text
    longest = max(len(p) for p in phrases)
    tokens = text.split()
    bare = [_bare(t) for t in tokens]
    items: list[tuple[str, str]] = []
    changed = False
    i = 0
    while i < len(tokens):
        if bare[i] == "literal" and (m := _match(bare, i + 1, phrases, longest)):
            n = m[1]
            items.extend(("word", t) for t in tokens[i + 1:i + 1 + n])
            changed = True
            i += 1 + n
            continue
        m = _match(bare, i, phrases, longest)
        if m and _converts(m[0]):
            phrase, n = m
            output = mapping[phrase]
            role = _role(phrase, output)
            if role == "attach" and items and items[-1][0] == "word":
                prev = items.pop()[1].rstrip(_TOUCH_PUNCT)
                if prev:
                    items.append(("word", prev))
            items.append((role, output))
            changed = True
            i += n
            continue
        items.append(("word", tokens[i]))
        i += 1
    return _join(items) if changed else text
