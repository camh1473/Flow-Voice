import pytest

from flowvoice.lists import format_lists


def ph(i: int) -> str:
    return chr(0xE100 + i)


STORE = "Going to the store for:\n1. Apples\n2. Bananas\n3. Oranges"


@pytest.mark.parametrize("text, expected", [
    ("Going to the store for 1. Apples 2. Bananas 3. Oranges", STORE),
    ("Going to the store for one, apples, two, bananas, three, oranges.", STORE),
    ("Going to the store for 1. Apples, 2. Bananas, and 3. Oranges.", STORE),
    ("Going to the store for one, apples, two, bananas, and three, oranges.", STORE),
    ("Going to the store, 1. Apples 2. Bananas 3. Oranges", STORE.replace("store for", "store")),
    ("Going to the store for: 1. Apples 2. Bananas 3. Oranges", STORE),
    ("number one call Sam number two send the plans", "1. Call Sam\n2. Send the plans"),
    ("Number one, call Sam. Number two, send the plans.", "1. Call Sam\n2. Send the plans"),
    ("First, wake up. Second, make coffee. Third, ship it.", "1. Wake up\n2. Make coffee\n3. Ship it"),
    ("First wake up. Second make coffee.", "1. Wake up\n2. Make coffee"),
    ("My plan: firstly, rest; secondly, eat.", "My plan:\n1. Rest\n2. Eat"),
    ("Pick up 1. milk 2. eggs. Then call Sam.", "Pick up:\n1. Milk\n2. Eggs\n\nThen call Sam."),
    ("Todo 1) milk 2) eggs then 3) bread", "Todo:\n1. Milk\n2. Eggs\n3. Bread"),
    ("Steps 1: plan, 2: build.", "Steps:\n1. Plan\n2. Build"),
    ("1. Apples, 2. Bananas, 3. Oranges.", "1. Apples\n2. Bananas\n3. Oranges"),
    ("Get 1. milk 3. tea 2. eggs", "Get:\n1. Milk 3. tea\n2. Eggs"),
    ("Get 1. milk 2. eggs and then", "Get:\n1. Milk\n2. Eggs"),
    ("1. milk 2. eggs", "1. Milk\n2. Eggs"),
    ("Buy 1: milk, 2, eggs", "Buy:\n1. Milk\n2. Eggs"),
    ("Buy 1, milk, 2, eggs, 3, bread.", "Buy:\n1. Milk\n2. Eggs\n3. Bread"),
    ("Agenda: 1. call Dr. Smith 2. email Mr. Jones about the deal.",
     "Agenda:\n1. Call Dr. Smith\n2. Email Mr. Jones about the deal"),
    ("Bring 1. pens 2. paper, tape, etc. and more", "Bring:\n1. Pens\n2. Paper, tape, etc. and more"),
    ("Bring 1. pens 2. snacks, e.g. chips. Then go.", "Bring:\n1. Pens\n2. Snacks, e.g. chips\n\nThen go."),
])
def test_numbered_lists(text, expected):
    assert format_lists(text) == expected


@pytest.mark.parametrize("text", [
    "",
    "I need 1 apple and 2 oranges",
    "I want one, two, or three apples",
    "It costs 3.5 million",
    "It costs 3.5 million, 4.5 million.",
    "1. apples",
    "2. apples 3. pears",
    "1. milk 3. eggs",
    "Get 1. milk 3. eggs",
    "Shopping:\n- milk\n- eggs",
    "Shopping:\n1. milk\n2. eggs",
    "Call me at 5. Then 6.",
    "version 1.2 and version 2.1",
    "Chapter one, verse two",
    "Chapter one, verse two.",
    "We scored 1, 2, 3.",
    "I'll be there at 1, then 2, then 3.",
    "Second, make coffee. Third, ship it.",
    "First, make coffee.",
    "number one",
    "The first, best option.",
    "First of all, thanks. Second, the plans are late.",
    "Meet at 1:30 and 2:30.",
    "I'm number one, you're number two.",
    "Room 1, 2, and 3 are free.",
    "$1, $2.",
    "It was one, maybe two, people.",
    "At one, I eat. At two, I nap.",
    "Step one, preheat. Step two, mix.",
    "Tickets for 1, maybe 2, adults.",
    "Give me 1, I want 2. Thanks.",
    "My address is 1, Main Street, apartment 2, Houston.",
    "This is my number one priority. Number two is sales.",
    "He is the number one seller and the number two closer.",
    "Our number one goal, their number two goal.",
    "I woke up at 1. Then at 2. Then I gave up.",
    "It ended at 1. But at 2. So what.",
])
def test_unchanged(text):
    assert format_lists(text) == text


def test_placeholders_pass_through_items_untouched():
    text = f"Send 1. {ph(0)} to Sam 2. the plans"
    assert format_lists(text) == f"Send:\n1. {ph(0)} to Sam\n2. The plans"


def test_placeholder_only_item_invalidates_list():
    text = f"Send 1. {ph(0)} 2. the plans"
    assert format_lists(text) == text


def test_placeholder_is_never_a_marker():
    text = f"Send {ph(1)}. apples {ph(2)}. pears"
    assert format_lists(text) == text


def test_newline_in_last_item_starts_tail():
    text = "Buy 1. milk 2. eggs\nSee you soon."
    assert format_lists(text) == "Buy:\n1. Milk\n2. Eggs\n\nSee you soon."


@pytest.mark.parametrize("text", [
    "Going to the store for 1. Apples 2. Bananas 3. Oranges",
    "Pick up 1. milk 2. eggs. Then call Sam.",
    "number one call Sam number two send the plans",
    "First, wake up. Second, make coffee. Third, ship it.",
    "I want one, two, or three apples",
    "Going to the store for one, apples, two, bananas, three, oranges.",
    "Agenda: 1. call Dr. Smith 2. email Mr. Jones about the deal.",
    "This is my number one priority. Number two is sales.",
    "I woke up at 1. Then at 2. Then I gave up.",
    "It was one, maybe two, people.",
])
def test_idempotent(text):
    once = format_lists(text)
    assert format_lists(once) == once
