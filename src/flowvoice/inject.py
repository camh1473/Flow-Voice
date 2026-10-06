import time

import keyboard
import pyperclip

_MOD_KEYS = ("ctrl", "alt", "shift", "windows")


def _wait_modifiers_released(timeout: float = 1.0) -> None:
    end = time.time() + timeout
    while time.time() < end and any(keyboard.is_pressed(k) for k in _MOD_KEYS):
        time.sleep(0.02)


def _safe_get(get_clip):
    try:
        return get_clip()
    except Exception:
        return None


def paste_text(text: str, *, get_clip=pyperclip.paste, set_clip=pyperclip.copy,
               send=keyboard.send, type_text=keyboard.write, sleep=time.sleep) -> None:
    if not text.strip(" \t"):
        return
    original = _safe_get(get_clip)
    try:
        set_clip(text)
        try:
            send("ctrl+v")
            sleep(0.3)
        except Exception:
            type_text(text)
    finally:
        if original is not None:
            set_clip(original)


def copy_selection(*, get_clip=pyperclip.paste, set_clip=pyperclip.copy,
                   send=keyboard.send, sleep=time.sleep,
                   wait_released=_wait_modifiers_released) -> str:
    """Return the currently selected text (via Ctrl+C), restoring the clipboard."""
    original = _safe_get(get_clip)
    try:
        set_clip("")
        wait_released()
        send("ctrl+c")
        sleep(0.15)
        return get_clip()
    finally:
        if original is not None:
            set_clip(original)
