import threading

import pytest

from flowvoice.ai import AiError
from flowvoice.ai_polish import (
    EXAMPLES, SYSTEM_PROMPT, AiService, ai_acceptable, clean_ai_output, count_words,
    has_list_markup,
)
from flowvoice.config import Config

P0 = chr(0xE100)
P1 = chr(0xE101)

LONG = ("So I talked to the builder this morning and the framing on lot twelve is behind "
        "because of the rain last week. They think it will catch up by the end of the month. "
        "The buyers also asked about changing the countertops and I said I would check.")
LONG_PARAS = LONG.replace(" They think", "\n\nThey think")


class FakeClient:
    def __init__(self, *, up=True, model=True, reply="", raises=None, models=None):
        self.up, self.model, self.reply, self.raises = up, model, reply, raises
        self.models = models if models is not None else ["qwen3.5:2b-q4_K_M"]
        self.chats = []

    def is_up(self):
        return self.up

    def has_model(self):
        return self.model

    def chat(self, system, user, *, examples=None, max_tokens=512):
        self.chats.append((system, user, examples, max_tokens))
        if self.raises is not None:
            raise self.raises
        return self.reply(user) if callable(self.reply) else self.reply

    def list_models(self):
        if isinstance(self.models, Exception):
            raise self.models
        return self.models


class Harness:
    """AiService wired to fakes; threads run synchronously unless `deferred` is set."""

    def __init__(self, client=None, *, ensure_result=True, deferred=False, now=None):
        self.client = client or FakeClient(reply=LONG_PARAS)
        self.ensure_result = ensure_result
        self.factory_cfgs = []
        self.ensure_calls = 0
        self.statuses = []
        self.pending = []
        self.deferred = deferred

        def factory(cfg):
            self.factory_cfgs.append(cfg)
            return self.client

        def ensure(client):
            self.ensure_calls += 1
            return self.ensure_result

        def start_thread(target):
            if self.deferred:
                self.pending.append(target)
            else:
                target()

        kwargs = dict(client_factory=factory, ensure=ensure,
                      on_status=lambda s, d: self.statuses.append((s, d)), start_thread=start_thread)
        if now is not None:
            kwargs["now"] = now
        self.svc = AiService(**kwargs)


def on(**kw):
    return Config(ai_enabled=True, **kw)


def ready_harness(client=None):
    h = Harness(client)
    h.svc.configure(on())
    assert h.svc.status == "ready"
    return h


# ---- ai_acceptable ----

@pytest.mark.parametrize("candidate,ok", [
    (LONG, True),
    (LONG_PARAS, True),
    (LONG.replace("They think it will catch up by the end of the month. ", ""), False),
    (LONG + " The weather will be sunny all week. Interest rates are going down soon.", False),
    ("Sure, here is the text: " + LONG, False),
    ("Here is the formatted text:\n" + LONG, False),
    ("Okay: " + LONG, False),
    (LONG + " " + LONG + " " + LONG, False),
    ("", False),
    ("   \n ", False),
    (chr(0x201C) + "Here's" + chr(0x2019) + " " + LONG, False),
    ("Here" + chr(0x2019) + "s the cleaned up version. " + LONG, False),
])
def test_ai_acceptable_table(candidate, ok):
    assert ai_acceptable(LONG, candidate) is ok


def test_ai_acceptable_rebulleted_same_words():
    original = ("For the open house I need sign-in sheets, extra flyers, bottled water, "
                "doormats, a welcome banner, and some cookies for the visitors this weekend")
    candidate = ("For the open house I need:\n- Sign-in sheets\n- Extra flyers\n- Bottled water\n"
                 "- Doormats\n- A welcome banner\n- Some cookies for the visitors this weekend")
    assert ai_acceptable(original, candidate)


def test_ai_acceptable_dropping_repeated_word_counts():
    original = "this is very very very very important and I mean it today"
    assert not ai_acceptable(original, "this is very important and I mean it today")


def test_ai_acceptable_placeholders():
    original = f"Send them my link {P0} and the address {P1} before the showing tomorrow afternoon please"
    assert ai_acceptable(original, original.replace(" before", "\n\nBefore"))
    assert not ai_acceptable(original, original.replace(P0, ""))
    assert not ai_acceptable(original, original.replace(P0, P0 + P0))
    assert not ai_acceptable(original, original.replace(P1, P0))
    assert not ai_acceptable(original, original + " " + chr(0xE102))


