from pathlib import Path

from flowvoice.commands import DEFAULT_COMMANDS


def test_dash_commands_are_em_dash():
    assert DEFAULT_COMMANDS["dash"] == "\u2014"
    assert DEFAULT_COMMANDS["em dash"] == "\u2014"


def test_all_python_sources_are_ascii():
    root = Path(__file__).resolve().parent.parent
    bad = []
    for d in ("src/flowvoice", "tests"):
        for f in (root / d).rglob("*.py"):
            if any(b > 127 for b in f.read_bytes()):
                bad.append(str(f))
    assert bad == []
