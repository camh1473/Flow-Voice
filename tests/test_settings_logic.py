import sys
import types

import pytest

from flowvoice.config import Config
from flowvoice.settings_logic import (
    escape_text,
    mic_choices,
    needs_restart,
    parse_phrases,
    rows_to_commands,
    unescape_text,
)


def test_parse_phrases_one_per_line_trimmed_deduped():
    assert parse_phrases("  Scratch that \n\nnever mind\nscratch that\n") == ["scratch that", "never mind"]


def test_phrase_only_change_needs_no_restart():
    old = Config()
    new = Config(backtrack_phrases=["oops"], filler_phrases=["x"])
    assert needs_restart(old, new) is False


def test_hotkey_model_mic_autostart_changes_need_restart():
    old = Config()
    for change in ({"ptt_key": "f9"}, {"tts_key": "f10"}, {"model": "base.en"},
                   {"mic_device": 2}, {"start_with_windows": True}):
        assert needs_restart(old, Config(**change)) is True


@pytest.mark.parametrize("s", ["\n- ", "\u2014", "\\", "a\tb", "\\n literal", "\n\n", ""])
def test_escape_round_trips(s):
    assert unescape_text(escape_text(s)) == s


def test_escape_shows_breaks_and_keeps_non_ascii():
    assert escape_text("\n- ") == "\\n- "
    assert escape_text("\t") == "\\t"
    assert escape_text("\\") == "\\\\"
    assert escape_text("\u2014") == "\u2014"


def test_unescape_leaves_unknown_escapes_and_trailing_backslash():
    assert unescape_text("\\x") == "\\x"
    assert unescape_text("end\\") == "end\\"


def test_rows_to_commands_lowercases_and_unescapes():
    assert rows_to_commands([("New Line", "\\n")]) == {"new line": "\n"}


def test_rows_to_commands_drops_blank_phrases_and_later_rows_win():
    rows = [("", "x"), ("   ", "y"), (" Comma ", ","), ("comma", ";")]
    assert rows_to_commands(rows) == {"comma": ";"}


def test_mic_choices_lists_input_devices_after_default(monkeypatch):
    fake = types.SimpleNamespace(query_devices=lambda: [
        {"name": "Speakers", "max_input_channels": 0},
        {"name": "USB Mic", "max_input_channels": 1},
    ])
    monkeypatch.setitem(sys.modules, "sounddevice", fake)
    assert mic_choices() == [("System default", None), ("1: USB Mic", 1)]


def test_mic_choices_never_raises(monkeypatch):
    def boom():
        raise OSError("no audio")
    monkeypatch.setitem(sys.modules, "sounddevice", types.SimpleNamespace(query_devices=boom))
    assert mic_choices() == [("System default", None)]
