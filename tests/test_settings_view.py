import threading
import time

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QScrollArea

from flowvoice.cleanup import DEFAULT_BACKTRACK_PHRASES, DEFAULT_FILLER_PHRASES
from flowvoice.commands import DEFAULT_COMMANDS
from flowvoice.config import Config
from flowvoice.ui.hotkey_edit import CAPTURE_TEXT, HotkeyEdit
from flowvoice.ui.main_window import MainWindow
from flowvoice.ui.settings_view import MODELS, SettingsView
from flowvoice.ui.switch import Switch

MICS = [("System default", None), ("1: USB Mic", 1), ("3: Headset", 3)]


def _view(config: Config | None = None, saved: list | None = None) -> SettingsView:
    sink = saved if saved is not None else []
    return SettingsView(config or Config(), MICS, sink.append)


def _wait(predicate, timeout: float = 2.0) -> bool:
    from PySide6.QtWidgets import QApplication
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def test_to_config_round_trips_loaded_config(qapp):
    cfg = Config(ptt_key="f9", ui_scale=1.3)
    assert _view(cfg).to_config() == cfg


def test_to_config_round_trips_non_default_values(qapp):
    cfg = Config(ptt_key="f8", tts_key="ctrl+alt+r", model="medium.en", mic_device=3,
                 start_with_windows=True, voice_commands=False, hands_free=False,
                 silence_stop_seconds=6.5, save_history=False, pill_always_visible=False,
                 ui_scale=0.85, filler_phrases=["um"], backtrack_phrases=["oops"],
                 command_phrases={"tab key": "\t"})
    assert _view(cfg).to_config() == cfg


def test_changing_every_control_is_reflected(qapp):
    view = _view()
    view.ptt_edit.set_hotkey("f9")
    view.tts_edit.set_hotkey("f10")
    view.model_combo.setCurrentIndex(MODELS.index("tiny.en"))
    view.mic_combo.setCurrentIndex(2)
    view.autostart_switch.setChecked(True)
    view.history_switch.setChecked(False)
    view.hands_free_switch.setChecked(False)
    view.pill_switch.setChecked(False)
    view.commands_switch.setChecked(False)
    view.silence_slider.setValue(15)
    view.scale_slider.setValue(30)
    view.filler_edit.setPlainText("Um\nuh\n")
    view.backtrack_edit.setPlainText("oops")
    cfg = view.to_config()
    assert cfg.ptt_key == "f9"
    assert cfg.tts_key == "f10"
    assert cfg.model == "tiny.en"
    assert cfg.mic_device == 3
    assert cfg.start_with_windows is True
    assert cfg.save_history is False
    assert cfg.hands_free is False
    assert cfg.pill_always_visible is False
    assert cfg.voice_commands is False
    assert cfg.silence_stop_seconds == 7.5
    assert cfg.ui_scale == 1.5
    assert cfg.filler_phrases == ["um", "uh"]
    assert cfg.backtrack_phrases == ["oops"]


def test_command_table_round_trips_defaults(qapp):
    assert _view().to_config().command_phrases == DEFAULT_COMMANDS


def test_command_table_shows_escaped_outputs(qapp):
    view = _view()
    rows = view.command_rows()
    assert ("bullet point", "\\n- ") in rows
    assert ("dash", "\u2014") in rows


def test_added_row_appears_in_config(qapp):
    view = _view()
    view.add_command_row("oops sign", "!")
    assert view.to_config().command_phrases["oops sign"] == "!"


def test_add_button_adds_blank_row_and_remove_button_removes_selected(qapp):
    view = _view(Config(command_phrases={"comma": ","}))
    view.add_row_button.click()
    assert view.command_table.rowCount() == 2
    view.command_table.setCurrentCell(0, 0)
    view.remove_row_button.click()
    assert view.command_table.rowCount() == 1
    assert view.to_config().command_phrases == {}


