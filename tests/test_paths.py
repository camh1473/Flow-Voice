import sys

from flowvoice import autostart, paths


def test_source_run_relaunches_with_python_dash_m(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert paths.relaunch_command() == [sys.executable, "-m", "flowvoice"]


def test_frozen_run_relaunches_the_exe_itself(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\FlowVoice\FlowVoice.exe")
    assert paths.relaunch_command() == [r"C:\Apps\FlowVoice\FlowVoice.exe"]
    assert paths.app_dir().name == "FlowVoice"


def test_frozen_autostart_command_is_the_quoted_exe_only(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\Flow Voice\FlowVoice.exe")
    assert autostart.default_command() == r'"C:\Apps\Flow Voice\FlowVoice.exe"'


def test_source_autostart_command_uses_pythonw(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Proj\.venv\Scripts\python.exe")
    assert autostart.default_command() == r'"C:\Proj\.venv\Scripts\pythonw.exe" -m flowvoice'


def test_bundled_model_found_only_when_model_bin_exists(tmp_path):
    assert paths.bundled_model("small.en", tmp_path) is None
    folder = tmp_path / "models" / "small.en"
    folder.mkdir(parents=True)
    assert paths.bundled_model("small.en", tmp_path) is None  # folder without model.bin
    (folder / "model.bin").write_bytes(b"x")
    assert paths.bundled_model("small.en", tmp_path) == str(folder)


def test_engine_prefers_a_bundled_model(tmp_path, monkeypatch):
    from flowvoice import engine as eng

    folder = tmp_path / "models" / "tiny.en"
    folder.mkdir(parents=True)
    (folder / "model.bin").write_bytes(b"x")
    monkeypatch.setattr(eng, "bundled_model", lambda name: paths.bundled_model(name, tmp_path))
    seen = []

    def factory(name, device, compute_type):
        seen.append(name)
        return object()

    eng.Engine("tiny.en", device="cpu", model_factory=factory)
    eng.Engine("base.en", device="cpu", model_factory=factory)
    assert seen == [str(folder), "base.en"]
