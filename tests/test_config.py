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


def test_phrase_lists_not_shared_between_instances():
    a, b = Config(), Config()
    a.filler_phrases.append("zzz")
    assert "zzz" not in b.filler_phrases
