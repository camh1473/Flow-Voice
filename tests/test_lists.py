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


def test_placeholder_only_item_is_an_item():
    text = f"Send 1. {ph(0)} 2. the plans"
    assert format_lists(text) == f"Send:\n1. {ph(0)}\n2. The plans"


def test_placeholder_only_numbered_items():
    text = f"1. {ph(0)} 2. {ph(1)}"
    assert format_lists(text) == f"1. {ph(0)}\n2. {ph(1)}"


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


BULLETS = "\n- Apples\n- Bananas\n- Oranges"


@pytest.mark.parametrize("text, expected", [
    ("Shopping list: apples, bananas, and oranges.", "Shopping list:" + BULLETS),
    ("Please add the following milk, eggs, and bread", "Please add the following:\n- Milk\n- Eggs\n- Bread"),
    ("Buy the following: apples, bananas, oranges", "Buy the following:" + BULLETS),
    ("Here is a list of: apples, bananas, oranges", "Here is a list of:" + BULLETS),
    ("Here is my list of: apples, bananas, oranges", "Here is my list of:" + BULLETS),
    ("Shopping list, milk, eggs, and bread.", "Shopping list:\n- Milk\n- Eggs\n- Bread"),
    ("My shopping list, milk, eggs, and bread.", "My shopping list:\n- Milk\n- Eggs\n- Bread"),
    ("Okay, shopping list, milk, eggs, and bread.", "Okay, shopping list:\n- Milk\n- Eggs\n- Bread"),
    ("So our agenda, budget, hiring, and sales.", "So our agenda:\n- Budget\n- Hiring\n- Sales"),
    ("Today's agenda, budget, hiring, and sales.", "Today's agenda:\n- Budget\n- Hiring\n- Sales"),
    ("Hi Sam. Shopping list, milk, eggs, bread.", "Hi Sam. Shopping list:\n- Milk\n- Eggs\n- Bread"),
    ("To-do list, call Sam, send the plans, and book the lender.",
     "To-do list:\n- Call Sam\n- Send the plans\n- Book the lender"),
    ("Things to do, call Sam, send the plans, and book the lender.",
     "Things to do:\n- Call Sam\n- Send the plans\n- Book the lender"),
    ("Things I need, milk, eggs, and bread.", "Things I need:\n- Milk\n- Eggs\n- Bread"),
    ("Agenda, budget, hiring, and sales.", "Agenda:\n- Budget\n- Hiring\n- Sales"),
    ("Ingredients, flour, sugar, eggs, and butter.", "Ingredients:\n- Flour\n- Sugar\n- Eggs\n- Butter"),
    ("Items, pens, cups, and boxes.", "Items:\n- Pens\n- Cups\n- Boxes"),
    ("A list of, pens, cups, and boxes.", "A list of:\n- Pens\n- Cups\n- Boxes"),
    ("The following, milk, eggs, and bread.", "The following:\n- Milk\n- Eggs\n- Bread"),
    ("Shopping list, family pack, jelly, and supply bags.",
     "Shopping list:\n- Family pack\n- Jelly\n- Supply bags"),
    ("My to-do list: apples, bananas, oranges", "My to-do list:" + BULLETS),
    ("My to do list: apples, bananas, oranges", "My to do list:" + BULLETS),
    ("My todo list: apples, bananas, oranges", "My todo list:" + BULLETS),
    ("Things to do: apples, bananas, oranges", "Things to do:" + BULLETS),
    ("Things I need: apples, bananas, oranges", "Things I need:" + BULLETS),
    ("Agenda: apples, bananas, oranges", "Agenda:" + BULLETS),
    ("Ingredients: apples, bananas, oranges", "Ingredients:" + BULLETS),
    ("Items: apples, bananas, oranges", "Items:" + BULLETS),
    ("things to do: call Sam, send the plans then book the lender",
     "things to do:\n- Call Sam\n- Send the plans\n- Book the lender"),
    ("Shopping list: milk and eggs and bread", "Shopping list:\n- Milk\n- Eggs\n- Bread"),
    ("Shopping list: milk, eggs, bread. Then I leave.", "Shopping list:\n- Milk\n- Eggs\n- Bread\n\nThen I leave."),
    ("Shopping list: milk, eggs, bread\nSee you.", "Shopping list:\n- Milk\n- Eggs\n- Bread\n\nSee you."),
    ("Agenda: call Dr. Smith, email Mr. Jones, review costs vs. budget. So long.",
     "Agenda:\n- Call Dr. Smith\n- Email Mr. Jones\n- Review costs vs. budget\n\nSo long."),
    ("Hi Sam. Shopping list: milk, eggs, bread.", "Hi Sam. Shopping list:\n- Milk\n- Eggs\n- Bread"),
    ("The agenda items: budget, hiring, sales", "The agenda items:\n- Budget\n- Hiring\n- Sales"),
    ("Items: 1,000 pens, 2,000 cups, and 5 boxes", "Items:\n- 1,000 pens\n- 2,000 cups\n- 5 boxes"),
    ("Shopping list: 1. milk 2. eggs 3. bread", "Shopping list:\n1. Milk\n2. Eggs\n3. Bread"),
    ("Things to do: 1. call Sam, 2. send plans, 3. rest.", "Things to do:\n1. Call Sam\n2. Send plans\n3. Rest"),
    ("Can you get the following milk, eggs, and bread?", "Can you get the following:\n- Milk\n- Eggs\n- Bread?"),
    ("Get the following pens, then cups, then boxes. And then rest.",
     "Get the following:\n- Pens\n- Cups\n- Boxes\n\nAnd then rest."),
    ("Please buy the following eggs, milk, bread, etc.", "Please buy the following:\n- Eggs\n- Milk\n- Bread\n- Etc."),
])
def test_bulleted_lists(text, expected):
    assert format_lists(text) == expected


