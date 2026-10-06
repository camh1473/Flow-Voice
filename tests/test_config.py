import json
from flowvoice.config import Config, load_config, save_config


def test_defaults_when_file_missing(tmp_path):
    assert load_config(tmp_path / "x.json") == Config()


def test_roundtrip(tmp_path):
    p = tmp_path / "sub" / "c.json"
    cfg = Config(ptt_key="f9", model="base.en")
    save_config(cfg, p)
    assert load_config(p) == cfg


def test_corrupt_file_returns_defaults(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{not json")
    assert load_config(p) == Config()


def test_unknown_keys_ignored(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"ptt_key": "f8", "bogus": 1}))
    assert load_config(p).ptt_key == "f8"

def test_new_phrase_lists_have_defaults_and_roundtrip(tmp_path):
    cfg = Config()
    assert "scratch that" in cfg.backtrack_phrases and "excuse me" in cfg.backtrack_phrases
    assert "you know" in cfg.filler_phrases
    cfg.backtrack_phrases = ["oops"]
    p = tmp_path / "c.json"
    save_config(cfg, p)
    assert load_config(p).backtrack_phrases == ["oops"]


def test_v2_defaults():
    c = Config()
    assert c.voice_commands is True and c.hands_free is True
    assert c.silence_stop_seconds == 4.0
    assert c.save_history is True and c.pill_always_visible is True
    assert c.ui_scale == 1.0
    assert c.command_phrases["full stop"] == "."
    assert "quote" not in c.command_phrases


def test_v2_roundtrip(tmp_path):
    p = tmp_path / "c.json"
    cfg = Config(command_phrases={"smiley": ":)"}, ui_scale=1.3)
    save_config(cfg, p)
    back = load_config(p)
    assert back.command_phrases == {"smiley": ":)"} and back.ui_scale == 1.3


def test_command_phrases_not_shared_between_instances():
    a, b = Config(), Config()
    a.command_phrases["zzz"] = "z"
    assert "zzz" not in b.command_phrases


def test_bad_types_fall_back_to_defaults(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"command_phrases": [1, 2], "ui_scale": "big", "ptt_key": "f8"}))
    c = load_config(p)
    assert c.command_phrases == Config().command_phrases
    assert c.ui_scale == 1.0
    assert c.ptt_key == "f8"


def test_ui_scale_clamped_on_load(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"ui_scale": 5}))
    assert load_config(p).ui_scale == 1.6
    p.write_text(json.dumps({"ui_scale": 0.1}))
    assert load_config(p).ui_scale == 0.8


def test_ensure_config_file_writes_once_on_first_run(tmp_path):
    from flowvoice.config import ensure_config_file
    p = tmp_path / "sub" / "c.json"
    cfg = Config(ptt_key="f9")
    assert ensure_config_file(cfg, p) is True
    assert p.exists() and load_config(p).ptt_key == "f9"
    assert ensure_config_file(Config(), p) is False
    assert load_config(p).ptt_key == "f9"  # an existing file is never overwritten


def test_ensure_config_file_save_failure_is_not_fatal(tmp_path):
    from flowvoice.config import ensure_config_file
    blocker = tmp_path / "file"
    blocker.write_text("x")
    p = blocker / "c.json"  # parent is a file: mkdir/write fails
    assert ensure_config_file(Config(), p) is True


def test_phrase_lists_not_shared_between_instances():
    a, b = Config(), Config()
    a.filler_phrases.append("zzz")
    assert "zzz" not in b.filler_phrases