def test_ai_acceptable_length_ignores_markers_and_newlines():
    original = "milk eggs bread butter cheese apples bananas oranges"
    candidate = "\n".join(f"- {w}" for w in original.split())
    assert ai_acceptable(original, candidate)
    numbered = "\n".join(f"{i}. {w}" for i, w in enumerate(original.split(), 1))
    assert ai_acceptable(original, numbered)


def test_ai_acceptable_preamble_allowed_when_original_has_it():
    original = "Sure, I can meet you at the model home on Thursday at ten and bring the plans with me"
    assert ai_acceptable(original, original)


def test_ai_acceptable_rejects_echoed_prompt():
    sentence = [s for s in SYSTEM_PROMPT.split("\n") if len(s.split()) >= 8][0]
    assert not ai_acceptable(LONG, LONG + "\n" + sentence)


def test_examples_pass_own_check():
    assert len(EXAMPLES) == 4
    for user, assistant in EXAMPLES:
        assert ai_acceptable(user, assistant), user
        assert user.isascii() and assistant.isascii()
    assert EXAMPLES[3][0] == EXAMPLES[3][1]
    assert "\n- " in EXAMPLES[0][1] and "\n1. " in EXAMPLES[1][1] and "\n\n" in EXAMPLES[2][1]


# ---- clean_ai_output / has_list_markup / count_words ----

@pytest.mark.parametrize("raw,expected", [
    ("  hello there \n", "hello there"),
    ('"hello there"', "hello there"),
    (chr(0x201C) + "hello there" + chr(0x201D), "hello there"),
    ('"Hi" she said "bye"', '"Hi" she said "bye"'),
    ("```\nhello\nthere\n```", "hello\nthere"),
    ("```text\nhello there\n```", "hello there"),
    ("line one\r\nline two", "line one\nline two"),
    ("<think>\nhmm\n</think>\n\nhello there", "hello there"),
    ("<think></think>```\n\"hello\"\n```", "hello"),
])
def test_clean_ai_output(raw, expected):
    assert clean_ai_output(raw) == expected


def test_clean_ai_output_non_string():
    assert clean_ai_output(None) == ""


@pytest.mark.parametrize("text,expected", [
    ("Shopping list:\n- Apples\n- Pears", True),
    ("- Apples", True),
    ("Steps:\n1. Wake up\n2. Coffee", True),
    ("I need 1 apple and 2 oranges", False),
    ("It costs 3.5 million - roughly", False),
    ("plain text", False),
])
def test_has_list_markup(text, expected):
    assert has_list_markup(text) is expected


def test_count_words_ignores_placeholders():
    assert count_words(f"call {P0} now") == 2
    assert count_words(P0 + P1) == 0


# ---- AiService.configure ----

def test_disabled_configure_starts_nothing():
    h = Harness()
    h.svc.configure(Config())
    assert h.svc.status == "off"
    assert h.ensure_calls == 0 and h.factory_cfgs == [] and h.pending == []
    assert h.statuses == []


def test_enable_warms_to_ready():
    h = Harness()
    h.svc.configure(on())
    assert h.statuses == [("warming", ""), ("ready", "")]
    assert h.ensure_calls == 1
    assert h.factory_cfgs[-1].ai_timeout_seconds == 90.0
    assert h.client.chats and h.client.chats[-1][3] <= 8


def test_reconfigure_same_settings_does_not_rewarm():
    h = ready_harness()
    h.svc.configure(on(ai_min_words=30))
    assert h.ensure_calls == 1
    assert h.statuses == [("warming", ""), ("ready", "")]


def test_missing_model():
    h = Harness(FakeClient(model=False))
    h.svc.configure(on(ai_model="llama3.2:3b"))
    assert h.statuses[-1] == ("missing model", "ollama pull llama3.2:3b")
    assert (h.svc.status, h.svc.detail) == ("missing model", "ollama pull llama3.2:3b")
    assert h.client.chats == []


