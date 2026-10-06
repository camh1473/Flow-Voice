import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from flowvoice.cleanup import DEFAULT_BACKTRACK_PHRASES, DEFAULT_FILLER_PHRASES
from flowvoice.commands import DEFAULT_COMMANDS


@dataclass
class Config:
    ptt_key: str = "right ctrl"
    tts_key: str = "ctrl+alt+s"
    model: str = "small.en"
    mic_device: int | None = None
    start_with_windows: bool = False
    filler_phrases: list[str] = field(default_factory=lambda: list(DEFAULT_FILLER_PHRASES))
    backtrack_phrases: list[str] = field(default_factory=lambda: list(DEFAULT_BACKTRACK_PHRASES))
    voice_commands: bool = True
    command_phrases: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_COMMANDS))
    hands_free: bool = True
    silence_stop_seconds: float = 4.0
    save_history: bool = True
    pill_always_visible: bool = True
    ui_scale: float = 1.0


UI_SCALE_MIN, UI_SCALE_MAX = 0.8, 1.6


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _valid(name: str, v) -> bool:
    if name in ("ptt_key", "tts_key", "model"):
        return isinstance(v, str)
    if name == "mic_device":
        return v is None or (isinstance(v, int) and not isinstance(v, bool))
    if name in ("start_with_windows", "voice_commands", "hands_free",
                "save_history", "pill_always_visible"):
        return isinstance(v, bool)
    if name in ("filler_phrases", "backtrack_phrases"):
        return isinstance(v, list) and all(isinstance(x, str) for x in v)
    if name == "command_phrases":
        return isinstance(v, dict) and all(
            isinstance(k, str) and isinstance(x, str) for k, x in v.items())
    if name in ("silence_stop_seconds", "ui_scale"):
        return _is_num(v)
    return True


def default_path() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "FlowVoice" / "config.json"


def load_config(path: Path | None = None) -> Config:
    path = path or default_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in fields(Config)}
        kwargs = {k: v for k, v in data.items() if k in known and _valid(k, v)}
        if "ui_scale" in kwargs:
            kwargs["ui_scale"] = float(min(UI_SCALE_MAX, max(UI_SCALE_MIN, kwargs["ui_scale"])))
        if "silence_stop_seconds" in kwargs:
            kwargs["silence_stop_seconds"] = float(kwargs["silence_stop_seconds"])
        return Config(**kwargs)
    except Exception:
        return Config()


def save_config(cfg: Config, path: Path | None = None) -> None:
    path = path or default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")


def ensure_config_file(cfg: Config, path: Path | None = None) -> bool:
    """Write cfg if no config file exists yet; return whether this was the first run."""
    path = path or default_path()
    if path.exists():
        return False
    try:
        save_config(cfg, path)
    except Exception:
        pass
    return True
