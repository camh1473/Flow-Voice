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