def test_ensure_false_is_unavailable():
    h = Harness(ensure_result=False)
    h.svc.configure(on())
    assert h.statuses == [("warming", ""), ("unavailable", "Ollama is not running and could not be started")]


def test_client_raising_during_warmup_is_unavailable_and_service_survives():
    h = Harness(FakeClient(raises=RuntimeError("secret dictated words")))
    h.svc.configure(on())
    assert h.svc.status == "unavailable"
    assert "secret" not in h.svc.detail and h.svc.detail
    h.client.raises = AiError("Local AI timed out")
    h.svc.configure(on())
    assert (h.svc.status, h.svc.detail) == ("unavailable", "Local AI timed out")
    h.client.raises = None
    h.svc.configure(on())
    assert h.svc.status == "ready"


def test_factory_refusing_url_is_unavailable():
    def factory(cfg):
        raise AiError("AI server must be on this PC (localhost)")
    calls = []
    svc = AiService(client_factory=factory, ensure=lambda c: calls.append(c) or True,
                    start_thread=lambda t: t())
    svc.configure(on(ai_url="http://example.com:11434"))
    assert svc.status == "unavailable" and calls == []


def test_model_change_rewarms():
    h = ready_harness()
    h.svc.configure(on(ai_model="llama3.2:3b"))
    assert h.ensure_calls == 2
    assert h.factory_cfgs[-1].ai_model == "llama3.2:3b"
    assert h.statuses == [("warming", ""), ("ready", ""), ("warming", ""), ("ready", "")]


def test_newer_configure_supersedes_older_warmup():
    h = Harness(deferred=True)
    h.svc.configure(on(ai_model="a"))
    h.svc.configure(on(ai_model="b"))
    assert len(h.pending) == 2
    h.client.model = True
    h.pending[1]()
    assert h.svc.status == "ready"
    h.client.model = False
    h.pending[0]()
    assert h.svc.status == "ready"
    assert h.statuses == [("warming", ""), ("ready", "")]


def test_disable_during_warmup_ignores_result():
    h = Harness(deferred=True)
    h.svc.configure(on())
    h.svc.configure(Config())
    h.pending[0]()
    assert h.svc.status == "off"
    assert h.statuses == [("warming", ""), ("off", "")]


def test_on_status_exception_does_not_break_service():
    def boom(status, detail):
        raise RuntimeError("ui gone")
    svc = AiService(client_factory=lambda cfg: FakeClient(), ensure=lambda c: True,
                    on_status=boom, start_thread=lambda t: t())
    svc.configure(on())
    assert svc.status == "ready"


# ---- AiService.polish ----

def test_polish_returns_accepted_cleaned_result():
    h = ready_harness(FakeClient(reply="```\n" + LONG_PARAS + "\n```"))
    assert h.svc.polish(LONG, on()) == LONG_PARAS
    system, user, examples, _ = h.client.chats[-1]
    assert (system, user, examples) == (SYSTEM_PROMPT, LONG, EXAMPLES)


def test_polish_below_threshold():
    h = ready_harness()
    n = len(h.client.chats)
    assert h.svc.polish("short text here", on()) is None
    assert h.svc.polish(LONG, on(ai_min_words=200)) is None
    assert len(h.client.chats) == n


def test_polish_skips_list_markup():
    h = ready_harness()
    n = len(h.client.chats)
    assert h.svc.polish(LONG + "\n- Apples\n- Pears", on()) is None
    assert len(h.client.chats) == n


def test_polish_skips_while_warming_and_when_disabled():
    h = Harness(deferred=True)
    h.svc.configure(on())
    assert h.svc.polish(LONG, on()) is None
    assert h.client.chats == []
    h2 = ready_harness()
    n = len(h2.client.chats)
    assert h2.svc.polish(LONG, Config()) is None
    assert h2.svc.polish(LONG, on(ai_model="other:1b")) is None
    assert len(h2.client.chats) == n


def test_polish_never_calls_ensure():
    h = ready_harness()
    h.svc.polish(LONG, on())
    assert h.ensure_calls == 1


def test_polish_model_error():
    h = ready_harness()
    h.client.raises = AiError("Local AI returned an empty reply")
    assert h.svc.polish(LONG, on()) is None
    assert h.svc.last_note == "model error: Local AI returned an empty reply"
    assert h.svc.status == "ready"


