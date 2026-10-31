"""Where the app lives, and how to start another copy of it (source tree or packaged .exe)."""
import sys
from pathlib import Path


def frozen() -> bool:
    """True inside the PyInstaller-built FlowVoice.exe."""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Folder holding FlowVoice.exe, or the repository root when run from source."""
    if frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def relaunch_command() -> list[str]:
    """Command line that starts a fresh copy of this app."""
    return [sys.executable] if frozen() else [sys.executable, "-m", "flowvoice"]


def bundled_model(name: str, base: Path | None = None) -> str | None:
    """Folder of a speech model shipped next to the app (`models/<name>/model.bin`), if present.

    Lets a packaged copy work offline; otherwise the model is downloaded on first use.
    """
    folder = (base or app_dir()) / "models" / name
    return str(folder) if (folder / "model.bin").is_file() else None
