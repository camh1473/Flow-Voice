import pytest
from flowvoice.cleanup import clean


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