def test_polish_timeout():
    h = ready_harness()
    h.client.raises = AiError("Local AI timed out")
    assert h.svc.polish(LONG, on()) is None
    assert h.svc.last_note == "timed out"
    assert h.svc.status == "ready"


def test_polish_connection_failure_marks_unavailable_once():
    h = ready_harness()
    h.client.raises = AiError("Could not reach the local AI server")
    assert h.svc.polish(LONG, on()) is None
    assert h.svc.polish(LONG, on()) is None
    assert h.svc.status == "unavailable"
    assert h.statuses.count(("unavailable", "Could not reach the local AI server")) == 1


@pytest.mark.parametrize("exc", [RecursionError(), ValueError("x"), MemoryError()])
def test_polish_any_exception_returns_none(exc):
    h = ready_harness()
    h.client.raises = exc
    assert h.svc.polish(LONG, on()) is None
    assert h.svc.last_note.startswith("model error")


def test_polish_rejection_sets_note_keeps_status():
    h = ready_harness(FakeClient(reply="Sure! The builder is behind schedule."))
    assert h.svc.polish(LONG, on()) is None
    assert h.svc.last_note.startswith("rejected")
    assert h.svc.status == "ready"
    h.client.reply = "The builder is behind. " + LONG[:40]
    assert h.svc.polish(LONG, on()) is None
    assert h.svc.last_note == "rejected: dropped words"


def test_polish_preserves_placeholder():
    text = LONG + f" Here is my link {P0} for later."
    h = ready_harness(FakeClient(reply=lambda user: user.replace(" They think", "\n\nThey think")))
    assert P0 in h.svc.polish(text, on())
    h.client.reply = lambda user: user.replace(P0, "")
    assert h.svc.polish(text, on()) is None
    assert "placeholder" in h.svc.last_note


def test_polish_non_string_reply():
    h = ready_harness(FakeClient(reply=None))
    assert h.svc.polish(LONG, on()) is None


def test_polish_concurrent_calls():
    h = ready_harness(FakeClient(reply=lambda user: user.replace(" They think", "\n\nThey think")))
    results, errors = [], []
    barrier = threading.Barrier(8)

    def worker():
        try:
            barrier.wait()
            for _ in range(20):
                results.append(h.svc.polish(LONG, on()))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert results == [LONG_PARAS] * 160
    assert h.svc.status == "ready" and h.svc.last_note == "accepted"


# ---- AiService.test / list_models ----

def test_test_success_format_works_when_disabled():
    ticks = iter([10.0, 11.46])
    client = FakeClient(reply=lambda user: user)
    h = Harness(client, now=lambda: next(ticks))
    result = h.svc.test(Config())
    assert result.startswith("OK in 1.5 s: ")
    assert len(result) <= len("OK in 1.5 s: ") + 80 and "\n" not in result
    assert h.ensure_calls == 0


def test_test_failures():
    h = Harness(FakeClient(up=False))
    assert h.svc.test(Config()) == "Ollama is not running"
    h.client.up, h.client.model = True, False
    assert h.svc.test(Config(ai_model="x:1b")) == "model not installed: ollama pull x:1b"
    h.client.model = True
    h.client.raises = AiError("AI server returned HTTP 500")
    assert h.svc.test(Config()) == "model error: AI server returned HTTP 500"
    h.client.raises = AiError("Local AI timed out")
    assert h.svc.test(Config()) == "timed out"
    h.client.raises = RuntimeError("boom")
    assert h.svc.test(Config()).startswith("model error")
    h.client.raises = None
    h.client.reply = "Sure, here you go."
    assert h.svc.test(Config()).startswith("rejected")
    assert h.ensure_calls == 0


def test_list_models():
    h = Harness(FakeClient(models=["a:1b", "b:2b"]))
    assert h.svc.list_models(Config()) == ["a:1b", "b:2b"]
    h.client.models = AiError("Could not reach the local AI server")
    assert h.svc.list_models(Config()) == []
    svc = AiService(client_factory=lambda cfg: 1 / 0, start_thread=lambda t: t())
    assert svc.list_models(Config()) == []
    assert h.ensure_calls == 0
