"""Local dictation history (SQLite) and foreground app name lookup."""
import ctypes
import os
import sqlite3
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass
class HistoryEntry:
    id: int | None
    created_at: str
    raw_text: str
    clean_text: str
    app_name: str


def default_path() -> Path:
    return Path(os.environ.get("APPDATA", Path.home())) / "FlowVoice" / "history.db"


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class History:
    """SQLite-backed history; opens a fresh connection per call (thread safe)."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS entries ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, "
                "raw_text TEXT NOT NULL, clean_text TEXT NOT NULL, "
                "app_name TEXT NOT NULL DEFAULT '')"
            )

    def _connect(self):
        """Connection context manager: commits on success, always closes."""
        return _Conn(self.path)

    def add(self, raw: str, clean: str, app_name: str = "") -> HistoryEntry:
        created = datetime.now().isoformat(timespec="seconds")
        with self._connect() as con:
            cur = con.execute(
                "INSERT INTO entries (created_at, raw_text, clean_text, app_name) "
                "VALUES (?, ?, ?, ?)",
                (created, raw, clean, app_name),
            )
            entry_id = cur.lastrowid
        return HistoryEntry(entry_id, created, raw, clean, app_name)

    def list(self, limit: int = 200, query: str = "") -> list[HistoryEntry]:
        sql = "SELECT id, created_at, raw_text, clean_text, app_name FROM entries"
        params: list = []
        if query:
            like = f"%{_escape_like(query)}%"
            sql += (
                " WHERE clean_text LIKE ? ESCAPE '\\' OR raw_text LIKE ? ESCAPE '\\'"
            )
            params += [like, like]
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._connect() as con:
            rows = con.execute(sql, params).fetchall()
        return [HistoryEntry(*row) for row in rows]

    def delete(self, entry_id: int) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM entries WHERE id = ?", (entry_id,))

    def clear(self) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM entries")


class _Conn:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._con: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self._con = sqlite3.connect(self._path, timeout=10)
        return self._con

    def __exit__(self, exc_type, exc, tb) -> None:
        con = self._con
        try:
            if exc_type is None:
                con.commit()
            else:
                con.rollback()
        finally:
            con.close()


def active_app_name() -> str:
    """Executable base name of the foreground window's process, or "" on failure."""
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.GetForegroundWindow.restype = wintypes.HWND
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(1024)
            buf = ctypes.create_unicode_buffer(size.value)
            if not kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                return ""
            return os.path.basename(buf.value)
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        return ""