def test_reset_phrases_restores_defaults(qapp):
    view = _view(Config(filler_phrases=[], backtrack_phrases=[], command_phrases={}))
    view.reset_phrases_button.click()
    cfg = view.to_config()
    assert cfg.filler_phrases == DEFAULT_FILLER_PHRASES
    assert cfg.backtrack_phrases == DEFAULT_BACKTRACK_PHRASES
    assert cfg.command_phrases == DEFAULT_COMMANDS


def test_save_calls_on_save_with_to_config(qapp):
    saved = []
    view = _view(Config(ptt_key="f9"), saved)
    view.model_combo.setCurrentIndex(MODELS.index("base.en"))
    view.save_button.click()
    assert saved == [view.to_config()]
    assert saved[0].model == "base.en"


def test_load_replaces_every_control(qapp):
    view = _view()
    cfg = Config(ptt_key="f7", hands_free=False, ui_scale=1.6, silence_stop_seconds=1.0)
    view.load(cfg)
    assert view.to_config() == cfg


def test_unknown_mic_and_model_are_kept(qapp):
    cfg = Config(mic_device=9, model="large-v3")
    assert _view(cfg).to_config() == cfg


def test_blank_hotkey_keeps_previous(qapp):
    view = _view(Config(ptt_key="f9"))
    view.ptt_edit.set_hotkey("")
    assert view.to_config().ptt_key == "f9"


def test_page_scrolls(qapp):
    assert _view().findChild(QScrollArea) is not None


def test_set_scale_grows_switches(qapp):
    view = _view()
    small = view.hands_free_switch.sizeHint()
    view.set_scale(1.5)
    big = view.hands_free_switch.sizeHint()
    assert big.width() > small.width() and big.height() > small.height()


def test_switch_keeps_checkbox_semantics(qapp):
    switch = Switch()
    seen = []
    switch.toggled.connect(seen.append)
    switch.setChecked(True)
    assert switch.isChecked()
    switch.click()
    assert not switch.isChecked()
    assert seen == [True, False]


def test_switch_space_key_toggles(qapp):
    switch = Switch()
    assert switch.focusPolicy() & Qt.TabFocus
    QTest.keyClick(switch, Qt.Key_Space)
    assert switch.isChecked()


def test_switch_knob_moves(qapp):
    switch = Switch()
    off = switch.knob_x()
    switch.setChecked(True)
    assert switch.knob_x() > off


def test_hotkey_set_hotkey_round_trips(qapp):
    edit = HotkeyEdit()
    edit.set_hotkey("right ctrl")
    assert edit.hotkey() == "right ctrl"
    assert edit.text() == "Right Ctrl"


def test_hotkey_captured_signal_sets_field(qapp):
    edit = HotkeyEdit()
    edit.set_hotkey("right ctrl")
    edit.captured.emit("f9")
    assert edit.hotkey() == "f9"
    assert edit.text() == "F9"


def test_capture_uses_reader_thread_and_delivers(qapp):
    threads = []

    def reader(suppress=True):
        threads.append(threading.current_thread())
        return "ctrl+shift+f9"

    edit = HotkeyEdit(reader=reader)
    edit.set_hotkey("right ctrl")
    got = []
    edit.captured.connect(got.append)
    edit.begin_capture()
    assert _wait(lambda: edit.hotkey() == "ctrl+shift+f9")
    assert got == ["ctrl+shift+f9"]
    assert threads and threads[0] is not threading.main_thread()
    assert not edit.is_capturing()


def test_capture_shows_prompt_until_key(qapp):
    release = threading.Event()

    def reader(suppress=True):
        release.wait(2)
        return "f9"

    edit = HotkeyEdit(reader=reader)
    edit.set_hotkey("right ctrl")
    edit.begin_capture()
    assert edit.text() == CAPTURE_TEXT
    assert edit.is_capturing()
    release.set()
    assert _wait(lambda: edit.hotkey() == "f9")


def test_capture_escape_restores_previous(qapp):
    edit = HotkeyEdit(reader=lambda suppress=True: "esc")
    edit.set_hotkey("right ctrl")
    edit.begin_capture()
    assert _wait(lambda: not edit.is_capturing())
    assert edit.text() == "Right Ctrl"


