"""Create a GitHub Release and upload the installers, using the credential Git already stores.

  python scripts/publish_release.py --check
  python scripts/publish_release.py --tag v0.1.0 --title "Flow Voice 0.1.0" \
      --notes packaging/release-notes/0.1.0.md dist/FlowVoice-0.1.0-Setup.exe dist/SHA256SUMS.txt

The token is read from `git credential fill` and is never printed or put on a command line
(it goes to curl through a private temporary header file that is deleted afterwards).
Refuses to touch an existing release for the same tag.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

REPO = "camh1473/Flow-Voice"
API = f"https://api.github.com/repos/{REPO}"


def parse_credential(text: str) -> dict[str, str]:
    """The key=value lines `git credential fill` prints."""
    out = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


def stored_token() -> str:
    proc = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                          capture_output=True, text=True, timeout=30,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    token = parse_credential(proc.stdout).get("password", "")
    if not token:
        raise SystemExit("No stored GitHub credential found (git credential fill returned nothing).")
    return token


def api(method: str, url: str, token: str, body: dict | None = None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                                          "User-Agent": "FlowVoice-release", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, dict(resp.headers), json.loads(resp.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read().decode() or "null")


def check(token: str) -> bool:
    status, headers, data = api("GET", API, token)
    perms = (data or {}).get("permissions", {}) if isinstance(data, dict) else {}
    print(f"repo {REPO}: HTTP {status}, private={data.get('private') if isinstance(data, dict) else '?'}, "
          f"push permission={perms.get('push')}, token scopes={headers.get('X-OAuth-Scopes', headers.get('x-oauth-scopes', '(fine-grained/none listed)'))}")
    return status == 200 and bool(perms.get("push"))


def upload(path: Path, upload_url: str, token: str) -> None:
    kind = "application/vnd.microsoft.portable-executable" if path.suffix == ".exe" else "text/plain"
    with tempfile.TemporaryDirectory() as tmp:
        header_file = Path(tmp) / "h.txt"
        header_file.write_text(f"Authorization: Bearer {token}\n", encoding="ascii")
        url = upload_url.split("{")[0] + f"?name={path.name}"
        cmd = ["curl", "--fail-with-body", "--retry", "3", "-sS", "-X", "POST", "-H", f"@{header_file}",
               "-H", "Accept: application/vnd.github+json", "-H", f"Content-Type: {kind}",
               "--data-binary", f"@{path}", url, "-o", os.devnull]
        subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--tag")
    ap.add_argument("--title")
    ap.add_argument("--notes")
    ap.add_argument("--target", default="main")
    ap.add_argument("files", nargs="*")
    args = ap.parse_args()
    token = stored_token()
    if args.check:
        return 0 if check(token) else 1
    if not (args.tag and args.title and args.notes and args.files):
        ap.error("--tag, --title, --notes and at least one file are required")
    files = [Path(f) for f in args.files]
    for f in files:
        if not f.is_file():
            raise SystemExit(f"missing file: {f}")
    status, _, _ = api("GET", f"{API}/releases/tags/{args.tag}", token)
    if status == 200:
        raise SystemExit(f"A release for {args.tag} already exists; not touching it.")
    status, _, rel = api("POST", f"{API}/releases", token, {
        "tag_name": args.tag, "target_commitish": args.target, "name": args.title,
        "body": Path(args.notes).read_text(encoding="utf-8"), "draft": True, "prerelease": False})
    if status != 201:
        raise SystemExit(f"Could not create the release: HTTP {status} {rel}")
    print("draft release created:", rel["html_url"])
    for f in files:
        print(f"uploading {f.name} ({f.stat().st_size // 1048576} MB)...", flush=True)
        upload(f, rel["upload_url"], token)
    status, _, done = api("PATCH", f"{API}/releases/{rel['id']}", token, {"draft": False})
    if status != 200:
        raise SystemExit(f"Uploaded, but could not publish the draft: HTTP {status} {done}")
    print("published:", done["html_url"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
