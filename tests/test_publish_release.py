import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("publish_release", Path(__file__).resolve().parents[1] / "scripts" / "publish_release.py")
publish = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publish)


def test_parse_credential_reads_key_value_lines():
    out = publish.parse_credential("protocol=https\nhost=github.com\nusername=me\npassword=s3cr=t\n\n")
    assert out["password"] == "s3cr=t" and out["host"] == "github.com"


def test_parse_credential_ignores_noise():
    assert publish.parse_credential("") == {} and publish.parse_credential("garbage line") == {}


def test_repo_points_at_this_project():
    assert publish.REPO == "camh1473/Flow-Voice" and publish.API.endswith("/camh1473/Flow-Voice")
