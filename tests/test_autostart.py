from flowvoice.autostart import RUN_KEY, set_autostart


class FakeReg:
    def __init__(self):
        self.values = {}

    def set(self, key, name, value):
        self.values[(key, name)] = value

    def delete(self, key, name):
        self.values.pop((key, name), None)


def test_enable_writes_run_value():
    r = FakeReg()
    set_autostart(True, command="pythonw -m flowvoice", registry=r)
    assert r.values[(RUN_KEY, "FlowVoice")] == "pythonw -m flowvoice"


def test_disable_removes_run_value_and_is_idempotent():
    r = FakeReg()
    set_autostart(True, command="x", registry=r)
    set_autostart(False, command="x", registry=r)
    set_autostart(False, command="x", registry=r)
    assert (RUN_KEY, "FlowVoice") not in r.values
