import pytest
from flowvoice.inject import paste_text


class Fake:
    def __init__(self, clip="orig", fail_send=False):
        self.clip = clip
        self.fail_send = fail_send
        self.sent = []
        self.clip_at_send = None
        self.typed = []
        self.events = []

    def get(self):
        return self.clip

    def set(self, v):
        self.clip = v

    def send(self, keys):
        self.events.append("send")
        if self.fail_send:
            raise RuntimeError("blocked")
        self.sent.append(keys)
        self.clip_at_send = self.clip

    def type(self, t):
        self.typed.append(t)

    def sleep(self, s):
        self.events.append("sleep")


def run(f, text):
    paste_text(text, get_clip=f.get, set_clip=f.set, send=f.send,
               type_text=f.type, sleep=f.sleep)


def test_pastes_and_restores_clipboard():
    f = Fake()
    run(f, "hello")
    assert f.sent == ["ctrl+v"] and f.clip_at_send == "hello" and f.clip == "orig"


def test_empty_text_noop():
    f = Fake()
    run(f, "   ")
    assert f.sent == [] and f.events == [] and f.clip == "orig"


def test_restores_clipboard_when_send_raises():
    f = Fake(fail_send=True)
    run(f, "hello")
    assert f.typed == ["hello"] and f.clip == "orig"


def test_restore_happens_after_paste_delay():
    f = Fake()
    run(f, "hi")
    assert f.events == ["send", "sleep"]

def test_copy_selection_returns_selected_text_and_restores_clipboard():
    from flowvoice.inject import copy_selection
    state = {"clip": "orig"}

    def send(keys):
        assert keys == "ctrl+c"
        state["clip"] = "selected words"

    got = copy_selection(get_clip=lambda: state["clip"],
                         set_clip=lambda v: state.__setitem__("clip", v),
                         send=send, sleep=lambda s: None)
    assert got == "selected words" and state["clip"] == "orig"
