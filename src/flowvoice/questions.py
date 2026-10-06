"""Rule-based question marks: a sentence that clearly asks a question ends with '?'."""
import re

_WH = r"(?:who|whom|whose|what|when|where|why|how|which)"
_PRONOUN = {"i", "we", "you", "they", "he", "she", "it"}
_AUX_WORDS = {"is", "are", "was", "were", "do", "does", "did", "can", "could", "will", "would",
              "should", "shall", "has", "have", "had", "may", "might", "must"}
_SUBJECTS = {
    "is": "i|you|he|she|it|we|they|this|that|there|these|those|the|a|an|my|your|our|his|her|their|any|anyone|anybody|someone|everyone",
    "yes_no": "i|you|he|she|it|we|they|this|that|there|these|those|anyone|anybody|someone|everyone|my|your|our|his|her|their|any",
}
_BE = {"is", "are", "was", "were"}
_NEEDS_DETERMINER_OK = {"does", "did", "can", "could", "will", "would", "should", "has"}
_ABBREVIATION = re.compile(r"(?<![\w.])(?:mrs|mr|ms|dr|st|jr|sr|vs|etc|e\.g|i\.e)\.$", re.IGNORECASE)
_SPLIT = re.compile(r"((?<=[.!?])[ \t]+|\n+)")
_WORD = re.compile(r"[A-Za-z']+")
_PLACEHOLDER = "[" + chr(0xE100) + "-" + chr(0xE1FF) + "]"


def _words(sentence: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(sentence)]


def _lead_len(words: list[str]) -> int:
    n = 0
    while n < len(words) and words[n] in {"so", "and", "but", "okay", "ok", "well", "now", "also", "then", "hey"}:
        n += 1
    return n


def is_question(sentence: str) -> bool:
    """True for sentences shaped like a question (wh-question or aux-first yes/no question)."""
    words = _words(sentence)
    words = words[_lead_len(words):]
    if len(words) < 2:
        return False
    first, second = words[0], words[1]
    if re.fullmatch(_WH, first):
        if first == "how" and second == "come":
            return True
        # An auxiliary must come before any pronoun subject: "What time is it", "How much
        # does it cost", but not "What I did was..." or "How we got here ...".
        for w in words[1:5]:
            if w in _AUX_WORDS:
                return True
            if w in _PRONOUN:
                return False
        return False
    if first in _BE:
        return second in _SUBJECTS["is"].split("|")
    if first in _AUX_WORDS:
        allowed = _SUBJECTS["yes_no"].split("|")
        if first in _NEEDS_DETERMINER_OK:
            allowed = allowed + ["the", "a", "an"]
        return second in allowed
    return False


def add_question_marks(text: str) -> str:
    """End each question-shaped sentence with '?' (only from '.' or no punctuation)."""
    parts = _SPLIT.split(text)
    out = []
    for i in range(0, len(parts), 2):
        seg = parts[i]
        sep = parts[i + 1] if i + 1 < len(parts) else ""
        body = seg.rstrip()
        trail = seg[len(body):]
        if body and not body.endswith(("..", "?", "!")) and not _ABBREVIATION.search(body) \
                and is_question(body):
            if body.endswith("."):
                body = body[:-1] + "?"
            elif body[-1].isalnum() or re.fullmatch(_PLACEHOLDER, body[-1]):
                body += "?"
        out.append(body + trail + sep)
    return "".join(out)
