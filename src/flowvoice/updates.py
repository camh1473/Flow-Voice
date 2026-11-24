"""Once-a-day check for a newer release on GitHub. Notifies only; never downloads or installs.

It asks api.github.com for the latest release of this project and sends nothing about you
(no id, no usage data). Turn it off with Settings > Interface > Check for updates.
Every failure (offline, rate limit, bad reply) is silent: dictation never depends on this.
"""
import json
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO = "camh1473/Flow-Voice"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGE_PREFIX = f"https://github.com/{REPO}/"
INTERVAL_SECONDS = 24 * 3600
TIMEOUT_SECONDS = 6.0


@dataclass(frozen=True)
class Update:
    version: str
    url: str


def parse_version(text) -> tuple[int, ...] | None:
    """'v1.2.3' -> (1, 2, 3). Anything that is not plain dotted numbers (e.g. '1.0-rc1') -> None."""
    if not isinstance(text, str):
        return None
    m = re.fullmatch(r"[vV]?(\d+(?:\.\d+){0,3})", text.strip())
    return tuple(int(x) for x in m.group(1).split(".")) if m else None


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    if a is None or b is None:
        return False
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) > b + (0,) * (n - len(b))


def safe_url(url) -> bool:
    """Only ever offer a page on this project's own GitHub."""
    return isinstance(url, str) and url.startswith(PAGE_PREFIX)


def fetch_latest(opener=urllib.request.urlopen, timeout: float = TIMEOUT_SECONDS) -> Update | None:
    try:
        req = urllib.request.Request(API_URL, headers={
            "Accept": "application/vnd.github+json", "User-Agent": "FlowVoice-update-check"})
        with opener(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
            return None
        tag, url = data.get("tag_name"), data.get("html_url")
        if parse_version(tag) is None or not safe_url(url):
            return None
        return Update(str(tag).lstrip("vV"), url)
    except Exception:
        return None


def check(current: str, state_file: Path, *, fetch=fetch_latest, now=time.time,
          interval: float = INTERVAL_SECONDS) -> Update | None:
    """The newer release if there is one. Asks GitHub at most once per `interval`; never raises."""
    try:
        state = {}
        try:
            state = json.loads(Path(state_file).read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                state = {}
        except Exception:
            state = {}
        t = now()
        last = state.get("checked")
        if isinstance(last, (int, float)) and 0 <= t - last < interval:
            found = Update(state["version"], state["url"]) if state.get("version") and safe_url(state.get("url")) else None
        else:
            found = fetch()
            try:
                Path(state_file).parent.mkdir(parents=True, exist_ok=True)
                Path(state_file).write_text(json.dumps(
                    {"checked": t, "version": found.version if found else "", "url": found.url if found else ""}),
                    encoding="utf-8")
            except Exception:
                pass
        return found if found and is_newer(found.version, current) else None
    except Exception:
        return None
