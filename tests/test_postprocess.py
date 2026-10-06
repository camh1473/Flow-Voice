import threading

import pytest

from flowvoice import postprocess
from flowvoice.ai_polish import ai_acceptable
from flowvoice.config import Config
from flowvoice.postprocess import Postprocessor

LINKEDIN = "https://linkedin.com/in/cam"


def make_cfg(**kw) -> Config:
    base = dict(snippets={"my linkedin": LINKEDIN})
    base.update(kw)
    return Config(**base)


class FakeAi:
    def __init__(self, result=None, error=None, transform=None):
        self.calls = []
        self.result = result
        self.error = error
        self.transform = transform

    def polish(self, text, cfg):
        self.calls.append(text)
        if self.error:
            raise self.error
        if self.transform:
            return self.transform(text)
        return self.result


class AcceptingService:
    """Fake service that applies the real acceptance check like AiService does."""

    def __init__(self, output):
        self.output = output
        self.calls = []

    def polish(self, text, cfg):
        self.calls.append(text)
        out = self.output(text) if callable(self.output) else self.output
        return out if ai_acceptable(text, out) else None


def test_empty_text_returns_empty_without_ai():
    ai = FakeAi(result="x")
    assert Postprocessor(ai).process("", make_cfg(ai_enabled=True)) == ""
    assert ai.calls == []


def test_snippet_expands_exactly():
    assert Postprocessor().process("my linkedin.", make_cfg()) == LINKEDIN


def test_snippet_mid_text_keeps_sentence_end():
    out = Postprocessor().process("Here is my LinkedIn. Let me know if you have questions.", make_cfg())
    assert out == f"Here is {LINKEDIN}. Let me know if you have questions."


def test_snippet_protected_before_commands():
    cfg = make_cfg(snippets={"first new line": "SNIP"})
    assert Postprocessor().process("first new line", cfg) == "SNIP"


def test_commands_still_work():
    assert Postprocessor().process("hello comma new line world", make_cfg()) == "Hello,\nWorld"


def test_voice_commands_off_skips_commands():
    out = Postprocessor().process("hello new line world", make_cfg(voice_commands=False))
    assert "\n" not in out


def test_scratch_that_after_snippet_removes_it():
    out = Postprocessor().process("my linkedin. scratch that. thanks", make_cfg())
    assert out == "Thanks"


def test_dictionary_runs_after_clean_even_at_sentence_start():
    cfg = make_cfg(dictionary_terms=["TBB"])
    assert Postprocessor().process("tbb is great", cfg) == "TBB is great"


def test_dictionary_fix_applies():
    cfg = make_cfg(dictionary_fixes={"perry homes": "Perry Homes"})
    assert Postprocessor().process("call perry homes today", cfg) == "Call Perry Homes today"


def test_lists_not_formed_for_spoken_numbers():
    text = "Going to the store for one apples two bananas three oranges"
    out = Postprocessor().process(text, make_cfg())
    assert "\n" not in out


def test_lists_formed_for_marked_numbers():
    out = Postprocessor().process("Going to the store for 1. apples 2. bananas 3. oranges", make_cfg())
    assert "\n1. " in out and "\n2. " in out and "\n3. " in out


def test_auto_lists_false_skips_lists():
    out = Postprocessor().process("Going to the store for 1. apples 2. bananas 3. oranges",
                                  make_cfg(auto_lists=False))
    assert "\n" not in out


def test_stage_order(monkeypatch):
    log = []
    real_clean, real_dict, real_lists = postprocess.clean, postprocess.apply_dictionary, postprocess.format_lists
    real_expand = postprocess.expand_snippets

    def rec(name, fn):
        def wrapper(*a, **k):
            log.append(name)
            return fn(*a, **k)
        return wrapper

    monkeypatch.setattr(postprocess, "clean", rec("clean", real_clean))
    monkeypatch.setattr(postprocess, "apply_dictionary", rec("dictionary", real_dict))
    monkeypatch.setattr(postprocess, "format_lists", rec("lists", real_lists))
    monkeypatch.setattr(postprocess, "expand_snippets", rec("expand", real_expand))

    class Ai:
        def polish(self, text, cfg):
            log.append("ai")
            return None

    Postprocessor(Ai()).process("my linkedin and some words", make_cfg(ai_enabled=True))
    assert log == ["clean", "dictionary", "lists", "ai", "expand"]


def test_ai_sees_listed_text_with_placeholders():
    ai = FakeAi(result=None)
    text = "Send my linkedin for 1. apples 2. bananas 3. oranges"
    Postprocessor(ai).process(text, make_cfg(ai_enabled=True))
    assert len(ai.calls) == 1
    seen = ai.calls[0]
    assert LINKEDIN not in seen
    assert any(0xE000 <= ord(c) <= 0xF8FF for c in seen)
    assert "\n1. Apples" in seen


def test_ai_result_keeping_placeholder_expands_verbatim():
    ai = FakeAi(transform=lambda t: t.replace(" and ", "\n\nand ", 1))
    text = "please send my linkedin and then call the buyer about the closing date"
    out = Postprocessor(ai).process(text, make_cfg(ai_enabled=True))
    assert LINKEDIN in out
    assert "\n\nand " in out
    assert not any(0xE000 <= ord(c) <= 0xF8FF for c in out)


