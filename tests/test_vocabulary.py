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


def test_echo_full_prompt_and_prefix():
    terms = ["Perry Homes", "TBB", "Seiren"]
    assert is_glossary_echo("Glossary: Perry Homes, TBB, Seiren.", terms)
    assert is_glossary_echo("Perry Homes, TBB, Seiren", terms)
    assert is_glossary_echo("Perry Homes, TBB", terms)
    assert is_glossary_echo("Glossary: Perry Homes, TBB.", ["Perry Homes", "TBB"])
    assert is_glossary_echo("Glossary: TBB.", ["TBB"])


def test_not_echo_short_dictation():
    assert not is_glossary_echo("perry", ["Perry Homes"])
    assert not is_glossary_echo("the", ["The Big Build"])
    assert not is_glossary_echo("voice", ["Flow Voice"])
    assert not is_glossary_echo("c", ["C++"])
    assert not is_glossary_echo("Perry Homes", ["Perry Homes"])
    assert not is_glossary_echo("tbb", ["TBB", "Perry Homes"])
    assert not is_glossary_echo("TBB perry homes", ["Perry Homes", "TBB"])
    assert not is_glossary_echo("Perry Homes, TBB, hello", ["Perry Homes", "TBB", "Seiren"])
    assert not is_glossary_echo("TBB is great", ["TBB", "Perry Homes"])
    assert not is_glossary_echo("", ["TBB", "Perry Homes"])


def test_echo_glossary_word_with_any_term_prefix():
    terms = ["TBB", "Perry Homes", "Seiren"]
    assert is_glossary_echo("Glossary: TBB, Perry Homes.", terms)
    assert is_glossary_echo("Glossary: TBB.", terms)
    assert is_glossary_echo("Glossary.", terms)
    assert is_glossary_echo("Glossary:", terms)
    assert is_glossary_echo("glossary", ["TBB"])


def test_glossary_word_needs_in_order_prefix_and_a_glossary():
    terms = ["TBB", "Perry Homes", "Seiren"]
    assert not is_glossary_echo("Glossary: Perry Homes.", terms)
    assert not is_glossary_echo("Glossary: TBB, Seiren.", terms)
    assert not is_glossary_echo("Glossary: Perry Homes, TBB.", terms)
    assert not is_glossary_echo("Glossary: TBB, Perry Homes, Seiren, hello.", terms)
    assert not is_glossary_echo("The glossary.", terms)
    assert not is_glossary_echo("Glossary.", [])
    assert not is_glossary_echo("TBB", ["TBB"])


def test_longer_term_outranks_overlapping_fix():
    out = apply_dictionary("perry homes llc", ["Perry Homes LLC"], {"perry homes": "Perry Homes"})
    assert out == "Perry Homes LLC"


def test_term_inside_fix_does_not_alter_write_as():
    assert apply_dictionary("see perry home", ["perry"], {"perry home": "PERRY Homes"}) == "see PERRY Homes"


def test_prompt_exact_400_boundary():
    first = "x" * 200
    kept = glossary_prompt([first, "y" * 187])
    assert len(kept) == 400 and kept.endswith("y.")
    assert glossary_prompt([first, "y" * 188]) == f"Glossary: {first}."
