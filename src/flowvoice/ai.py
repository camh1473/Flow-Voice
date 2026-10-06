"""Loopback-only Ollama client (stdlib) and helper to start the local server."""
import json
import os
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

CREATE_NO_WINDOW = 0x08000000
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
_PROBE_TIMEOUT = 1.5


class AiError(Exception):
    """Any failure talking to the local model; the message is short and safe to show."""


def is_loopback(url: str) -> bool:
    """True only for http(s) URLs whose host is localhost, 127.0.0.1 or ::1."""
    try:
        parts = urllib.parse.urlsplit(url.strip())
        host = parts.hostname
        if parts.scheme not in ("http", "https") or not host:
            return False
        if parts.username is not None or parts.password is not None:
            return False
        return host.lower().strip("[]") in _LOOPBACK_HOSTS
    except ValueError:
        return False


def _literal_base(url: str) -> str:
    """Request base URL with the name localhost replaced by 127.0.0.1 (no IPv6-first resolution stall)."""
    parts = urllib.parse.urlsplit(url)
    if (parts.hostname or "").lower() != "localhost":
        return url
    netloc = "127.0.0.1" + (f":{parts.port}" if parts.port else "")
    return urllib.parse.urlunsplit(parts._replace(netloc=netloc))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AiError("Local AI server tried to redirect the request")


def _opener() -> urllib.request.OpenerDirector:
    # No system proxy: the request must go straight to the loopback address.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())


class OllamaClient:
    def __init__(self, url: str, model: str, timeout: float = 6.0):
        if not is_loopback(url):
            raise AiError("AI server must be on this PC (localhost)")
        self.url = url.strip().rstrip("/")
        self.model = model
        self.timeout = timeout
        self._base = _literal_base(self.url)

    def _request(self, path: str, body: dict | None, timeout: float) -> bytes:
        """One HTTP call with a total deadline (worker thread joined with a timeout)."""
        result: dict = {}

        def work() -> None:
            try:
                data = json.dumps(body).encode("utf-8") if body is not None else None
                req = urllib.request.Request(
                    self._base + path, data=data,
                    headers={"Content-Type": "application/json"} if data else {},
                    method="POST" if data is not None else "GET")
                with _opener().open(req, timeout=timeout) as resp:
                    if resp.status != 200:
                        raise AiError(f"AI server returned HTTP {resp.status}")
                    result["data"] = resp.read()
            except AiError as e:
                result["error"] = e
            except urllib.error.HTTPError as e:
                result["error"] = AiError(f"AI server returned HTTP {e.code}")
            except Exception:
                result["error"] = AiError("Could not reach the local AI server")

        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        worker.join(timeout)
        if worker.is_alive():
            raise AiError("Local AI timed out")
        if "error" in result:
            raise result["error"]
        return result["data"]

    def _json(self, path: str, body: dict | None, timeout: float):
        raw = self._request(path, body, timeout)
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            raise AiError("Local AI sent an unreadable reply") from None

    def chat(self, system: str, user: str, *,
             examples: list[tuple[str, str]] | None = None, max_tokens: int = 512) -> str:
        messages = [{"role": "system", "content": system}]
        for q, a in examples or []:
            messages.append({"role": "user", "content": q})
            messages.append({"role": "assistant", "content": a})
        messages.append({"role": "user", "content": user})
        body = {
            "model": self.model, "stream": False, "think": False, "keep_alive": "30m",
            "options": {"temperature": 0, "num_predict": max_tokens},
            "messages": messages,
        }
        data = self._json("/api/chat", body, self.timeout)
        message = data.get("message") if isinstance(data, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise AiError("Local AI returned an empty reply")
        return content

    def _list(self, timeout: float) -> list[str]:
        data = self._json("/api/tags", None, timeout)
        models = data.get("models") if isinstance(data, dict) else None
        if not isinstance(models, list):
            raise AiError("Local AI sent an unreadable model list")
        return [m["name"] for m in models if isinstance(m, dict) and isinstance(m.get("name"), str)]

    def list_models(self) -> list[str]:
        return self._list(self.timeout)

    def is_up(self) -> bool:
        try:
            self._list(_PROBE_TIMEOUT)
            return True
        except Exception:
            return False

    def has_model(self) -> bool:
        try:
            names = self._list(_PROBE_TIMEOUT)
        except Exception:
            return False
        if self.model in names:
            return True
        return ":" not in self.model and f"{self.model}:latest" in names


def find_ollama_exe() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    base = os.environ.get("LOCALAPPDATA")
    if base:
        path = os.path.join(base, "Programs", "Ollama", "ollama.exe")
        if os.path.isfile(path):
            return path
    return None


def _spawn_hidden(args: list[str]) -> subprocess.Popen:
    # Deliberately not waited on: the server keeps running after the app exits unless the user stops it.
    return subprocess.Popen(
        args, creationflags=CREATE_NO_WINDOW, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, close_fds=True)


def ensure_running(client, *, spawn: Callable = _spawn_hidden, sleep: Callable = time.sleep,
                   clock: Callable = time.monotonic, exe: Callable = find_ollama_exe,
                   wait_seconds: float = 30.0) -> bool:
    """Start `ollama serve` if the server is down; True once it answers. Never raises."""
    try:
        if client.is_up():
            return True
        path = exe()
        if not path:
            return False
        spawn([path, "serve"])
        deadline = clock() + wait_seconds
        while clock() < deadline:
            sleep(0.5)
            if client.is_up():
                return True
        return False
    except Exception:
        return False
