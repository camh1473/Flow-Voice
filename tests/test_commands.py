import pytest

from flowvoice.commands import DEFAULT_COMMANDS, apply_commands


@pytest.mark.parametrize(
    "text, expected",
    [
        ("hello comma how are you question mark", "hello, how are you?"),
        ("Hello, comma, how are you question mark.", "Hello, how are you?"),
        ("hello new line world", "hello\nworld"),
        ("hello new paragraph world", "hello\n\nworld"),
        ("bullet point apples bullet point pears", "- apples\n- pears"),
        ("he said open quote hi there close quote", 'he said "hi there"'),
        ("call open paren home close paren now", "call (home) now"),
        ("see open bracket one close bracket", "see [one]"),
        ("done full stop next", "done. next"),
        ("john at sign gmail", "john@gmail"),
        ("my underscore name", "my_name"),
        ("dollar sign 5", "$5"),
        ("50 percent sign", "50%"),
        ("1 plus sign 1 equals sign 2", "1 + 1 = 2"),
        ("salt ampersand pepper", "salt & pepper"),
        ("wait semicolon go", "wait; go"),
        ("well ellipsis maybe", "well... maybe"),
        ("wow exclamation point", "wow!"),
        ("wow exclamation mark", "wow!"),
        ("literal comma", "comma"),
        ("literal new line", "new line"),
        ("hello NEW LINE world", "hello\nworld"),
        ("Hello Comma world", "Hello, world"),
        ("a red exclamation point", "a red!"),
        ("hello , comma world", "hello, world"),
        ("she said quote unquote", "she said quote unquote"),
        ("this has no commands at all.", "this has no commands at all."),
    ],
)
def test_apply_commands(text, expected):
    assert apply_commands(text) == expected


def test_longest_phrase_wins():
    mapping = {"exclamation": "EXC", "exclamation point": "!"}
    assert apply_commands("hi exclamation point", mapping) == "hi!"


def test_custom_phrase():
    assert apply_commands("great oops sign", {"oops sign": "!"}) == "great!"


def test_custom_phrase_spaced_normally():
    assert apply_commands("a smiley face b", {"smiley face": ":)x"}) == "a :)x b"


def test_removed_phrase_leaves_words():
    mapping = {k: v for k, v in DEFAULT_COMMANDS.items() if k != "comma"}
    assert apply_commands("hello comma world", mapping) == "hello comma world"


def test_empty_mapping_returns_text_unchanged():
    text = "hello comma world new line"
    assert apply_commands(text, {}) == text


@pytest.mark.parametrize(
    "text",
    [
        "the time period is long",
        "a trial period",
        "a trial period.",
        "a dash of salt",
        "an em dash here",
        "this colon",
        "that hyphen",
        "the slash key",
        "say quote hello",
        "see you dot",
        "the dot com bubble",
        "in that period we grew",
        "done period. next",
        "Over a long period, we grew.",
        "It was a hard period. Then we moved on.",
        "We had a great period.",
        "I had to dash to the store",
        "My colon is fine",
        "our slash key",
        "I wrote it in all caps.",
        "I wrote it in all caps and he got mad.",
        "type it with all caps",
        "the all caps style",
    ],
)
def test_guarded_words_stay_words(text):
    assert apply_commands(text) == text


@pytest.mark.parametrize(
    "text, expected",
    [
        ("I am done period", "I am done."),
        ("Done, period.", "Done."),
        ("Done. Period.", "Done."),
        ("all caps hello end caps.", "HELLO."),
        ("all caps hello, end caps world", "HELLO, world"),
        ("All caps. Hello world. End caps.", "HELLO WORLD."),
        ("All caps, hello. End caps, world", "HELLO. world"),
        ("Hi. All caps. Hello. End caps.", "Hi. HELLO."),
        ("john at sign my dash company dot com", "john@my-company.com"),
        ("done period new line next", "done.\nnext"),
        ("note colon buy milk", "note: buy milk"),
        ("well hyphen known", "well-known"),
        ("wait dash what", "wait\u2014what"),
        ("wait em dash what", "wait\u2014what"),
        ("john at sign gmail dot com", "john@gmail.com"),
        ("john at sign mail dot example dot org", "john@mail.example.org"),
        ("example dot com slash pricing", "example.com/pricing"),
        ("my underscore name", "my_name"),
        ("all caps hello end caps world", "HELLO world"),
        ("all caps hello world", "HELLO WORLD"),
        ("say all caps hi comma there end caps ok", "say HI, THERE ok"),
        ("literal period", "period"),
        ("literal dot", "dot"),
        ("literal dash", "dash"),
        ("literal all caps", "all caps"),
        ("full stop", "."),
    ],
)
def test_guarded_commands_convert(text, expected):
    assert apply_commands(text) == expected


def test_address_run_ends_at_next_plain_word():
    assert apply_commands("email john at sign gmail dot com then the dot") == (
        "email john@gmail.com then the dot"
    )


def test_address_run_overrides_word_guard():
    assert apply_commands("x at sign the dash a dot com") == "x@the-a.com"


def test_default_mapping_not_mutated():
    before = dict(DEFAULT_COMMANDS)
    apply_commands("hello comma world")
    assert DEFAULT_COMMANDS == before
