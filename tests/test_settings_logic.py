from flowvoice.config import Config
from flowvoice.settings_logic import needs_restart, parse_phrases


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
