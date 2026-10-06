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


def test_silence_stop_seconds_clamped_on_load(tmp_path):
    p = tmp_path / "c.json"
    for bad in (0, -3, 0.2):
        p.write_text(json.dumps({"silence_stop_seconds": bad}))
        assert load_config(p).silence_stop_seconds == 0.5
    p.write_text(json.dumps({"silence_stop_seconds": 2}))
    c = load_config(p)
    assert c.silence_stop_seconds == 2.0 and isinstance(c.silence_stop_seconds, float)


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


def test_v3_defaults():
    c = Config()
    assert c.dictionary_terms == [] and c.dictionary_fixes == {} and c.snippets == {}
    assert c.auto_lists is True and c.ai_enabled is False
    assert c.ai_model == "qwen3.5:2b-q4_K_M"
    assert c.ai_min_words == 20 and c.ai_timeout_seconds == 6.0
    assert c.ai_url == "http://localhost:11434"


def test_v3_roundtrip(tmp_path):
    p = tmp_path / "c.json"
    cfg = Config(dictionary_terms=["Kubernetes"], dictionary_fixes={"cube ctl": "kubectl"},
                 snippets={"my email": "a@b.co"}, auto_lists=False, ai_enabled=True,
                 ai_model="m:1b", ai_min_words=30, ai_timeout_seconds=9.5,
                 ai_url="http://127.0.0.1:11434")
    save_config(cfg, p)
    assert load_config(p) == cfg


def test_v3_bad_types_fall_back_per_field(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({
        "dictionary_terms": "nope", "dictionary_fixes": {"a": 1}, "snippets": {"a": 2},
        "ai_min_words": "x", "ai_enabled": "yes", "auto_lists": 1, "ai_model": 5,
        "ai_url": None, "ai_timeout_seconds": "fast", "ptt_key": "f8"}))
    c = load_config(p)
    d = Config()
    assert c.dictionary_terms == d.dictionary_terms
    assert c.dictionary_fixes == d.dictionary_fixes and c.snippets == d.snippets
    assert c.ai_min_words == 20 and c.ai_enabled is False and c.auto_lists is True
    assert c.ai_model == d.ai_model and c.ai_url == d.ai_url
    assert c.ai_timeout_seconds == 6.0
    assert c.ptt_key == "f8"


def test_ai_min_words_clamped_and_int(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"ai_min_words": 2}))
    assert load_config(p).ai_min_words == 5
    p.write_text(json.dumps({"ai_min_words": 20.7}))
    c = load_config(p)
    assert c.ai_min_words == 20 and isinstance(c.ai_min_words, int)
    p.write_text(json.dumps({"ai_min_words": True}))
    assert load_config(p).ai_min_words == 20


def test_ai_timeout_clamped(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"ai_timeout_seconds": 0.1}))
    assert load_config(p).ai_timeout_seconds == 1.0
    p.write_text(json.dumps({"ai_timeout_seconds": 999}))
    c = load_config(p)
    assert c.ai_timeout_seconds == 60.0 and isinstance(c.ai_timeout_seconds, float)


def test_collections_truncated_on_load(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({
        "dictionary_terms": [f"t{i}" for i in range(250)],
        "dictionary_fixes": {f"f{i}": "x" for i in range(250)},
        "snippets": {f"s{i}": "x" for i in range(150)}}))
    c = load_config(p)
    assert c.dictionary_terms == [f"t{i}" for i in range(200)]
    assert list(c.dictionary_fixes) == [f"f{i}" for i in range(200)]
    assert list(c.snippets) == [f"s{i}" for i in range(100)]


def test_v3_collections_not_shared_between_instances():
    a, b = Config(), Config()
    a.dictionary_terms.append("zzz")
    a.dictionary_fixes["z"] = "y"
    a.snippets["z"] = "y"
    assert b.dictionary_terms == [] and b.dictionary_fixes == {} and b.snippets == {}
