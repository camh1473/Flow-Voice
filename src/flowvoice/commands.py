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

GUARDED = frozenset({"period", "colon", "hyphen", "dash", "em dash", "slash", "dot"})
GUARD_WORDS = frozenset({
    "the", "a", "an", "this", "that", "time", "grace", "trial", "probation",
    "my", "your", "his", "her", "our", "their", "to",
})
CAPS_GUARD_WORDS = frozenset({
    "in", "with", "using", "is", "are", "was", "were", "the", "a", "an", "my", "your",
})
TLDS = frozenset({"com", "org", "net", "edu", "gov", "io", "co", "us", "ai", "dev", "app", "uk"})
_ADDRESS_JOINERS = frozenset({"slash", "hyphen", "dash", "em dash", "underscore", "dot"})
_CAPS_ON = ("all", "caps")
_CAPS_OFF = ("end", "caps")

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


def _set_off(token: str) -> bool:
    return token != token.strip(_TOUCH_PUNCT)


def _ends_clause(items: list[tuple[str, str]]) -> bool:
    """True when nothing is emitted yet or the last item already ends in punctuation."""
    if not items:
        return True
    last = items[-1][1].rstrip(" ")
    return not last or last[-1] in _TOUCH_PUNCT + ":\n"


def _converts(phrase, tokens, bare, i, n, in_address, next_is_command) -> bool:
    """Whether a matched phrase becomes its output here (guard rules)."""
    if phrase not in GUARDED:
        return True
    if in_address and phrase in _ADDRESS_JOINERS:
        return True
    if i > 0 and bare[i - 1] in GUARD_WORDS:
        return False
    if phrase == "dot":
        return i + n < len(bare) and bare[i + n] in TLDS
    if phrase == "period":
        bare_end = i + n >= len(tokens) and not _set_off(tokens[i])
        after_punct = i > 0 and tokens[i - 1][-1] in _TOUCH_PUNCT + ":"
        return bare_end or after_punct or next_is_command
    return True


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
    phrases.setdefault(_CAPS_ON, "all caps")
    phrases.setdefault(_CAPS_OFF, "end caps")
    longest = max(len(p) for p in phrases)
    tokens = text.split()
    bare = [_bare(t) for t in tokens]
    items: list[tuple[str, str]] = []
    changed = caps = in_address = False

    def add_word(token: str) -> None:
        nonlocal in_address
        if items and items[-1][0] == "word":
            in_address = False
        items.append(("word", token.upper() if caps else token))
        if "@" in token:
            in_address = True
        elif _set_off(token):
            in_address = False

    i = 0
    while i < len(tokens):
        if bare[i] == "literal" and (m := _match(bare, i + 1, phrases, longest)):
            n = m[1]
            for t in tokens[i + 1:i + 1 + n]:
                add_word(t)
            changed = True
            i += 1 + n
            continue
        m = _match(bare, i, phrases, longest)
        marker = tuple(bare[i:i + m[1]]) if m else None
        if marker in (_CAPS_ON, _CAPS_OFF) and not (
            marker == _CAPS_ON and i > 0 and bare[i - 1] in CAPS_GUARD_WORDS
        ):
            n = m[1]
            caps = marker == _CAPS_ON
            last = tokens[i + n - 1]
            trail = last[len(last.rstrip(_TOUCH_PUNCT)):]
            if trail and not _ends_clause(items):
                items.append(("attach", trail))
            changed = True
            i += n
            continue
        if m:
            phrase, n = m
            next_is_command = _match(bare, i + n, phrases, longest) is not None
            if marker not in (_CAPS_ON, _CAPS_OFF) and _converts(
                phrase, tokens, bare, i, n, in_address, next_is_command
            ):
                output = mapping[phrase]
                if in_address and phrase == "dash":
                    output = "-"
                role = _role(phrase, output)
                if role == "attach" and items and items[-1][0] == "word":
                    prev = items.pop()[1].rstrip(_TOUCH_PUNCT)
                    if prev:
                        items.append(("word", prev))
                items.append((role, output))
                in_address = (in_address and role == "join") or output == "@" or (
                    phrase == "dot" and role == "join"
                )
                changed = True
                i += n
                continue
            for t in tokens[i:i + n]:
                add_word(t)
            i += n
            continue
        add_word(tokens[i])
        i += 1
    return _join(items) if changed else text
