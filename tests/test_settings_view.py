import threading
import time

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QScrollArea

from flowvoice.cleanup import DEFAULT_BACKTRACK_PHRASES, DEFAULT_FILLER_PHRASES
from flowvoice.commands import DEFAULT_COMMANDS
from flowvoice.config import Config
from flowvoice.settings_logic import escape_text
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


# ----- Words, Snippets, Lists and AI -----

V3 = Config(dictionary_terms=["Perry Homes", "Bellaire"],
            dictionary_fixes={"perry homes": "Perry Homes", "flow boys": "Flow Voice"},
            snippets={"my sig": "Best,\nCam\t(Perry)", "my address": "123 Main St \\ Unit 4"},
            auto_lists=False, ai_enabled=True, ai_model="llama3.2:3b", ai_min_words=42,
            ai_timeout_seconds=9.5, ai_url="http://127.0.0.1:11500")


class FakeProbe:
    """Duck-typed ai_probe; optionally blocks until `release` is set."""

    def __init__(self, models=None, result="OK in 1.2 s: sample", block=False, error=None):
        self.models = models if models is not None else ["qwen3.5:2b-q4_K_M", "llama3.2:3b"]
        self.result = result
        self.error = error
        self.release = threading.Event()
        if not block:
            self.release.set()
        self.started = threading.Event()
        self.calls: list[tuple[str, Config]] = []
        self.threads: list[threading.Thread] = []

    def _enter(self, name, cfg):
        self.calls.append((name, cfg))
        self.threads.append(threading.current_thread())
        self.started.set()
        self.release.wait(5)
        if self.error is not None:
            raise self.error

    def list_models(self, cfg):
        self._enter("list_models", cfg)
        return list(self.models)

    def test(self, cfg):
        self._enter("test", cfg)
        return self.result


def _ai_view(probe=None, config=None) -> SettingsView:
    return SettingsView(config or Config(), MICS, lambda c: None, ai_probe=probe)


def test_v3_defaults_round_trip(qapp):
    assert _ai_view().to_config() == Config()


def test_v3_non_default_values_round_trip(qapp):
    assert _ai_view(config=V3).to_config() == V3


def test_v3_load_repopulates_every_new_control(qapp):
    view = _ai_view()
    view.load(V3)
    assert view.terms_edit.toPlainText() == "Perry Homes\nBellaire"
    assert ("flow boys", "Flow Voice") in view.fix_rows()
    assert ("my sig", "Best,\\nCam\\t(Perry)") in view.snippet_rows()
    assert not view.auto_lists_switch.isChecked()
    assert view.ai_switch.isChecked()
    assert view.ai_model_combo.currentText() == "llama3.2:3b"
    assert view.ai_min_words.value() == 42
    assert view.to_config() == V3
    view.load(Config())
    assert view.to_config() == Config()


def test_v3_changing_every_new_control_is_reflected(qapp):
    view = _ai_view(config=Config(ai_timeout_seconds=12.0, ai_url="http://[::1]:11434"))
    view.terms_edit.setPlainText("Perry Homes\n\n  bellaire \nperry homes\nKaty\n")
    view.add_fix_row("  Flow   BOYS ", "Flow Voice")
    view.add_fix_row("", "dropped")
    view.add_snippet_row("My Sig", "Best,\\nCam")
    view.auto_lists_switch.setChecked(False)
    view.ai_switch.setChecked(True)
    view.ai_model_combo.setEditText("  llama3.2:3b ")
    view.ai_min_words.setValue(30)
    cfg = view.to_config()
    assert cfg.dictionary_terms == ["Perry Homes", "bellaire", "Katy"]
    assert cfg.dictionary_fixes == {"flow boys": "Flow Voice"}
    assert cfg.snippets == {"my sig": "Best,\nCam"}
    assert cfg.auto_lists is False
    assert cfg.ai_enabled is True
    assert cfg.ai_model == "llama3.2:3b"
    assert cfg.ai_min_words == 30
    assert cfg.ai_timeout_seconds == 12.0
    assert cfg.ai_url == "http://[::1]:11434"


