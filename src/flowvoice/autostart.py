import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_NAME = "FlowVoice"


class _WinReg:
    def set(self, key, name, value):
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)

    def delete(self, key, name):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
                winreg.DeleteValue(k, name)
        except FileNotFoundError:
            pass


def default_command() -> str:
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    return f'"{pythonw}" -m flowvoice'


def set_autostart(enabled: bool, *, command: str | None = None, registry=None) -> None:
    registry = registry or _WinReg()
    if enabled:
        registry.set(RUN_KEY, _NAME, command or default_command())
    else:
        registry.delete(RUN_KEY, _NAME)
