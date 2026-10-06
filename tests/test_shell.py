import threading

import pytest
from PySide6.QtCore import QCoreApplication, QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from flowvoice.__main__ import AiProbe, ai_status_handler, ai_toast, make_ai_service, make_on_save
from flowvoice.config import Config
from flowvoice.history import HistoryEntry
from flowvoice.ui import shell as shell_mod
from flowvoice.ui.shell import (
    HookGroup,
    Shell,
    apply_saved_config,
    restart_process,
    wire_capture,
)

MICS = [("System default", None)]


class FakeHistory:
    def __init__(self):
        self.rows = []

    def list(self, query=""):
        return list(self.rows)


class FakeHook:
    def __init__(self):
        self.enabled = False
        self.calls = []

    def enable(self):
        self.enabled = True
        self.calls.append("enable")

    def disable(self):
        self.enabled = False
        self.calls.append("disable")


class FakeTalk:
    def __init__(self, state="idle"):
        self.state = state


class FakeApp:
    def __init__(self, state="idle"):
        self.talk = FakeTalk(state)
        self.keys = []
        self.applied = []

    def other_key(self, name):
        self.keys.append(name)

    def apply_config(self, cfg):
        self.applied.append(cfg)


@pytest.fixture
def make_shell(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(shell_mod, "_quit_qt", lambda: None)
    made = []

    def make(config=None, history=None, first_run=False, ai_probe=None):
        settings = QSettings(str(tmp_path / "window.ini"), QSettings.IniFormat)
        s = Shell(config or Config(), history, settings=settings, mics=MICS, dark=False,
                  first_run=first_run, ai_probe=ai_probe)
        made.append(s)
        return s

    yield make
    for s in made:
        s.shutdown()
        s.pill.close()


def _entry(text="Hello there, world.", id=7):
    return HistoryEntry(id, "2026-10-05T09:30:00", "hello there world", text, "notepad.exe")


def _body_color(pill):
    rect = pill.capsule_rect()
    x = int(rect.left() + rect.height() * 0.3)
    return pill.grab().toImage().pixelColor(x, int(rect.center().y()))


def test_shell_constructs(make_shell):
    s = make_shell()
    assert s.ui is not None and s.pill is not None and s.window is not None
    assert s.tray is not None


def test_ui_state_from_worker_thread_turns_pill_blue(make_shell):
    s = make_shell()
    t = threading.Thread(target=s.ui.set_state, args=("recording",))
    t.start()
    t.join()
    QCoreApplication.processEvents()
    c = _body_color(s.pill)
    assert c.blue() > 200 and c.red() < 80
    assert s.window.home.state() == "recording"


def test_add_history_shows_on_home_and_history(make_shell):
    s = make_shell(history=FakeHistory())
    s.ui.add_history(_entry("Dictated words."))
    QCoreApplication.processEvents()
    assert s.window.home.entry_label.text() == "Dictated words."
    assert s.window.history_view.row_count() == 1


def test_pill_click_calls_on_toggle(make_shell):
    s = make_shell()
    calls = []
    s.on_toggle = lambda: calls.append("toggle")
    center = s.pill.capsule_rect().center().toPoint()
    QTest.mouseClick(s.pill, Qt.LeftButton, Qt.NoModifier, QPoint(center.x(), center.y()))
    assert calls == ["toggle"]


def test_home_toggle_and_tray_start_stop_call_on_toggle(make_shell):
    s = make_shell()
    calls = []
    s.on_toggle = lambda: calls.append("toggle")
    s.window.home.toggle_clicked.emit()
    s.start_stop_action.trigger()
    assert calls == ["toggle", "toggle"]


def test_toggle_before_app_ready_notifies_still_loading(make_shell):
    s = make_shell()
    shown = []
    s.ui.message.connect(shown.append)
    s.window.home.toggle_clicked.emit()
    s.start_stop_action.trigger()
    assert shown == ["Still loading the speech model...", "Still loading the speech model..."]


def test_first_run_shows_window(make_shell):
    s = make_shell(first_run=True)
    assert s.window.isVisible()


def test_not_first_run_keeps_window_hidden(make_shell):
    s = make_shell()
    assert not s.window.isVisible()


def test_show_window_request_from_worker_opens_settings_page(make_shell):
    s = make_shell()
    t = threading.Thread(target=s.ui.show_window, args=("Settings",))
    t.start()
    t.join()
    QCoreApplication.processEvents()
    assert s.window.isVisible()
    assert s.window.pages.currentWidget() is s.window.settings_view


def test_restart_process_order():
    order = []
    restart_process(shutdown=lambda: order.append("shutdown"),
                    spawn=lambda: order.append("spawn"),
                    exit=lambda: order.append("exit"),
                    notify=lambda m: order.append(("notify", m)))
    assert order == ["shutdown", "spawn", "exit"]


def test_restart_process_exits_even_when_spawn_fails():
    order = []

    def spawn():
        order.append("spawn")
        raise OSError("no python")

    def notify(m):
        order.append(("notify", m))
        raise RuntimeError("tray gone")

    restart_process(shutdown=lambda: order.append("shutdown"), spawn=spawn,
                    exit=lambda: order.append("exit"), notify=notify)
    assert order == ["shutdown", "spawn", ("notify", "Restart failed: no python"), "exit"]


def test_restart_process_exits_even_when_shutdown_fails():
    order = []

    def shutdown():
        raise RuntimeError("boom")

    restart_process(shutdown=shutdown, spawn=lambda: order.append("spawn"),
                    exit=lambda: order.append("exit"), notify=lambda m: None)
    assert order.count("exit") == 1 and order[-1] == "exit"


def test_tray_menu_has_open_start_stop_quit(make_shell):
    s = make_shell()
    texts = [a.text() for a in s.tray.contextMenu().actions() if not a.isSeparator()]
    assert texts == ["Open", "Start dictation", "Quit"]
    s.ui.set_state("recording")
    QCoreApplication.processEvents()
    assert s.start_stop_action.text() == "Stop dictation"


def test_tray_icon_is_drawn(make_shell):
    s = make_shell()
    assert not s.tray.icon().isNull()


def test_tick_timer_calls_on_tick(make_shell):
    s = make_shell()
    ticks = []
    s.on_tick = lambda: ticks.append(1)
    assert s.tick_timer.interval() == 200 and s.tick_timer.isActive()
    s.tick_timer.timeout.emit()
    assert ticks == [1]


def test_apply_config_scales_pill_and_hides_idle(make_shell):
    s = make_shell()
    width = s.pill.width()
    assert s.pill.isVisible()
    s.apply_config(Config(ui_scale=1.5, pill_always_visible=False))
    assert s.pill.width() > width
    assert not s.pill.isVisible()


def test_quit_runs_on_quit_then_saves_geometry_then_quits(make_shell, tmp_path, monkeypatch):
    order = []
    monkeypatch.setattr(shell_mod, "_quit_qt", lambda: order.append("qt_quit"))
    s = make_shell()
    s.on_quit = lambda: order.append("on_quit")
    s.window.show()
    s.window.resize(700, 520)
    s.quit()
    settings = QSettings(str(tmp_path / "window.ini"), QSettings.IniFormat)
    assert settings.value("geometry") is not None
    assert order == ["on_quit", "qt_quit"]
    assert not s.window.isVisible()


def test_quit_saves_geometry_when_window_never_shown(make_shell, tmp_path):
    s = make_shell()
    s.quit()
    settings = QSettings(str(tmp_path / "window.ini"), QSettings.IniFormat)
    assert settings.value("geometry") is not None


def test_hook_group_enable_pause_resume_close():
    group = HookGroup()
    a, b = FakeHook(), FakeHook()
    group.set([a, b])
    assert a.enabled and b.enabled
    group.pause()
    assert not a.enabled and not b.enabled
    group.resume()
    assert a.enabled and b.enabled
    group.close()
    assert not a.enabled and not b.enabled
    group.resume()
    assert not a.enabled
    c = FakeHook()
    group.set([c])
    assert not c.enabled


def test_hook_group_set_while_paused_waits_for_resume():
    group = HookGroup()
    group.pause()
    a = FakeHook()
    group.set([a])
    assert not a.enabled
    group.resume()
    assert a.enabled


def test_hook_group_rolls_back_partial_enable():
    class Broken(FakeHook):
        def enable(self):
            raise ValueError("bad key")

    group = HookGroup()
    a = FakeHook()
    with pytest.raises(ValueError):
        group.set([a, Broken()])
    assert not a.enabled


def test_capture_pauses_hooks_and_cancels_active_take(make_shell):
    s = make_shell()
    group = HookGroup()
    hook = FakeHook()
    group.set([hook])
    app = FakeApp("latched")
    wire_capture(s.window, group, lambda: app)
    s.window.capture_started.emit()
    assert not hook.enabled
    assert app.keys == ["esc"]
    s.window.capture_finished.emit()
    assert hook.enabled


def test_capture_does_not_cancel_when_idle_or_app_missing(make_shell):
    s = make_shell()
    group = HookGroup()
    app = FakeApp("idle")
    apps = [None]
    wire_capture(s.window, group, lambda: apps[0])
    s.window.capture_started.emit()
    s.window.capture_finished.emit()
    apps[0] = app
    s.window.capture_started.emit()
    assert app.keys == []


def _saver(log):
    return lambda cfg: log.append(("save", cfg))


def test_saved_config_restart_path():
    log, app = [], FakeApp()
    old, new = Config(), Config(ptt_key="f9")
    result = apply_saved_config(old, new, save=_saver(log), app=app,
                                apply_ui=lambda c: log.append(("ui", c)),
                                restart=lambda: log.append(("restart",)),
                                notify=lambda m: log.append(("notify", m)))
    assert result == "restart"
    assert log == [("save", new), ("notify", "Applying settings..."), ("restart",)]
    assert app.applied == []


def test_saved_config_live_path():
    log, app = [], FakeApp()
    old, new = Config(), Config(ui_scale=1.3, hands_free=False)
    result = apply_saved_config(old, new, save=_saver(log), app=app,
                                apply_ui=lambda c: log.append(("ui", c)),
                                restart=lambda: log.append(("restart",)),
                                notify=lambda m: log.append(("notify", m)))
    assert result == "live"
    assert app.applied == [new]
    assert log == [("save", new), ("ui", new), ("notify", "Settings saved")]


def test_saved_config_live_path_before_app_is_ready():
    log = []
    new = Config(ui_scale=1.2)
    result = apply_saved_config(Config(), new, save=_saver(log), app=None,
                                apply_ui=lambda c: log.append(("ui", c)),
                                restart=lambda: log.append(("restart",)),
                                notify=lambda m: log.append(("notify", m)))
    assert result == "live"
    assert ("ui", new) in log


def test_saved_config_save_failure_notifies_and_stops():
    log, app = [], FakeApp()

    def boom(cfg):
        raise OSError("disk full")

    result = apply_saved_config(Config(), Config(ptt_key="f9"), save=boom, app=app,
                                apply_ui=lambda c: log.append(("ui", c)),
                                restart=lambda: log.append(("restart",)),
                                notify=lambda m: log.append(("notify", m)))
    assert result == "failed"
    assert log == [("notify", "Could not save settings: disk full")]
    assert app.applied == []


def test_apply_config_toggles_the_history_banner(make_shell):
    s = make_shell(config=Config(save_history=False), history=FakeHistory())
    assert s.window.history_view.banner.isVisibleTo(s.window.history_view)
    s.apply_config(Config(save_history=True))
    assert not s.window.history_view.banner.isVisibleTo(s.window.history_view)
    s.apply_config(Config(save_history=False))
    assert s.window.history_view.banner.isVisibleTo(s.window.history_view)


class FakeSettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.statuses = []

    def set_ai_status(self, status, detail):
        self.statuses.append((threading.current_thread(), status, detail))


def test_shell_forwards_ai_status_to_settings_on_the_main_thread(make_shell):
    s = make_shell()
    assert s.window.settings_view._ai_probe is None
    page = FakeSettingsPage()
    s.window.set_settings_view(page)
    page.statuses.clear()
    worker = threading.Thread(target=lambda: s.ui.set_ai_status("missing model", "ollama pull m"))
    worker.start()
    worker.join()
    assert page.statuses == []
    QCoreApplication.processEvents()
    assert page.statuses == [(threading.main_thread(), "missing model", "ollama pull m")]


def test_shell_passes_ai_probe_to_settings(make_shell):
    probe = object()
    s = make_shell(ai_probe=probe)
    assert s.window.settings_view._ai_probe is probe


class FakeAi:
    def __init__(self):
        self.configured = []

    def configure(self, cfg):
        self.configured.append(cfg)


def test_saved_config_before_app_is_ready_configures_ai_directly():
    ai, log = FakeAi(), []
    new = Config(ai_enabled=True)
    result = apply_saved_config(Config(), new, save=_saver(log), app=None, ai=ai,
                                apply_ui=lambda c: None, restart=lambda: None,
                                notify=lambda m: None)
    assert result == "live"
    assert ai.configured == [new]


def test_saved_config_with_app_leaves_ai_to_the_app():
    ai, app, log = FakeAi(), FakeApp(), []
    new = Config(ai_enabled=True)
    apply_saved_config(Config(), new, save=_saver(log), app=app, ai=ai,
                       apply_ui=lambda c: None, restart=lambda: None, notify=lambda m: None)
    assert app.applied == [new]
    assert ai.configured == []


def test_saved_config_restart_does_not_configure_ai():
    ai, log = FakeAi(), []
    apply_saved_config(Config(), Config(ptt_key="f9"), save=_saver(log), app=None, ai=ai,
                       apply_ui=lambda c: None, restart=lambda: None, notify=lambda m: None)
    assert ai.configured == []


def test_saved_config_failed_save_does_not_configure_ai():
    ai = FakeAi()

    def boom(cfg):
        raise OSError("disk full")

    apply_saved_config(Config(), Config(ai_enabled=True), save=boom, app=None, ai=ai,
                       apply_ui=lambda c: None, restart=lambda: None, notify=lambda m: None)
    assert ai.configured == []


@pytest.mark.parametrize("prev, status, detail, enabled, expected", [
    ("warming", "unavailable", "Ollama is not running and could not be started", True,
     "AI polish unavailable: Ollama is not running and could not be started"),
    ("ready", "unavailable", "Could not reach the local AI server", True,
     "AI polish unavailable: Could not reach the local AI server"),
    ("warming", "missing model", "ollama pull qwen3.5:2b-q4_K_M", True,
     "AI model not installed. Run: ollama pull qwen3.5:2b-q4_K_M"),
    ("off", "warming", "", True, None),
    ("warming", "ready", "", True, None),
    ("ready", "off", "", True, None),
    ("unavailable", "unavailable", "x", True, None),
    ("missing model", "missing model", "ollama pull m", True, None),
    ("warming", "unavailable", "x", False, None),
    ("warming", "missing model", "ollama pull m", False, None),
])
def test_ai_toast_table(prev, status, detail, enabled, expected):
    assert ai_toast(prev, status, detail, enabled=enabled) == expected


class FakeUi:
    def __init__(self):
        self.statuses = []
        self.messages = []

    def set_ai_status(self, status, detail):
        self.statuses.append((status, detail))

    def notify(self, message):
        self.messages.append(message)


def test_ai_status_handler_forwards_every_status_and_toasts_once():
    ui, enabled = FakeUi(), [True]
    on_status = ai_status_handler(lambda: ui, lambda: enabled[0])
    for status, detail in [("warming", ""), ("unavailable", "down"),
                           ("warming", ""), ("unavailable", "down")]:
        on_status(status, detail)
    assert ui.statuses == [("warming", ""), ("unavailable", "down"),
                           ("warming", ""), ("unavailable", "down")]
    assert ui.messages == ["AI polish unavailable: down"]


def test_ai_status_handler_toasts_again_after_ai_is_switched_off_and_on():
    ui = FakeUi()
    on_status = ai_status_handler(lambda: ui, lambda: True)
    for status, detail in [("warming", ""), ("missing model", "ollama pull m"), ("off", ""),
                           ("warming", ""), ("missing model", "ollama pull m")]:
        on_status(status, detail)
    assert ui.messages == ["AI model not installed. Run: ollama pull m"] * 2


def test_ai_status_handler_is_silent_when_ai_is_disabled():
    ui = FakeUi()
    on_status = ai_status_handler(lambda: ui, lambda: False)
    on_status("unavailable", "down")
    assert ui.statuses == [("unavailable", "down")]
    assert ui.messages == []


class SpyClient:
    def __init__(self, log):
        self.log = log

    def is_up(self):
        self.log.append("is_up")
        return False

    def has_model(self):
        self.log.append("has_model")
        return False

    def list_models(self):
        self.log.append("list_models")
        return ["m1"]

    def chat(self, *args, **kwargs):
        self.log.append("chat")
        return "OK"


def _spy_service(log, ui=None, enabled=lambda: True):
    def ensure(client):
        log.append("ensure")
        return True

    def start_thread(target):
        log.append("thread")

    return make_ai_service(lambda: ui or FakeUi(), enabled,
                           client_factory=lambda cfg: SpyClient(log), ensure=ensure,
                           start_thread=start_thread)


def test_ai_probe_never_starts_ollama():
    log = []
    probe = AiProbe(_spy_service(log))
    cfg = Config(ai_enabled=True)
    assert probe.list_models(cfg) == ["m1"]
    assert probe.test(cfg) == "Ollama is not running"
    assert "ensure" not in log
    assert "thread" not in log
    assert set(log) <= {"list_models", "is_up", "has_model", "chat"}


def test_ai_probe_exposes_only_list_models_and_test():
    probe = AiProbe(object())
    public = {n for n in dir(probe) if not n.startswith("_")}
    assert public == {"list_models", "test"}


def test_ai_disabled_at_startup_runs_nothing():
    log, ui = [], FakeUi()
    ai = _spy_service(log, ui=ui, enabled=lambda: False)
    ai.configure(Config())
    assert log == []
    assert ui.messages == []
    assert ai.status == "off"


def test_ai_enabled_at_startup_warms_once_and_reports_status():
    log, ui = [], FakeUi()
    ai = _spy_service(log, ui=ui)
    cfg = Config(ai_enabled=True)
    ai.configure(cfg)
    ai.configure(cfg)  # App(ai=...) configures again with the same config: no second warm-up
    assert log == ["thread"]
    assert ui.statuses == [("warming", "")]


class MissingModelClient:
    def has_model(self):
        return False


def _save_harness(save=lambda c: None):
    from types import SimpleNamespace
    ui = FakeUi()
    state = SimpleNamespace(cfg=Config(), ai_enabled=False)
    ai = make_ai_service(lambda: ui, lambda: state.ai_enabled,
                         client_factory=lambda cfg: MissingModelClient(), ensure=lambda c: True,
                         start_thread=lambda target: target())

    def apply(old, new):
        return apply_saved_config(old, new, save=save, app=None, apply_ui=lambda c: None,
                                  restart=lambda: None, notify=ui.notify, ai=ai)

    return ui, state, make_on_save(state, apply)


def test_enabling_ai_with_instant_warmup_failure_toasts_once():
    ui, state, on_save = _save_harness()
    new = Config(ai_enabled=True, ai_model="m:1b")
    on_save(new)
    assert ui.messages == ["AI model not installed. Run: ollama pull m:1b", "Settings saved"]
    assert state.cfg is new and state.ai_enabled is True


def test_failed_save_restores_ai_enabled_flag():
    def boom(cfg):
        raise OSError("disk full")

    ui, state, on_save = _save_harness(save=boom)
    old = state.cfg
    on_save(Config(ai_enabled=True))
    assert state.cfg is old and state.ai_enabled is False
