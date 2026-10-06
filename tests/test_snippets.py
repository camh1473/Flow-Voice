import pytest

from flowvoice.cleanup import clean
from flowvoice.commands import DEFAULT_COMMANDS
from flowvoice.snippets import PLACEHOLDER_BASE, expand_snippets, protect_snippets

LINK = "https://www.linkedin.com/in/cam-h"
PROFILE = "Cam H. - Sales Counselor, Perry Homes"
GITHUB = "github.com/camh"
SIGNATURE = "Thanks,\nCam\ncam@example.com | https://example.com/x?a=1&b=2."

SNIPPETS = {
    "my LinkedIn": LINK,
    "my linkedin profile": PROFILE,
    "my github": GITHUB,
    "my signature": SIGNATURE,
}


def ph(i: int) -> str:
    return chr(PLACEHOLDER_BASE + i)


def test_whole_word_case_insensitive_match():
    text, mapping = protect_snippets("send my LINKEDIN please", SNIPPETS)
    assert text == f"send {ph(0)} please"
    assert mapping == {ph(0): LINK}


@pytest.mark.parametrize("raw", [
    "army linkedin is here",
    "my linkedinx",
    "my linked in",
    "nothing to see",
])
def test_partial_words_and_unmatched_text_unchanged(raw):
    assert protect_snippets(raw, SNIPPETS) == (raw, {})


def test_longest_trigger_wins():
    text, mapping = protect_snippets("see my linkedin profile today", SNIPPETS)
    assert text == f"see {ph(0)} today"
    assert mapping == {ph(0): PROFILE}


@pytest.mark.parametrize("raw,expected", [
    ("my linkedin.", "{0}"),
    ("my linkedin,", "{0}"),
    ("here is my linkedin, thanks", "here is {0} thanks"),
    ("is it my linkedin?!", "is it {0}"),
    ("see ...my linkedin; ok", "see {0} ok"),
])
def test_touching_punctuation_absorbed(raw, expected):
    text, mapping = protect_snippets(raw, SNIPPETS)
    assert text == expected.format(ph(0))
    assert mapping == {ph(0): LINK}


def test_absorbed_punctuation_leaves_expansion_verbatim():
    text, mapping = protect_snippets("my linkedin.", SNIPPETS)
    assert expand_snippets(text, mapping) == LINK


def test_spaced_punctuation_is_not_absorbed():
    text, _ = protect_snippets("my linkedin .", SNIPPETS)
    assert text == f"{ph(0)} ."


def test_literal_keeps_trigger_words_and_drops_literal():
    assert protect_snippets("type literal my LinkedIn now", SNIPPETS) == (
        "type my LinkedIn now", {})
    assert protect_snippets("LITERAL my github.", SNIPPETS) == ("my github.", {})


def test_literal_only_applies_to_the_next_trigger():
    text, mapping = protect_snippets("literal my github and my github", SNIPPETS)
    assert text == f"my github and {ph(0)}"
    assert mapping == {ph(0): GITHUB}


def test_literal_not_before_a_trigger_is_kept():
    assert protect_snippets("a literal translation", SNIPPETS) == ("a literal translation", {})


def test_multiline_punctuation_heavy_snippet_arrives_verbatim():
    text, mapping = protect_snippets("best, my signature", SNIPPETS)
    assert expand_snippets(text, mapping) == "best, " + SIGNATURE


def test_same_trigger_twice_gets_same_placeholder():
    text, mapping = protect_snippets("my github and My GitHub", SNIPPETS)
    assert text == f"{ph(0)} and {ph(0)}"
    assert mapping == {ph(0): GITHUB}


def test_different_triggers_get_different_placeholders_in_order():
    text, mapping = protect_snippets("my github then my linkedin", SNIPPETS)
    assert text == f"{ph(0)} then {ph(1)}"
    assert mapping == {ph(0): GITHUB, ph(1): LINK}


def test_empty_snippets_returns_text_unchanged():
    assert protect_snippets("my linkedin.", {}) == ("my linkedin.", {})


def test_blank_trigger_ignored():
    assert protect_snippets("hello there", {"": "x", "  ": "y"}) == ("hello there", {})


def test_trigger_regex_characters_escaped():
    text, mapping = protect_snippets("see c++ (docs) now", {"c++ (docs)": "X"})
    assert text == f"see {ph(0)} now"
    assert mapping == {ph(0): "X"}


def test_expansion_never_rescanned():
    snippets = {"my github": "my linkedin " + ph(1), "my linkedin": LINK}
    text, mapping = protect_snippets("my github my linkedin", snippets)
    assert mapping == {ph(0): "my linkedin " + ph(1), ph(1): LINK}
    assert expand_snippets(text, mapping) == "my linkedin " + ph(1) + " " + LINK


def test_expand_with_empty_mapping_is_identity():
    assert expand_snippets("plain text", {}) == "plain text"


def _run(raw: str, **kwargs) -> str:
    captured: dict[str, str] = {}

    def hook(t: str) -> str:
        out, mapping = protect_snippets(t, SNIPPETS)
        captured.update(mapping)
        return out

    cleaned = clean(raw, before_commands=hook, commands=DEFAULT_COMMANDS, **kwargs)
    return expand_snippets(cleaned, captured)


@pytest.mark.parametrize("raw,expected", [
    ("my github my github", f"{GITHUB} {GITHUB}"),
    ("my github, my github", f"{GITHUB} {GITHUB}"),
    ("uh my github uh my github", f"{GITHUB} {GITHUB}"),
    ("my github is here", f"{GITHUB} is here"),
    ("hello. my github is here", f"Hello. {GITHUB} is here"),
    ("hello comma my github thanks", f"Hello, {GITHUB} thanks"),
    ("this is my github period", f"This is {GITHUB}."),
    ("this is my github question mark", f"This is {GITHUB}?"),
    ("my github my linkedin", f"{GITHUB} {LINK}"),
    ("my github.my linkedin", f"{GITHUB}{LINK}"),
    ("first my github new line my linkedin second", f"First {GITHUB}\n{LINK} second"),
    ("um, you know, my signature", SIGNATURE),
    ("see my linkedin profile. bye", f"See {PROFILE} bye"),
])
def test_placeholder_survives_clean(raw, expected):
    assert _run(raw) == expected


def test_placeholder_untouched_by_clean_steps():
    for i in range(3):
        p = ph(i)
        for raw in (f"{p}", f"{p} {p}", f"a. {p} b", f"x, {p}, y", f"{p}{p}",
                    f"{p} new line {p}", f"um {p} uh {p}."):
            out = clean(raw, commands=DEFAULT_COMMANDS)
            assert out.count(p) == raw.count(p), (raw, out)


def test_snippet_in_backtracked_sentence_never_appears():
    seen: list[str] = []

    def hook(t: str) -> str:
        seen.append(t)
        return protect_snippets(t, SNIPPETS)[0]

    out = clean("Here is my github. Scratch that. Here is my linkedin.",
                before_commands=hook, commands=DEFAULT_COMMANDS)
    assert seen == ["Here is my linkedin."]
    assert out == f"Here is {ph(0)}"