@pytest.mark.parametrize("text", [
    "Shopping list: apples and bananas.",
    "Shopping list: apples, bananas.",
    "the following is a long sentence with many words, b, c",
    "things to do call Sam send the plans",
    "the agenda is clear",
    "the following day I left",
    "Shopping list:\n- milk\n- eggs\n- bread",
    "The agenda is long, boring, and late.",
    "I made a list of reasons, none good.",
    "Ingredients matter, quality matters, price matters.",
    "She has items, boxes, and bags everywhere.",
    "For the agenda, we discussed sales, hiring, and budget.",
    "The following week, Monday, Tuesday, and Friday were busy.",
    "He left the following day, came back, and slept.",
    "The following are needed, a, b, and c.",
    "We need the following are: a, b, c",
    "A list of names, dates, and places was found.",
    "The ingredients are fresh, local, and cheap.",
    "Those items are big, heavy, and expensive.",
    "My shopping list is long, messy, and lost.",
    "The to-do list grew, shrank, and grew again.",
    "Things to do in Paris, Rome, and London are endless.",
    "Things I need to say, think, and do.",
    "The agenda, the minutes, and the budget are ready.",
    "List of the day: none.",
    "Items in stock, on order, and sold out.",
    "I sorted the items, then washed them, then left.",
    "Ingredients, tools and time all matter.",
    "The following morning, we ate, drank, and slept.",
    "In the following years, sales rose, fell, and rose.",
    "Shopping list: milk, a big carton of fresh whole milk, eggs.",
    "Agenda: budget, , hiring",
    "Agenda: budget, and, hiring",
    "the following",
    "Agenda:",
    "Items: one thing.",
    "Check the following link, it is new, and good.",
    "Send the following to Sam, Bob, and Ann.",
    "I read the following, liked it, and shared it.",
    "Add it to my shopping list, then call me, then leave.",
    "My to-do list keeps growing, slowly, and surely.",
    "Things to do today, tomorrow, and next week.",
    "Things I need to buy are eggs, milk, and bread.",
    "What's on the agenda, Sam, Bob, and Ann?",
    "The items, the boxes, and the bags are gone.",
    "Return the items, then the boxes, then the bags.",
    "Items like pens, cups, and boxes are cheap.",
    "The following items, pens, cups and boxes.",
    # Review round 2: noun cues with a comma only when they begin the sentence.
    "The agenda, the minutes, and the budget are ready.",
    "My shopping list, honestly, was too long, messy, and lost.",
    "The agenda, as always, ran long, late, and loud.",
    "Things I need, I buy, fast, and cheap.",
    "Please check our agenda, budget, hiring, and sales.",
    "Okay so the agenda, budget, hiring, and sales.",
    # Review round 2: "a list of" / "list of" no longer take the colon-free form.
    "I made a list of apples, bananas, and oranges.",
    "Make a list of apples, bananas, oranges",
    "Dr. Smith gave me a list of pills, creams, and drops.",
    "He made a list of names, addresses and phone numbers and sent it.",
    "I got a list of complaints, mostly small, but some big.",
    "There is a list of reasons, good, bad, and ugly.",
    # Review round 2: "the following" mid-sentence takes no comma; head nouns, adverbs, conjunctions cancel.
    "Please add the following, milk, eggs, and bread.",
    "I need the following, honestly, truly, and deeply.",
    "Follow the following instructions carefully, slowly, and calmly.",
    "I agree with the following points, mostly, and partly.",
    "I'll do it the following way, quickly, and quietly.",
    "Consider the following scenario, bad, worse, and worst.",
    "Please review the following, thanks, Sam, and Ann.",
    "Use the following, a pen, a pad, and a laptop.",
    "Get the following milk, eggs, but not bread.",
    "Shopping list, quickly, milk, and eggs.",
    "The following, slowly, milk, and eggs.",
    # Any form: an item starting with a conjunction cancels the list.
    "Shopping list: one, two, or three apples.",
    "Shopping list, one, two, or three apples.",
    "Agenda: budget, hiring, yet sales.",
])
def test_bullets_unchanged(text):
    assert format_lists(text) == text