def test_v3_blank_model_keeps_loaded_value(qapp):
    view = _ai_view(config=Config(ai_model="llama3.2:3b"))
    view.ai_model_combo.setEditText("   ")
    assert view.to_config().ai_model == "llama3.2:3b"


def test_min_words_range(qapp):
    view = _ai_view()
    assert (view.ai_min_words.minimum(), view.ai_min_words.maximum()) == (5, 200)


def test_fix_and_snippet_buttons_add_and_remove_rows(qapp):
    view = _ai_view(config=V3)
    view.add_fix_button.click()
    assert view.fixes_table.rowCount() == 3
    view.fixes_table.setCurrentCell(0, 0)
    view.remove_fix_button.click()
    assert view.fixes_table.rowCount() == 2
    assert view.to_config().dictionary_fixes == {"flow boys": "Flow Voice"}
    view.add_snippet_button.click()
    assert view.snippets_table.rowCount() == 3
    view.snippets_table.setCurrentCell(0, 0)
    view.remove_snippet_button.click()
    assert view.to_config().snippets == {"my address": "123 Main St \\ Unit 4"}


def test_snippet_warnings_label_tracks_current_rows(qapp):
    view = _ai_view(config=Config(command_phrases={"new line": "\n"}))
    assert view.snippet_warnings_label.isHidden()
    row = view.add_snippet_row("new line", "x")
    assert not view.snippet_warnings_label.isHidden()
    assert "is also a spoken command" in view.snippet_warnings_label.text()
    view.snippets_table.item(row, 0).setText("my sig")
    assert view.snippet_warnings_label.isHidden()
    view.add_snippet_row("My  Sig", "y")
    assert "my sig" in view.snippet_warnings_label.text()
    assert "more than one" in view.snippet_warnings_label.text()
    view.snippets_table.setCurrentCell(1, 0)
    view.remove_snippet_button.click()
    assert view.snippet_warnings_label.isHidden()


def test_newline_only_snippet_has_no_warning(qapp):
    view = _ai_view(config=Config(command_phrases={}, snippets={"line break": "\n"}))
    assert view.snippet_warnings_label.isHidden()


def test_snippet_over_limit_warns_counting_distinct_usable_rows(qapp):
    view = _ai_view(config=Config(command_phrases={}))
    for i in range(100):
        view.add_snippet_row(f"trigger {i}", "x")
    view.add_snippet_row("trigger  0", "dup")
    view.add_snippet_row("", "")
    assert "Only the first" not in view.snippet_warnings_label.text()
    view.add_snippet_row("trigger 100", "x")
    assert not view.snippet_warnings_label.isHidden()
    assert "Only the first 100 snippets are used (101 rows)." in view.snippet_warnings_label.text()
    assert len(view.to_config().snippets) == 100
    view.snippets_table.setCurrentCell(view.snippets_table.rowCount() - 1, 0)
    view.remove_snippet_button.click()
    assert "Only the first" not in view.snippet_warnings_label.text()


def test_snippet_over_limit_warning_cleared_on_load(qapp):
    snippets = {f"trigger {i}": "x" for i in range(100)}
    view = _ai_view(config=Config(command_phrases={}, snippets=snippets))
    assert view.snippet_warnings_label.isHidden()
    view.add_snippet_row("one more", "x")
    assert not view.snippet_warnings_label.isHidden()
    view.load(Config(command_phrases={}, snippets=snippets))
    assert view.snippet_warnings_label.isHidden()


def test_snippet_blank_trigger_rows_warn(qapp):
    view = _ai_view(config=Config(command_phrases={}))
    view.add_snippet_row("", "")
    view.add_snippet_row("   ", "")
    assert view.snippet_warnings_label.isHidden()
    view.add_snippet_row("  ", "orphan text")
    view.add_snippet_row("", "\\n")
    assert ("A snippet needs a trigger phrase: 2 row(s) without one will be ignored."
            in view.snippet_warnings_label.text())


def test_words_warning_label_hidden_by_default(qapp):
    view = _ai_view(config=V3)
    assert view.words_warning_label.isHidden()


