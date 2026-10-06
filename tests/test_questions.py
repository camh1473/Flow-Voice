import pytest

from flowvoice.questions import add_question_marks


@pytest.mark.parametrize("text, expected", [
    ("What time is it.", "What time is it?"),
    ("What time is it", "What time is it?"),
    ("How much does it cost.", "How much does it cost?"),
    ("Where is the file.", "Where is the file?"),
    ("Why would I do that.", "Why would I do that?"),
    ("How come you left.", "How come you left?"),
    ("Is the door open.", "Is the door open?"),
    ("Are you coming.", "Are you coming?"),
    ("Do you have the keys.", "Do you have the keys?"),
    ("Can we meet tomorrow.", "Can we meet tomorrow?"),
    ("Could the team send it.", "Could the team send it?"),
    ("Have you seen it.", "Have you seen it?"),
    ("Okay, so what do you think.", "Okay, so what do you think?"),
    ("I am home. Are you coming. Call me.", "I am home. Are you coming? Call me."),
    ("Hello.\nwhat is the plan", "Hello.\nwhat is the plan?"),
    ("What is Perry's number. It is 555.", "What is Perry's number? It is 555."),
])
def test_questions_get_a_question_mark(text, expected):
    assert add_question_marks(text) == expected


@pytest.mark.parametrize("text", [
    "What I need is a break.",
    "What you said was fine.",
    "How we got here does not matter.",
    "Do the dishes.",
    "Do not forget the keys.",
    "Have a nice day.",
    "Have the team send it.",
    "I wonder what time it is.",
    "Please tell me where it is.",
    "Where is Dr.",
    "What time is it?",
    "Are you serious!",
    "What time is it...",
    "That is the question.",
    "",
])
def test_statements_and_finished_sentences_are_unchanged(text):
    assert add_question_marks(text) == text


def test_snippet_placeholder_after_a_question_gets_the_mark():
    ph = chr(0xE100)
    assert add_question_marks(f"What is {ph}") == f"What is {ph}?"