def test_ai_dropping_placeholder_rejected_and_snippet_still_expands():
    svc = AcceptingService(lambda t: "".join(c for c in t if not 0xE000 <= ord(c) <= 0xF8FF))
    text = "please send my linkedin and then call the buyer about the closing date"
    out = Postprocessor(svc).process(text, make_cfg(ai_enabled=True))
    assert out == "Please send " + LINKEDIN + " and then call the buyer about the closing date"
    assert len(svc.calls) == 1


@pytest.mark.parametrize("ai, enabled", [(None, True), (FakeAi(result="ZZZ"), False)])
def test_ai_skipped(ai, enabled):
    out = Postprocessor(ai).process("hello there world", make_cfg(ai_enabled=enabled))
    assert out == "Hello there world"
    if ai is not None:
        assert ai.calls == []


def test_ai_returning_none_keeps_rule_text():
    ai = FakeAi(result=None)
    assert Postprocessor(ai).process("hello there world", make_cfg(ai_enabled=True)) == "Hello there world"
    assert len(ai.calls) == 1


def test_ai_result_used_when_returned():
    ai = FakeAi(result="Hello there\n\nworld")
    assert Postprocessor(ai).process("hello there world", make_cfg(ai_enabled=True)) == "Hello there\n\nworld"


def test_ai_raising_keeps_rule_text():
    ai = FakeAi(error=RuntimeError("boom"))
    out = Postprocessor(ai).process("my linkedin please", make_cfg(ai_enabled=True))
    assert out == LINKEDIN + " please"


def test_ai_skipped_over_300_words():
    assert postprocess.MAX_AI_WORDS == 300
    ai = FakeAi(result="x")
    text = " ".join(f"w{i}" for i in range(301))
    Postprocessor(ai).process(text, make_cfg(ai_enabled=True, snippets={}))
    assert ai.calls == []


def test_ai_runs_at_300_words():
    ai = FakeAi(result=None)
    text = " ".join(f"w{i}" for i in range(300))
    Postprocessor(ai).process(text, make_cfg(ai_enabled=True, snippets={}))
    assert len(ai.calls) == 1


def test_placeholders_do_not_count_toward_word_limit():
    ai = FakeAi(result=None)
    text = " ".join(["my linkedin"] * 300) + " end"
    Postprocessor(ai).process(text, make_cfg(ai_enabled=True))
    assert len(ai.calls) == 1


@pytest.mark.parametrize("stage, tail", [("apply_dictionary", " tbb"), ("format_lists", " TBB")])
def test_failing_optional_stage_keeps_text(monkeypatch, stage, tail):
    def boom(*a, **k):
        raise ValueError("bad")

    monkeypatch.setattr(postprocess, stage, boom)
    cfg = make_cfg(dictionary_terms=["TBB"])
    assert Postprocessor().process("my linkedin tbb", cfg) == LINKEDIN + tail


def test_failing_clean_propagates(monkeypatch):
    def boom(*a, **k):
        raise ValueError("bad")

    monkeypatch.setattr(postprocess, "clean", boom)
    with pytest.raises(ValueError):
        Postprocessor().process("hello", make_cfg())


def test_failing_expand_strips_placeholders_keeps_text(monkeypatch):
    def boom(*a, **k):
        raise ValueError("bad")

    monkeypatch.setattr(postprocess, "expand_snippets", boom)
    assert Postprocessor().process("hello my linkedin", make_cfg()) == "Hello "


def test_foreign_private_use_char_in_snippet_kept_verbatim():
    foreign = chr(0xE100)
    cfg = Config(snippets={"my site": "a" + foreign + "b", "sig": "S"})
    assert Postprocessor().process("sig my site", cfg) == "S a" + foreign + "b"


def test_two_snippets_one_containing_others_placeholder():
    foreign = chr(0xE101)
    cfg = Config(snippets={"my site": "a" + foreign + "b", "sig": "S"})
    out = Postprocessor().process("my site then sig", cfg)
    assert out == "a" + foreign + "b then S"

def test_keyboard_interrupt_propagates():
    ai = FakeAi(error=KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        Postprocessor(ai).process("hello there world", make_cfg(ai_enabled=True))


def test_glossary():
    pp = Postprocessor()
    assert pp.glossary(make_cfg()) is None
    assert pp.glossary(make_cfg(dictionary_terms=["TBB", "Perry"])) == "Glossary: TBB, Perry."


def test_thread_safety_snippets_never_cross():
    pp = Postprocessor()
    cfg_a = Config(snippets={"snip a": "AAA-expansion"})
    cfg_b = Config(snippets={"snip b": "BBB-expansion", "other thing": "CCC"})
    results = {"a": [], "b": []}
    barrier = threading.Barrier(2)

    def run(key, cfg, text):
        barrier.wait()
        for _ in range(200):
            results[key].append(pp.process(text, cfg))

    ta = threading.Thread(target=run, args=("a", cfg_a, "hello snip a there"))
    tb = threading.Thread(target=run, args=("b", cfg_b, "hello snip b there"))
    ta.start()
    tb.start()
    ta.join()
    tb.join()
    assert set(results["a"]) == {"Hello AAA-expansion there"}
    assert set(results["b"]) == {"Hello BBB-expansion there"}


def test_questions_get_a_mark_and_the_switch_turns_it_off():
    from flowvoice.config import Config
    from flowvoice.postprocess import Postprocessor
    p = Postprocessor(None)
    assert p.process("what time is it", Config()) == "What time is it?"
    assert p.process("what time is it", Config(auto_questions=False)) == "What time is it"
