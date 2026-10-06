"""Rule-based list formatting: numbered, ordinal and cue-based bulleted lists."""
import re
from typing import NamedTuple


class Marker(NamedTuple):
    start: int
    end: int
    value: int
    kind: str = ""


_NUMBER_WORDS = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "firstly": 1, "secondly": 2, "thirdly": 3, "fourthly": 4, "fifthly": 5,
}
_NUM = r"\d{1,2}|" + "|".join(_NUMBER_WORDS)
_SET_OFF = r"[.,:)](?=\s|$)"

_NUMBER_MARKER = re.compile(
    rf"(?<![\w.,:$])(?:number\s+(?P<a>{_NUM})(?!\w)(?:{_SET_OFF})?|(?P<b>{_NUM})(?P<p>[.,:)])(?=\s|$))",
    re.IGNORECASE,
)
_DETERMINER = re.compile(r"(?<!\w)(?:my|our|your|his|her|their|its|the|a|an)\s+$", re.IGNORECASE)
_SENTENCE_GLUE = re.compile(r"\s+(?:Then|And|But|So)(?!\w)")
_ABBREVIATION = re.compile(r"(?<![\w.])(?:mrs|mr|ms|dr|st|jr|sr|vs|etc|e\.g|i\.e)$", re.IGNORECASE)
_ORDINAL_MARKER = re.compile(
    r"(?<!\w)(?P<o>" + "|".join(sorted(_ORDINALS, key=len, reverse=True)) + r")(?!\w)(?!\s+of\s+all\b)(?P<p>[,:])?",
    re.IGNORECASE,
)
_MARKUP = re.compile(r"(?m)^[ \t]*- |\n[ \t]*\d+\. ")
_SENTENCE_START = re.compile(r"(?:^|[.!?:]\s+|\n\s*)$")
_LAST_ITEM_END = re.compile(r"[.!?](?=\s+\S)|\n")
_EDGE_WORD = re.compile(r"^(?:and|then)(?!\w)|(?<!\w)(?:and|then)$", re.IGNORECASE)

_OBJECT_CUES = ("the following", "a list of", "list of")
_NOUN_CUES = (
    "shopping list", "to-do list", "to do list", "todo list",
    "things to do", "things i need", "agenda", "ingredients", "items",
)
_BULLET_CUE = re.compile(
    r"(?<![\w-])(?P<cue>" + "|".join(c.replace(" ", r"\s+") for c in _OBJECT_CUES + _NOUN_CUES)
    + r")(?![\w-])[ \t]*(?P<p>[:,])?[ \t]*",
    re.IGNORECASE,
)
_NOT_AN_ITEM = re.compile(
    r"(?:is|are|was|were|be|been|will|would|can|could|should|must|may|might|has|have|had|do|does|did"
    r"|i|you|he|she|it|we|they|me|him|us|them|this|that|these|those|there|which|who|what"
    r"|to|for|from|with|in|on|at|of|by|about|into|after|before|like"
    r"|day|days|week|weeks|month|months|year|years|morning|afternoon|evening|night|weekend|time)(?!\w)",
    re.IGNORECASE,
)
_BULLET_SEP = re.compile(r"\s*,(?=\s|$)\s*(?:(?:and|then)\s+)?|\s+(?:and|then)\s+", re.IGNORECASE)
_MAX_BULLET_WORDS = 6


def _value(token: str) -> int:
    token = token.lower()
    return int(token) if token.isdigit() else _NUMBER_WORDS.index(token) + 1


def _has_list_markup(text: str) -> bool:
    return bool(_MARKUP.search(text))


def _number_markers(text: str) -> list[Marker]:
    markers: list[Marker] = []
    for m in _NUMBER_MARKER.finditer(text):
        if m.group("a"):
            if _DETERMINER.search(text[:m.start()]):
                continue
            kind = "number"
        else:
            kind = m.group("p")
            if kind == "." and _SENTENCE_GLUE.match(text, m.end()):
                continue
        markers.append(Marker(m.start(), m.end(), _value(m.group("a") or m.group("b")), kind))
    return markers


def _ordinal_markers(text: str) -> list[Marker]:
    return [
        Marker(m.start(), m.end(), _ORDINALS[m.group("o").lower()], "ordinal")
        for m in _ORDINAL_MARKER.finditer(text)
        if m.group("p") or _SENTENCE_START.search(text[:m.start()])
    ]


