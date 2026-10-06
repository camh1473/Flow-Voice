"""Real-model probe: the contract of AiService.polish against a running local Ollama.

Skipped unless Ollama is already up and the model is installed. Never starts Ollama.
Asserts only the contract (no exception; None or an acceptable result), never quality
or speed. Run with `pytest tests/test_ai_real.py -s` to see latencies and outputs.
"""
import time

import pytest

from flowvoice.ai import OllamaClient
from flowvoice.ai_polish import AiService, READY, ai_acceptable, rejection_reason
from flowvoice.config import Config

pytestmark = pytest.mark.slow

URL = "http://localhost:11434"
MODEL = "qwen3.5:2b-q4_K_M"
FIRST_CALL_LIMIT = 120.0
LATER_CALL_LIMIT = 60.0

CASES = {
    "grocery list": (
        "okay so for the store I need to get two gallons of milk and a dozen eggs and some "
        "bread and about three pounds of chicken and a bag of apples and the whole thing "
        "should come to around forty dollars I think"
    ),
    "counted sequence": (
        "to set up the new printer first plug it in and turn it on then second connect it "
        "to the wifi from the little screen on the front and third install the driver from "
        "the website and print a test page to make sure it works"
    ),
    "already fine": (
        "Thanks for sending the contract over. I reviewed it last night and everything looks "
        "good to me. I will sign it this afternoon and send it back before the end of the day."
    ),
    "meeting note": (
        "Quick note from the call with Priya and Marcus. We are meeting on October 14 at 3:30 "
        "in the afternoon to go over the budget. Marcus will not be able to join in person "
        "and Priya has not seen the latest numbers yet so please send them over before then."
    ),
}


@pytest.fixture(scope="module")
def probe():
    client = OllamaClient(URL, MODEL, timeout=5.0)
    if not client.is_up():
        pytest.skip(f"Ollama is not running at {URL}")
    if not client.has_model():
        pytest.skip(f"model {MODEL} is not installed (ollama pull {MODEL})")
    cfg = Config(ai_enabled=True, ai_model=MODEL, ai_min_words=5, ai_timeout_seconds=30.0)
    service = AiService(
        client_factory=lambda c: OllamaClient(c.ai_url, c.ai_model, c.ai_timeout_seconds),
        ensure=lambda c: c.is_up(),
        start_thread=lambda target: target(),
    )
    start = time.monotonic()
    service.configure(cfg)
    print(f"\nwarm-up: {time.monotonic() - start:.1f} s, status={service.status!r} {service.detail!r}")
    assert service.status == READY
    return service, cfg


@pytest.mark.parametrize("name", list(CASES))
def test_real_model_contract(probe, name):
    service, cfg = probe
    text = CASES[name]
    start = time.monotonic()
    result = service.polish(text, cfg)
    seconds = time.monotonic() - start
    verdict = "rejected" if result is None else "accepted"
    print(f"\n[{name}] {seconds:.1f} s, {verdict} ({service.last_note})")
    print(result if result is not None else "(rejected, rule-based text is kept)")
    assert seconds < (FIRST_CALL_LIMIT if name == next(iter(CASES)) else LATER_CALL_LIMIT)
    if result is not None:
        assert ai_acceptable(text, result), rejection_reason(text, result)
