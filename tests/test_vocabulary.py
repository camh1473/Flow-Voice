from flowvoice.vocabulary import apply_dictionary, glossary_prompt, is_glossary_echo


def test_prompt_format_and_order():
    assert glossary_prompt(["TBB", "Perry Homes"]) == "Glossary: TBB, Perry Homes."


def test_prompt_skips_blank_and_duplicates():
    assert glossary_prompt(["TBB", "  ", "", "tbb", "Perry"]) == "Glossary: TBB, Perry."


def test_prompt_none_when_empty():
    assert glossary_prompt([]) is None
    assert glossary_prompt(["", "  "]) is None


def test_prompt_cap_never_cuts_a_term():
    terms = [f"Term{i:03d}" + "x" * 20 for i in range(100)]
    prompt = glossary_prompt(terms)
    assert len(prompt) <= 400
    assert prompt.endswith(".")
    body = prompt[len("Glossary: "):-1].split(", ")
    assert body == terms[:len(body)]
    assert 0 < len(body) < 100


def test_term_casing():
    assert apply_dictionary("we use tbb daily", ["TBB"], {}) == "we use TBB daily"


def test_whole_word_only():
    assert apply_dictionary("many tbbs here", ["TBB"], {}) == "many tbbs here"


def test_multi_word_term():
    assert apply_dictionary("call perry homes now", ["Perry Homes"], {}) == "call Perry Homes now"


def test_fix():
    assert apply_dictionary("see perry home today", [], {"perry home": "Perry Homes"}) == "see Perry Homes today"


def test_longest_fix_first():
    fixes = {"perry": "P", "perry home": "Perry Homes"}
    assert apply_dictionary("perry home", [], fixes) == "Perry Homes"


def test_no_chaining():
    assert apply_dictionary("a", [], {"a": "b", "b": "c"}) == "b"
    assert apply_dictionary("a b", [], {"a": "b", "b": "c"}) == "b c"


def test_case_insensitive_match_exact_output():
    assert apply_dictionary("Perry HOME", [], {"perry home": "Perry Homes"}) == "Perry Homes"


def test_fix_wins_over_equal_term():
    assert apply_dictionary("tbb", ["TBB"], {"tbb": "The Big Build"}) == "The Big Build"


def test_empty_returns_text():
    assert apply_dictionary("hello there", [], {}) == "hello there"


def test_special_characters_literal():
    assert apply_dictionary("i like c++ and a.b", ["C++", "a.b"], {}) == "i like C++ and a.b"
    assert apply_dictionary("axb and c++", ["a.b"], {}) == "axb and c++"
    assert apply_dictionary("use .net now", [".NET"], {}) == "use .NET now"


def test_idempotent():
    once = apply_dictionary("tbb and perry home", ["TBB"], {"perry home": "Perry Homes"})
    assert apply_dictionary(once, ["TBB"], {"perry home": "Perry Homes"}) == once


def test_echo_detected():
    terms = ["TBB", "Perry Homes"]
    assert is_glossary_echo("Glossary: TBB, Perry Homes.", terms)
    assert is_glossary_echo("TBB, Perry Homes", terms)
    assert is_glossary_echo("tbb", terms)


def test_not_echo():
    terms = ["TBB", "Perry Homes"]
    assert not is_glossary_echo("TBB is great", terms)
    assert not is_glossary_echo("", terms)
    assert not is_glossary_echo("Glossary:", terms)
