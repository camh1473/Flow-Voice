"""Rule-based list formatting: spoken or typed numbered and ordinal lists."""
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
    if item.endswith("."):
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
    tail = ""
    end = next(
        (e for e in _LAST_ITEM_END.finditer(items[-1])
         if not (e.group() == "." and _ABBREVIATION.search(items[-1][:e.start()]))),
        None,
    )
    if end:
        cut = end.start() if end.group() == "\n" else end.end()
        items[-1], tail = items[-1][:cut], items[-1][end.end():].strip()
    return text[:run[0].start], items, tail


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


def format_lists(text: str) -> str:
    """Format a spoken list as lines; return text unchanged if none is found or markup exists."""
    if not text or _has_list_markup(text):
        return text
    return _format_numbered(text) or text
