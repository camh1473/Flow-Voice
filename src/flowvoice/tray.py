import ctypes
import queue
import threading
import tkinter as tk
from typing import Literal

import pystray
from PIL import Image, ImageDraw

State = Literal["idle", "recording", "processing"]
_COLORS = {"idle": "#888888", "recording": "#e03030", "processing": "#e0a020"}


def _icon(color: str) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((8, 8, 56, 56), fill=color)
    return img


def _no_activate(root: tk.Tk) -> None:
    """Make the badge a non-activating tool window so showing it never steals focus."""
    root.update_idletasks()
    user32 = ctypes.windll.user32
    hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    style = user32.GetWindowLongW(hwnd, -20)
    user32.SetWindowLongW(hwnd, -20, style | 0x08000000 | 0x00000080)  # NOACTIVATE | TOOLWINDOW


class _Indicator:
    """Small always-on-top dot at the bottom-center of the screen, on its own thread."""

    def __init__(self):
        self._q: queue.Queue = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def set(self, state: str) -> None:
        self._q.put(state)

    def _run(self) -> None:
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True, "-alpha", 0.85)
        w, h = 70, 26
        x = (root.winfo_screenwidth() - w) // 2
        y = root.winfo_screenheight() - 110
        root.geometry(f"{w}x{h}+{x}+{y}")
        label = tk.Label(root, text="", fg="white", font=("Segoe UI", 9, "bold"))
        label.pack(fill="both", expand=True)
        _no_activate(root)
        root.withdraw()

        def poll():
            try:
                while True:
                    s = self._q.get_nowait()
                    if s == "idle":
                        root.withdraw()
                    else:
                        label.config(text="REC" if s == "recording" else "...", bg=_COLORS[s])
                        root.deiconify()
            except queue.Empty:
                pass
            root.after(50, poll)

        poll()
        root.mainloop()


class Tray:
    def __init__(self, on_quit, on_settings=lambda: None):
        self._on_quit = on_quit
        self._indicator = _Indicator()
        self._icon = pystray.Icon("flowvoice", _icon(_COLORS["idle"]), "Flow Voice",
                                  menu=pystray.Menu(pystray.MenuItem("Settings...", lambda icon, item: on_settings()),
                                                    pystray.MenuItem("Quit", self._quit)))

    def run(self, on_ready=None) -> None:
        """Blocks on the tray loop; `on_ready` runs on a worker thread once the icon is up."""
        self._icon.run(setup=(lambda icon: (setattr(icon, "visible", True),
                                            threading.Thread(target=on_ready, daemon=True).start()
                                            if on_ready else None)))

    def set_state(self, state: State) -> None:
        self._icon.icon = _icon(_COLORS[state])
        self._indicator.set(state)

    def notify(self, message: str) -> None:
        try:
            self._icon.notify(message, "Flow Voice")
        except Exception:
            pass

    def _quit(self, icon, item) -> None:
        self._on_quit()
        icon.stop()