def test_terms_over_limit_warns_counting_distinct_lines(qapp):
    view = _ai_view()
    lines = [f"term {i}" for i in range(200)] + ["TERM 0", "", "  "]
    view.terms_edit.setPlainText("\n".join(lines))
    assert view.words_warning_label.isHidden()
    view.terms_edit.setPlainText("\n".join(lines + ["term 200", "term 201"]))
    assert not view.words_warning_label.isHidden()
    assert ("Only the first 200 dictionary terms are used (202 lines)."
            in view.words_warning_label.text())
    assert len(view.to_config().dictionary_terms) == 200


def test_fixes_over_limit_and_blank_key_warn(qapp):
    view = _ai_view()
    for i in range(201):
        view.add_fix_row(f"heard {i}", "x")
    assert ("Only the first 200 corrections are used (201 rows)."
            in view.words_warning_label.text())
    view.add_fix_row(" ", "Lonely")
    assert ('A correction needs a "heard as" text: 1 row(s) without one will be ignored.'
            in view.words_warning_label.text())
    view.load(Config())
    assert view.words_warning_label.isHidden()


def test_snippet_texts_survive_view_round_trip_verbatim(qapp):
    dash = chr(0x2014)
    view = _ai_view(config=Config(command_phrases={}))
    view.add_snippet_row("sig", escape_text("Best, \n\n"))
    view.add_snippet_row("literal", "a\\\\nb")
    view.add_snippet_row("slash end", "path\\")
    view.add_snippet_row("dash", f"a {dash} b")
    view.add_snippet_row("tabbed", "col1\\tcol2")
    first = view.to_config()
    assert first.snippets == {"sig": "Best, \n\n", "literal": "a\\nb", "slash end": "path\\",
                              "dash": f"a {dash} b", "tabbed": "col1\tcol2"}
    again = _ai_view(config=first)
    assert again.to_config() == first
    again.load(first)
    assert again.to_config().snippets == first.snippets


def test_snippet_warnings_follow_command_table_edits(qapp):
    view = _ai_view(config=Config(command_phrases={}, snippets={"full stop": "."}))
    assert view.snippet_warnings_label.isHidden()
    view.add_command_row("full stop", ".")
    assert "is also a spoken command" in view.snippet_warnings_label.text()


def test_refresh_fills_models_off_gui_thread_keeping_text(qapp):
    probe = FakeProbe(block=True)
    view = _ai_view(probe, Config(ai_model="my-custom:1b"))
    started = time.monotonic()
    view.refresh_models_button.click()
    assert time.monotonic() - started < 1.0
    assert probe.started.wait(2)
    assert not view.refresh_models_button.isEnabled()
    assert view.refresh_models_button.text() == "Refreshing..."
    view.refresh_models_button.click()
    view._refresh_models()
    ticks = []
    from PySide6.QtCore import QTimer
    QTimer.singleShot(0, lambda: ticks.append(1))
    assert _wait(lambda: ticks == [1])
    assert view.ai_model_combo.count() <= 1
    probe.release.set()
    assert _wait(lambda: view.ai_model_combo.count() == 2)
    assert [view.ai_model_combo.itemText(i) for i in range(2)] == probe.models
    assert view.ai_model_combo.currentText() == "my-custom:1b"
    assert view.refresh_models_button.isEnabled()
    assert view.refresh_models_button.text() == "Refresh"
    assert [c[0] for c in probe.calls] == ["list_models"]
    assert probe.threads[0] is not threading.main_thread()


def test_refresh_failure_shows_error(qapp):
    view = _ai_view(FakeProbe(error=OSError("connection refused")))
    view.refresh_models_button.click()
    assert _wait(lambda: "connection refused" in view.ai_result_label.text())
    assert view.refresh_models_button.isEnabled()


def test_test_button_runs_probe_with_unsaved_settings_off_gui_thread(qapp):
    probe = FakeProbe(block=True, result="OK in 2.3 s: Shopping list")
    view = _ai_view(probe)
    view.ai_model_combo.setEditText("llama3.2:3b")
    view.test_ai_button.click()
    assert probe.started.wait(2)
    assert not view.test_ai_button.isEnabled()
    assert view.test_ai_button.text() == "Testing..."
    view.test_ai_button.click()
    view._run_test()
    probe.release.set()
    assert _wait(lambda: view.ai_result_label.text() == "OK in 2.3 s: Shopping list")
    assert view.test_ai_button.isEnabled()
    assert view.test_ai_button.text() == "Test AI"
    assert len(probe.calls) == 1
    assert probe.calls[0][1].ai_model == "llama3.2:3b"
    assert probe.threads[0] is not threading.main_thread()