def test_capture_escape_key_in_field_restores_previous(qapp):
    release = threading.Event()
    edit = HotkeyEdit(reader=lambda suppress=True: release.wait(2) and "f9")
    edit.set_hotkey("right ctrl")
    edit.begin_capture()
    QTest.keyClick(edit, Qt.Key_Escape)
    assert not edit.is_capturing()
    assert edit.text() == "Right Ctrl"
    release.set()
    time.sleep(0.05)
    _wait(lambda: False, 0.1)
    assert edit.hotkey() == "right ctrl"


def test_capture_failure_restores_previous(qapp):
    def reader(suppress=True):
        raise ImportError("hook unavailable")

    edit = HotkeyEdit(reader=reader)
    edit.set_hotkey("right ctrl")
    edit.begin_capture()
    assert _wait(lambda: not edit.is_capturing())
    assert edit.hotkey() == "right ctrl"


def test_capture_timeout_restores_previous(qapp):
    release = threading.Event()
    edit = HotkeyEdit(reader=lambda suppress=True: release.wait(2) and "f9", timeout_ms=30)
    edit.set_hotkey("right ctrl")
    edit.begin_capture()
    assert _wait(lambda: not edit.is_capturing())
    assert edit.text() == "Right Ctrl"
    release.set()
    _wait(lambda: False, 0.1)
    assert edit.hotkey() == "right ctrl"


def test_capture_passes_suppress_false(qapp):
    calls = []

    def reader(**kwargs):
        calls.append(kwargs)
        return "f9"

    edit = HotkeyEdit(reader=reader)
    edit.begin_capture()
    assert _wait(lambda: not edit.is_capturing())
    assert calls == [{"suppress": False}]


def _record(obj) -> list[str]:
    events: list[str] = []
    obj.capture_started.connect(lambda: events.append("started"))
    obj.capture_finished.connect(lambda: events.append("finished"))
    return events


def _blocking_edit(**kwargs) -> tuple[HotkeyEdit, threading.Event]:
    release = threading.Event()
    edit = HotkeyEdit(reader=lambda suppress=True: release.wait(2) and "f9", **kwargs)
    edit.set_hotkey("right ctrl")
    return edit, release


def test_capture_signals_on_success(qapp):
    edit = HotkeyEdit(reader=lambda suppress=True: "f9")
    events = _record(edit)
    edit.begin_capture()
    assert events == ["started"]
    assert _wait(lambda: not edit.is_capturing())
    _wait(lambda: False, 0.05)
    assert events == ["started", "finished"]


def test_capture_signals_on_reader_esc(qapp):
    edit = HotkeyEdit(reader=lambda suppress=True: "esc")
    events = _record(edit)
    edit.begin_capture()
    assert _wait(lambda: not edit.is_capturing())
    _wait(lambda: False, 0.05)
    assert events == ["started", "finished"]


def test_capture_signals_on_escape_key(qapp):
    edit, release = _blocking_edit()
    events = _record(edit)
    edit.begin_capture()
    QTest.keyClick(edit, Qt.Key_Escape)
    release.set()
    _wait(lambda: False, 0.1)
    assert events == ["started", "finished"]


def test_capture_signals_on_timeout(qapp):
    edit, release = _blocking_edit(timeout_ms=30)
    events = _record(edit)
    edit.begin_capture()
    assert _wait(lambda: not edit.is_capturing())
    release.set()
    _wait(lambda: False, 0.1)
    assert events == ["started", "finished"]


def test_capture_signals_on_focus_out(qapp):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QFocusEvent
    edit, release = _blocking_edit()
    events = _record(edit)
    edit.begin_capture()
    edit.focusOutEvent(QFocusEvent(QEvent.FocusOut, Qt.MouseFocusReason))
    assert not edit.is_capturing()
    release.set()
    _wait(lambda: False, 0.1)
    assert events == ["started", "finished"]