def _select_run(markers: list[Marker]) -> list[Marker]:
    """Longest run 1, 2, 3, ... in text order; candidates off the run are skipped."""
    best: list[Marker] = []
    for i, first in enumerate(markers):
        if first.value != 1:
            continue
        run = [first]
        for m in markers[i + 1:]:
            if m.value == run[-1].value + 1:
                run.append(m)
        if len(run) > len(best):
            best = run
    return best if len(best) >= _min_length(best) else []


def _min_length(run: list[Marker]) -> int:
    """Comma-only runs (a final `N.` may end the sentence) need 3 markers; others need 2."""
    kinds = [m.kind for m in run]
    comma_only = bool(kinds) and all(k == "," for k in kinds[:-1]) and kinds[-1] in (",", ".")
    return 3 if comma_only else 2


def _clean_item(item: str) -> str:
    item = " ".join(item.split())
    while True:
        stripped = _EDGE_WORD.sub("", item.strip(" ,;")).strip(" ,;")
        if stripped == item:
            break
        item = stripped
    if item.endswith(".") and not _ABBREVIATION.search(item[:-1]):
        item = item[:-1].rstrip()
    if item[:1].isalpha():
        item = item[0].upper() + item[1:]
    return item


def _lead_in(text: str) -> str:
    lead = text.strip()
    if not lead or lead.endswith((":", "?", "!")):
        return lead
    return lead.rstrip(",.") + ":"


def _split(text: str, run: list[Marker]) -> tuple[str, list[str], str]:
    """Return (lead-in, raw items, tail) around the markers of `run`."""
    bounds = [m.start for m in run[1:]] + [len(text)]
    items = [text[m.end:end] for m, end in zip(run, bounds)]
    items[-1], tail = _cut_tail(items[-1])
    return text[:run[0].start], items, tail


def _cut_tail(text: str) -> tuple[str, str]:
    """Split at the first sentence end (not after a title abbreviation) or newline."""
    end = next(
        (e for e in _LAST_ITEM_END.finditer(text)
         if not (e.group() == "." and _ABBREVIATION.search(text[:e.start()]))),
        None,
    )
    if not end:
        return text, ""
    cut = end.start() if end.group() == "\n" else end.end()
    return text[:cut], text[end.end():].strip()


def _render(lead: str, lines: list[str], tail: str) -> str:
    out = "\n".join(([lead] if lead else []) + lines)
    return out + "\n\n" + tail if tail else out


def _format_numbered(text: str) -> str | None:
    run = _select_run(_number_markers(text)) or _select_run(_ordinal_markers(text))
    if not run:
        return None
    lead, raw_items, tail = _split(text, run)
    items = [_clean_item(item) for item in raw_items]
    if not all(re.search(r"\w", item) for item in items):
        return None
    lines = [f"{i}. {item}" for i, item in enumerate(items, 1)]
    return _render(_lead_in(lead), lines, tail)


def _bullet_items(text: str, cue: re.Match) -> tuple[list[str], str] | None:
    """Items and tail after `cue`, or None when the cue does not lead a list."""
    region, tail = _cut_tail(text[cue.end():])
    items = [_clean_item(item) for item in _BULLET_SEP.split(region)]
    if len(items) < 3:
        return None
    if cue.group("p") != ":":
        if " ".join(cue.group("cue").lower().split()) not in _OBJECT_CUES:
            return None
        if _SENTENCE_START.search(text[:cue.start()]) or ":" in region:
            return None
        if any(_NOT_AN_ITEM.match(item) for item in items):
            return None
    for item in items:
        words = [w for w in item.split() if re.search(r"\w", w)]
        if not words or len(words) > _MAX_BULLET_WORDS:
            return None
    return items, tail


def _format_bullets(text: str) -> str | None:
    for cue in _BULLET_CUE.finditer(text):
        found = _bullet_items(text, cue)
        if found:
            items, tail = found
            lead = text[:cue.start()] + cue.group("cue") + (cue.group("p") or "")
            return _render(_lead_in(lead), [f"- {item}" for item in items], tail)
    return None


def format_lists(text: str) -> str:
    """Format a spoken list as lines; return text unchanged if none is found or markup exists."""
    if not text or _has_list_markup(text):
        return text
    return _format_numbered(text) or _format_bullets(text) or text
