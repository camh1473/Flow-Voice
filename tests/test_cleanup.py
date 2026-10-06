import pytest
from flowvoice.cleanup import clean
from flowvoice.commands import DEFAULT_COMMANDS


@pytest.mark.parametrize("raw,expected", [
    ("um so uh I think we should go", "So I think we should go"),
    ("I I I want the the report", "I want the report"),
    ("hello   world .", "Hello world."),
    ("the umbrella is here", "The umbrella is here"),
    ("  ", ""),
    ("first sentence. second sentence", "First sentence. Second sentence"),
    ("Um, okay", "Okay"),
])
def test_clean(raw, expected):
    assert clean(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Send it to Bob. Scratch that. Send it to Alice.", "Send it to Alice."),
    ("Send it to Bob, scratch that, send it to Alice", "Send it to Alice"),
    ("Hi there. Send it to Bob. Never mind. Send it to Alice.", "Hi there. Send it to Alice."),
    ("Send it to Bob. Nevermind.", ""),
    ("Excuse me. Call me tomorrow", "Call me tomorrow"),
    ("Book Tuesday. Excuse me, book Wednesday.", "Book Wednesday."),
    ("Scratch that", ""),
    ("SCRATCH THAT. Hello", "Hello"),
    ("A one. B two. Scratch that. Scratch that. C three.", "C three."),
    ("I never mind waiting", "I never mind waiting"),
    ("Do you know the answer", "Do you know the answer"),
    ("It's, you know, a good idea.", "It's a good idea."),
    ("You know, I think so", "I think so"),
    ("Well, I think so", "I think so"),
    ("Basically, it works", "It works"),
])
def test_backtrack_and_fluff(raw, expected):
    assert clean(raw) == expected


def test_custom_backtrack_and_filler_lists():
    assert clean("Keep this. Drop me. Oops.", backtracks=["oops"]) == "Keep this."
    assert clean("It is, like, fine.", fillers=["like"]) == "It is fine."
    assert clean("Scratch that. Hi", backtracks=[]) == "Scratch that. Hi"


@pytest.mark.parametrize("raw,expected", [
    ("hello new line world", "Hello\nWorld"),
    ("hello new paragraph world", "Hello\n\nWorld"),
    ("yes new line yes", "Yes\nYes"),
    ("hello comma how are you question mark", "Hello, how are you?"),
    ("john at sign gmail dot com", "john@gmail.com"),
    ("the time period is long", "The time period is long"),
    ("Hi. Send it to Bob comma. Scratch that. Send it to Alice.", "Hi. Send it to Alice."),
])
def test_clean_with_commands(raw, expected):
    assert clean(raw, commands=DEFAULT_COMMANDS) == expected


def test_commands_off_by_default():
    assert clean("hello new line world") == "Hello new line world"
    assert clean("hello new line world", commands=None) == "Hello new line world"


def test_line_breaks_survive_whitespace_steps():
    assert clean("one  \n  two\t\tthree") == "One\nTwo three"
    assert clean("hello\nyes yes") == "Hello\nYes"
    assert clean("yes\nyes") == "Yes\nYes"


def test_bullet_marker_not_capitalized():
    assert clean("- apples") == "- apples"
    assert clean("list\n- apples\n- pears") == "List\n- apples\n- pears"


def test_address_like_tokens_not_capitalized():
    assert clean("see\nwww.example.com now") == "See\nwww.example.com now"
    assert clean("go to\n/tmp/x") == "Go to\n/tmp/x"
    assert clean("mail\nbob@x.com") == "Mail\nbob@x.com"


def test_command_input_with_real_newline_documented():
    # apply_commands splits on whitespace, so a pre-existing newline in its
    # input is collapsed once any command fires; the command's own break stays.
    out = clean("first line\nsecond new line third", commands=DEFAULT_COMMANDS)
    assert out == "First line second\nThird"


@pytest.mark.parametrize("raw,expected", [
    ("hello. how are you", "Hello. How are you"),
    ("yes. okay. fine", "Yes. Okay. Fine"),
    ("wait! what? no", "Wait! What? No"),
    ("send it to john@gmail.com. thanks", "Send it to john@gmail.com. Thanks"),
    ("example.com/pricing is live. ok", "example.com/pricing is live. Ok"),
])
def test_sentence_capitalization_after_punctuation(raw, expected):
    assert clean(raw, commands=None) == expected


def test_edge_line_breaks_from_commands_kept():
    assert clean("hello new line", commands=DEFAULT_COMMANDS) == "Hello\n"
    # apply_commands itself drops a leading break (commands.py, out of scope here)
    assert clean("new paragraph hello", commands=DEFAULT_COMMANDS) == "Hello"
    assert clean("\n\nhello") == "\n\nHello"
    assert clean("  ", commands=DEFAULT_COMMANDS) == ""
    assert clean(" \t ") == ""