def test_capture_signals_on_reader_failure(qapp):
    def reader(suppress=True):
        raise OSError("hook unavailable")
    edit = HotkeyEdit(reader=reader)
    events = _record(edit)
    edit.begin_capture()
    assert _wait(lambda: not edit.is_capturing())
    _wait(lambda: False, 0.05)
    assert events == ["started", "finished"]


def test_capture_signals_on_load_cancel(qapp):
    view = _view()
    view.ptt_edit._reader = lambda suppress=True: threading.Event().wait(0.2) and "f9"
    events = _record(view.ptt_edit)
    view.ptt_edit.begin_capture()
    view.load(Config())
    assert not view.ptt_edit.is_capturing()
    _wait(lambda: False, 0.3)
    assert events == ["started", "finished"]


def test_second_begin_capture_emits_nothing_extra(qapp):
    edit, release = _blocking_edit()
    events = _record(edit)
    edit.begin_capture()
    edit.begin_capture()
    assert events == ["started"]
    release.set()
    assert _wait(lambda: not edit.is_capturing())
    _wait(lambda: False, 0.05)
    assert events == ["started", "finished"]


def test_captured_without_capture_emits_no_lifecycle(qapp):
    edit = HotkeyEdit()
    events = _record(edit)
    edit.captured.emit("f9")
    edit.cancel_capture()
    assert events == []


@pytest.mark.parametrize("name", ["ptt_edit", "tts_edit"])
def test_settings_view_forwards_capture_signals(qapp, name):
    view = _view()
    edit = getattr(view, name)
    release = threading.Event()
    edit._reader = lambda suppress=True: release.wait(2) and "f9"
    events = _record(view)
    edit.begin_capture()
    assert events == ["started"]
    edit.cancel_capture()
    release.set()
    _wait(lambda: False, 0.05)
    assert events == ["started", "finished"]


@pytest.fixture
def window(qapp, tmp_path):
    settings = QSettings(str(tmp_path / "w.ini"), QSettings.IniFormat)
    saved = []
    win = MainWindow(Config(ptt_key="f9"), None, saved.append, settings=settings, mics=MICS)
    win.saved = saved
    yield win
    win.request_quit()
    win.close()


def test_main_window_mounts_settings_view(window):
    assert isinstance(window.settings_view, SettingsView)
    window.show_page("Settings")
    assert window.pages.currentWidget() is window.settings_view
    assert window.settings_view.to_config().ptt_key == "f9"


def test_main_window_settings_save_reaches_on_save_config(window):
    window.settings_view.save_button.click()
    assert window.saved == [window.settings_view.to_config()]


def test_main_window_forwards_capture_signals(window):
    events = _record(window)
    window.settings_view.capture_started.emit()
    window.settings_view.capture_finished.emit()
    assert events == ["started", "finished"]


def test_main_window_forwards_capture_signals_after_seam_replace(window):
    events = _record(window)
    old = window.settings_view
    new = SettingsView(Config(), MICS, lambda c: None)
    window.set_settings_view(new)
    old.capture_started.emit()
    new.capture_started.emit()
    new.capture_finished.emit()
    assert events == ["started", "finished"]


def test_switch_colors_follow_theme(qapp, tmp_path):
    from PySide6.QtGui import QColor

    from flowvoice.ui import theme
    settings = QSettings(str(tmp_path / "d.ini"), QSettings.IniFormat)
    win = MainWindow(Config(), None, lambda c: None, settings=settings, mics=MICS, dark=True)
    switch = win.settings_view.hands_free_switch
    switch.ensurePolished()
    assert switch.onColor == QColor(theme.DARK["accent"])
    assert switch.offColor == QColor(theme.DARK["switch_off"])
    win.request_quit()
    win.close()


def test_main_window_apply_scale_scales_settings(window):
    before = window.settings_view.hands_free_switch.sizeHint()
    window.apply_scale(1.5)
    assert window.settings_view.hands_free_switch.sizeHint().width() > before.width()
