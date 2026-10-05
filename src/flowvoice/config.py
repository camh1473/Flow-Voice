import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class Config:
    ptt_key: str = "right ctrl"
    tts_key: str = "ctrl+alt+s"
    model: str = "small.en"
    mic_device: int | None = None
    start_with_windows: bool = False


def default_path() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "FlowVoice" / "config.json"


def load_config(path: Path | None = None) -> Config:
    path = path or default_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        known = {f.name for f in fields(Config)}
        return Config(**{k: v for k, v in data.items() if k in known})
    except Exception:
        return Config()


def save_config(cfg: Config, path: Path | None = None) -> None:
    path = path or default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