def test_test_button_shows_failure_string_and_raised_error(qapp):
    view = _ai_view(FakeProbe(result="Ollama is not running"))
    view.test_ai_button.click()
    assert _wait(lambda: view.ai_result_label.text() == "Ollama is not running")
    view2 = _ai_view(FakeProbe(error=RuntimeError("boom " + "x" * 300)))
    view2.test_ai_button.click()
    assert _wait(lambda: "boom" in view2.ai_result_label.text())
    assert len(view2.ai_result_label.text()) < 200
    assert view2.test_ai_button.isEnabled()


def test_result_after_view_destroyed_does_not_raise(qapp, monkeypatch):
    from PySide6.QtCore import QCoreApplication, QEvent
    errors = []
    monkeypatch.setattr(threading, "excepthook", lambda args: errors.append(args))
    probe = FakeProbe(block=True)
    view = _ai_view(probe)
    view.test_ai_button.click()
    view.refresh_models_button.click()
    assert probe.started.wait(2)
    view.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
    probe.release.set()
    deadline = time.monotonic() + 2
    while len(probe.threads) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    for t in probe.threads:
        t.join(2)
    _wait(lambda: False, 0.1)
    assert errors == []


def test_no_probe_disables_buttons_with_tooltip(qapp):
    view = _ai_view(None)
    for button in (view.refresh_models_button, view.test_ai_button):
        assert not button.isEnabled()
        assert button.toolTip() == "AI is not available"
    view.refresh_models_button.click()
    view._run_test()
    view._refresh_models()
    assert view.to_config() == Config()


@pytest.mark.parametrize("status, detail, expected", [
    ("ready", "", "AI: ready"),
    ("warming", "", "AI: warming up..."),
    ("off", "", "AI: off"),
    ("unavailable", "Ollama is not running", "AI: unavailable - Ollama is not running"),
    ("missing model", "ollama pull x",
     "AI: model not installed - run: ollama pull x"),
])
def test_set_ai_status_texts(qapp, status, detail, expected):
    view = _ai_view()
    view.set_ai_status(status, detail)
    assert view.ai_status_label.text() == expected


def test_set_ai_status_from_plain_thread_is_queued(qapp):
    view = _ai_view()
    before = view.ai_status_label.text()
    t = threading.Thread(target=view.set_ai_status, args=("ready", ""))
    t.start()
    t.join(2)
    assert view.ai_status_label.text() == before
    assert _wait(lambda: view.ai_status_label.text() == "AI: ready")


def test_new_cards_follow_scale(qapp):
    view = _ai_view()
    sizes = (view.ai_switch.sizeHint().width(), view.ai_model_combo.width(),
             view.fixes_table.height(), view.terms_edit.height())
    view.set_scale(1.5)
    grown = (view.ai_switch.sizeHint().width(), view.ai_model_combo.width(),
             view.fixes_table.height(), view.terms_edit.height())
    assert all(b > a for a, b in zip(sizes, grown))
    assert view.ai_min_words.width() > 0


def test_new_cards_sit_inside_scroll_area_and_save_bar_stays(qapp):
    view = _ai_view()
    body = view.scroll.widget()
    for widget in (view.terms_edit, view.fixes_table, view.snippets_table,
                   view.ai_switch, view.test_ai_button):
        assert body.isAncestorOf(widget)
    assert not body.isAncestorOf(view.save_button)


def test_ready_status_clears_a_stale_model_list_error(qapp):
    view = _ai_view()
    view._on_models([], "")
    assert view.ai_result_label.text().startswith("No installed models")
    view._apply_ai_status("ready", "")
    assert view.ai_result_label.text() == ""
    view.ai_result_label.setText("OK in 1.2 s: sample")
    view._apply_ai_status("ready", "")
    assert view.ai_result_label.text() == "OK in 1.2 s: sample"