def test_bullet_without_punctuation_is_a_known_limit():
    # Known limit: without a comma or colon after the cue there is no reliable split point.
    text = "My shopping list milk eggs and bread."
    assert format_lists(text) == text


def test_bullet_placeholders_pass_through():
    text = f"Shopping list: {ph(0)} milk, eggs, bread"
    assert format_lists(text) == f"Shopping list:\n- {ph(0)} milk\n- Eggs\n- Bread"


def test_bullet_placeholder_only_item_is_an_item():
    text = f"Agenda: budget, {ph(0)}, hiring"
    assert format_lists(text) == f"Agenda:\n- Budget\n- {ph(0)}\n- Hiring"


def test_bullet_placeholder_only_items_comma_form():
    text = f"Shopping list, {ph(0)}, {ph(1)}, and bread."
    assert format_lists(text) == f"Shopping list:\n- {ph(0)}\n- {ph(1)}\n- Bread"


def test_bullet_placeholders_never_count_as_words():
    text = f"Agenda: a b c d e f {ph(0)} {ph(1)}, budget, hiring"
    assert format_lists(text) == f"Agenda:\n- A b c d e f {ph(0)} {ph(1)}\n- Budget\n- Hiring"


@pytest.mark.parametrize("text, expected", [
    ("The agenda: budget, hiring, sales", "The agenda:\n- Budget\n- Hiring\n- Sales"),
    ("Agenda: really big budget, hiring, sales", "Agenda:\n- Really big budget\n- Hiring\n- Sales"),
])
def test_colon_form_keeps_working(text, expected):
    assert format_lists(text) == expected


@pytest.mark.parametrize("text", [
    "Shopping list: apples, bananas, and oranges.",
    "Please add the following milk, eggs, and bread",
    "Shopping list: milk, eggs, bread. Then I leave.",
    "things to do: call Sam, send the plans then book the lender",
    "The agenda is long, boring, and late.",
    "Shopping list: 1. milk 2. eggs 3. bread",
    "Okay, shopping list, milk, eggs, and bread.",
    "The following, milk, eggs, and bread.",
    "To-do list, call Sam, send the plans, and book the lender.",
])
def test_bullets_idempotent(text):
    once = format_lists(text)
    assert format_lists(once) == once


def _words(text: str) -> list[str]:
    return sorted(
        w for w in (t.strip(".,:;!?").lower() for t in text.replace("\n- ", " ").split())
        if w and w not in ("and", "then", "-")
    )


@pytest.mark.parametrize("text", [
    "Shopping list, milk, eggs, and bread.",
    "Okay, shopping list, milk, eggs, and bread.",
    "To-do list, call Sam, send the plans, and book the lender.",
    "Things to do: call Sam, send the plans then book the lender",
    "Please add the following milk, eggs, and bread",
    "Shopping list: milk, eggs, bread. Then I leave.",
    "The following, milk, eggs, and bread.",
])
def test_bullets_preserve_words(text):
    assert _words(format_lists(text)) == _words(text)
