import io
import json

import pytest

from flowvoice import updates
from flowvoice._version import __version__
from flowvoice.updates import Update, check, fetch_latest, is_newer, parse_version, safe_url

PAGE = "https://github.com/camh1473/Flow-Voice/releases/tag/v9.9.9"


@pytest.mark.parametrize("text,expected", [("1.2.3", (1, 2, 3)), ("v0.1", (0, 1)), (" V2 ", (2,)),
                                           ("1.0-rc1", None), ("abc", None), ("", None), (None, None), (5, None)])
def test_parse_version(text, expected):
    assert parse_version(text) == expected


@pytest.mark.parametrize("latest,current,newer", [("0.2.0", "0.1.0", True), ("0.1.0", "0.1.0", False),
                                                  ("0.1.0", "0.2.0", False), ("1.0", "0.9.9", True),
                                                  ("1.0.0", "1.0", False), ("0.10.0", "0.9.0", True),
                                                  ("junk", "0.1.0", False), ("1.0.0", "junk", False)])
def test_is_newer(latest, current, newer):
    assert is_newer(latest, current) is newer


def test_only_this_projects_github_pages_are_offered():
    assert safe_url(PAGE)
    for bad in ("https://evil.example/releases", "http://github.com/camh1473/Flow-Voice/", "https://github.com/other/repo/",
                "javascript:alert(1)", None, 5):
        assert not safe_url(bad)


def reply(**over):
    body = {"tag_name": "v9.9.9", "html_url": PAGE, "draft": False, "prerelease": False}
    body.update(over)
    return lambda req, timeout=None: io.BytesIO(json.dumps(body).encode())


class Ctx(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener(**over):
    body = {"tag_name": "v9.9.9", "html_url": PAGE, "draft": False, "prerelease": False}
    body.update(over)
    return lambda req, timeout=None: Ctx(json.dumps(body).encode())


def test_fetch_latest_reads_tag_and_page():
    assert fetch_latest(opener()) == Update("9.9.9", PAGE)


def test_fetch_latest_sends_a_user_agent_and_nothing_personal():
    seen = {}

    def spy(req, timeout=None):
        seen["headers"], seen["data"], seen["url"] = dict(req.header_items()), req.data, req.full_url
        return Ctx(b'{"tag_name": "v1.0.0", "html_url": "%s"}' % PAGE.encode())

    fetch_latest(spy)
    assert seen["url"] == updates.API_URL and seen["data"] is None
    assert set(k.lower() for k in seen["headers"]) == {"accept", "user-agent"}


@pytest.mark.parametrize("over", [{"draft": True}, {"prerelease": True}, {"tag_name": "nightly"},
                                  {"html_url": "https://evil.example/x"}, {"html_url": None}])
def test_fetch_latest_ignores_unusable_releases(over):
    assert fetch_latest(opener(**over)) is None


def test_fetch_latest_is_silent_on_any_failure():
    def boom(req, timeout=None):
        raise OSError("offline")

    assert fetch_latest(boom) is None
    assert fetch_latest(lambda req, timeout=None: Ctx(b"not json")) is None
    assert fetch_latest(lambda req, timeout=None: Ctx(b"[1, 2]")) is None


def test_check_returns_a_newer_release_and_remembers_it(tmp_path):
    state = tmp_path / "u.json"
    calls = []
    found = check("0.1.0", state, fetch=lambda: calls.append(1) or Update("9.9.9", PAGE), now=lambda: 1000.0)
    assert found == Update("9.9.9", PAGE) and calls == [1]
    again = check("0.1.0", state, fetch=lambda: calls.append(1) or None, now=lambda: 1000.0 + 3600)
    assert again == Update("9.9.9", PAGE) and calls == [1]  # an hour later: no second request


def test_check_asks_again_after_a_day(tmp_path):
    state = tmp_path / "u.json"
    calls = []
    check("0.1.0", state, fetch=lambda: calls.append(1) or None, now=lambda: 1000.0)
    check("0.1.0", state, fetch=lambda: calls.append(1) or None, now=lambda: 1000.0 + updates.INTERVAL_SECONDS + 1)
    assert calls == [1, 1]


def test_check_says_nothing_when_already_current(tmp_path):
    assert check("9.9.9", tmp_path / "u.json", fetch=lambda: Update("9.9.9", PAGE)) is None
    assert check("0.1.0", tmp_path / "v.json", fetch=lambda: None) is None


def test_check_survives_a_corrupt_state_file_and_an_unwritable_folder(tmp_path):
    bad = tmp_path / "u.json"
    bad.write_text("{{{ not json")
    assert check("0.1.0", bad, fetch=lambda: Update("9.9.9", PAGE)) == Update("9.9.9", PAGE)
    blocker = tmp_path / "file"
    blocker.write_text("x")
    assert check("0.1.0", blocker / "sub" / "u.json", fetch=lambda: Update("9.9.9", PAGE)) == Update("9.9.9", PAGE)


def test_check_never_raises_even_if_fetch_does(tmp_path):
    def boom():
        raise RuntimeError("x")

    assert check("0.1.0", tmp_path / "u.json", fetch=boom) is None


def test_clock_going_backwards_triggers_a_fresh_check(tmp_path):
    state = tmp_path / "u.json"
    calls = []
    check("0.1.0", state, fetch=lambda: calls.append(1) or None, now=lambda: 5000.0)
    check("0.1.0", state, fetch=lambda: calls.append(1) or None, now=lambda: 10.0)
    assert calls == [1, 1]


def test_version_is_plain_dotted_numbers():
    assert parse_version(__version__) is not None
