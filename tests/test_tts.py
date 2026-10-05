from flowvoice.tts import Speaker


class FakeVoice:
    def __init__(self):
        self.calls = []
        self.busy = False

    def Speak(self, text, flags):
        self.calls.append((text, flags))
        self.busy = True

    def WaitUntilDone(self, ms):
        return not self.busy


def test_speak_calls_async_with_purge():
    v = FakeVoice()
    Speaker(lambda: v).speak("hi")
    assert v.calls == [("hi", 1 | 2)]


def test_empty_text_noop():
    v = FakeVoice()
    Speaker(lambda: v).speak("  ")
    assert v.calls == []


def test_toggle_stops_when_speaking():
    v = FakeVoice()
    s = Speaker(lambda: v)
    s.toggle("hello")
    assert s.is_speaking()
    s.toggle("hello")
    assert v.calls[-1] == ("", 2)
