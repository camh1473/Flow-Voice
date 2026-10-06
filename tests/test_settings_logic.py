import sys
import types

import pytest

from flowvoice.config import Config
from flowvoice.settings_logic import (
    escape_text,
    mic_choices,
    needs_restart,
    parse_phrases,
    rows_duplicates,
    rows_to_commands,
    rows_to_dict,
    snippet_warnings,
    terms_from_text,
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


def test_rows_to_dict_trims_drops_blank_keys_keeps_value_verbatim():
    rows = [("", "x"), ("  ", "y"), ("  Sig  ", "Best,\\nCam ")]
    assert rows_to_dict(rows, lower_keys=False, limit=10) == {"Sig": "Best,\nCam "}


def test_rows_to_dict_lower_keys_and_case_preserved_values():
    rows = [("Heard As", "Write As"), ("HEARD as", "Final As")]
    assert rows_to_dict(rows, lower_keys=True, limit=10) == {"heard as": "Final As"}
    assert rows_to_dict([("Key", "V")], lower_keys=False, limit=10) == {"Key": "V"}


def test_rows_to_dict_round_trips_escaped_newline():
    value = "line1\nline2\t\\"
    assert rows_to_dict([("t", escape_text(value))], lower_keys=True, limit=5) == {"t": value}


def test_rows_to_dict_limit_keeps_first_distinct_keys_later_duplicate_overrides():
    rows = [("a", "1"), ("b", "2"), ("a", "9"), ("c", "3")]
    assert rows_to_dict(rows, lower_keys=True, limit=2) == {"a": "9", "b": "2"}
    assert list(rows_to_dict(rows, lower_keys=True, limit=2)) == ["a", "b"]


def test_rows_duplicates_reports_normalised_keys_once_in_order():
    rows = [("B", "1"), ("a", "2"), ("b", "3"), ("A", "4"), ("b", "5"), ("", "x"), ("", "y")]
    assert rows_duplicates(rows, lower_keys=True) == ["b", "a"]
    assert rows_duplicates(rows, lower_keys=False) == ["b"]
    assert rows_duplicates([("x", "1"), ("y", "2")], lower_keys=True) == []


def test_row_keys_collapse_internal_whitespace_values_untouched():
    rows = [("  my   Sig ", "Best,  Cam "), ("my sig\t", "x  y")]
    assert rows_to_dict(rows, lower_keys=True, limit=10) == {"my sig": "x  y"}
    assert rows_to_dict([("A  B", " v  ")], lower_keys=False, limit=10) == {"A B": " v  "}
    assert rows_duplicates(rows, lower_keys=True) == ["my sig"]


def test_snippet_warnings_command_collision_short_trigger_and_empty_text():
    snippets = {"new line": "x", "ab": "hello", "sig": "  ", "ok one": "fine"}
    out = snippet_warnings(snippets, {"New Line": "\n"})
    assert len(out) == 3
    assert "new line" in out[0] and "snippet wins" in out[0]
    assert "ab" in out[1] and "3" in out[1]
    assert "sig" in out[2] and "empty" in out[2]


def test_snippet_warnings_clean_is_empty():
    assert snippet_warnings({"my email": "a@b.c"}, {"comma": ","}) == []


def test_terms_from_text_dedupes_case_insensitively_keeping_first():
    text = " Kubernetes \n\nkubernetes\nPerry Homes\r\nPERRY HOMES\n"
    assert terms_from_text(text) == ["Kubernetes", "Perry Homes"]


def test_terms_from_text_limit():
    assert terms_from_text("a\nb\nc", limit=2) == ["a", "b"]
