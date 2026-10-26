"""GPU admission tests use fake nvidia-smi responses, never GPU/model loads."""
import json
import os
import subprocess
import sys

import pytest

from stages import gpu


@pytest.fixture
def admission(monkeypatch, tmp_path):
    monkeypatch.setattr(gpu, "LOCK_PATH", tmp_path / "logs/gpu.lock")
    monkeypatch.setattr(gpu, "smi", lambda *args: "10240" if "--query-gpu=memory.free" in args
                        else "123, explorer.exe\n456, [Insufficient Permissions]")
    return gpu.LOCK_PATH


def test_desktop_and_unreadable_processes_warn_but_do_not_block(admission, capsys):
    assert gpu.gpu_free()["free_mib"] == [10240]
    assert "No live" in gpu.gpu_idle()
    with gpu.gpu_job():
        assert int(admission.read_text()) == os.getpid()
    assert not admission.exists()
    assert "WARNING" in capsys.readouterr().out
    assert "Insufficient Permissions" in gpu.gpu_process_warnings()[0]


def test_low_memory_fails_and_releases_lock(admission, monkeypatch):
    monkeypatch.setattr(gpu, "smi", lambda *a: "10239")
    with pytest.raises(ValueError, match="10 GiB"):
        with gpu.gpu_job():
            pytest.fail("must not start")
    assert not admission.exists()


def test_live_lock_blocks_both_report_and_job(admission):
    admission.parent.mkdir()
    admission.write_text(str(os.getpid()))
    with pytest.raises(ValueError, match="already running"):
        gpu.gpu_idle()
    with pytest.raises(ValueError, match="already running"):
        with gpu.gpu_job():
            pytest.fail("must not start")
    assert admission.read_text() == str(os.getpid())


def test_dead_lock_ignored_and_replaced(admission, monkeypatch):
    admission.parent.mkdir()
    admission.write_text("987654")
    monkeypatch.setattr(gpu, "pid_alive", lambda pid: pid != 987654)
    assert "No live" in gpu.gpu_idle()
    with gpu.gpu_job():
        assert admission.read_text() == str(os.getpid())
    assert not admission.exists()


def test_exception_and_system_exit_release_lock(admission):
    for exception in (RuntimeError("test"), SystemExit(1), KeyboardInterrupt()):
        with pytest.raises(type(exception)):
            with gpu.gpu_job():
                raise exception
        assert not admission.exists()


def test_unavailable_process_query_is_only_warning(admission, monkeypatch):
    def fake(*args):
        if "--query-gpu=memory.free" in args:
            return "12000"
        raise subprocess.TimeoutExpired("nvidia-smi", 20)
    monkeypatch.setattr(gpu, "smi", fake)
    with gpu.gpu_job():
        assert "unavailable" in gpu.gpu_process_warnings()[0]


def test_pid_liveness():
    assert gpu.pid_alive(os.getpid())
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=10)
    assert not gpu.pid_alive(child.pid)
    assert not gpu.pid_alive(0)


def test_stale_lock_contenders_cannot_both_enter(admission, tmp_path):
    admission.parent.mkdir()
    admission.write_text("987654")
    # Children wait for a common start signal, and keep the winner's lock until
    # released by this test. Only GPU reporting and the old dead PID are mocked.
    code = '''
import sys, time
from pathlib import Path
from stages import gpu
gpu.LOCK_PATH = Path(sys.argv[1])
directory, name = Path(sys.argv[2]), sys.argv[3]
real_alive = gpu.pid_alive
gpu.pid_alive = lambda pid: False if pid == 987654 else real_alive(pid)
gpu.gpu_free = lambda: None
gpu.gpu_process_warnings = lambda: []
deadline = time.monotonic() + 10
while not (directory / "start").exists():
    if time.monotonic() > deadline: raise RuntimeError("start timeout")
    time.sleep(.01)
try:
    with gpu.gpu_job():
        (directory / name).write_text("entered")
        while not (directory / "release").exists():
            if time.monotonic() > deadline: raise RuntimeError("release timeout")
            time.sleep(.01)
except ValueError:
    (directory / name).write_text("blocked")
'''
    children = [subprocess.Popen([sys.executable, "-c", code, str(admission), str(tmp_path), str(i)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for i in range(2)]
    import time
    try:
        (tmp_path / "start").touch()
        deadline = time.monotonic() + 10
        while not all((tmp_path / str(i)).exists() for i in range(2)):
            if time.monotonic() > deadline:
                pytest.fail("lock contenders did not finish admission")
            time.sleep(.01)
        assert sorted((tmp_path / str(i)).read_text() for i in range(2)) == ["blocked", "entered"]
    finally:
        (tmp_path / "release").touch()
        for child in children:
            stdout, stderr = child.communicate(timeout=15)
            assert child.returncode == 0, stdout + stderr
    assert not admission.exists()


def test_stage5_evaluator_owns_lock_in_same_process():
    from stages.stage5_eval import command
    cmd = command({"kind": "plain", "model": "test", "name": "test"}, {})
    assert cmd[:5] == [sys.executable, "-u", "-m", "stages.gpu", "eval.baseline"]


@pytest.mark.parametrize("module,argv", [
    ("stages.load_smoke", ["--model", "test"]),
    ("stages.stage3_paraphrase", []),
    ("stages.stage4_qlora", []),
])
def test_stage_entry_points_reserve_and_release_before_work(admission, monkeypatch, module, argv):
    import importlib
    stage = importlib.import_module(module)
    observed = []
    def fake_run(args):
        observed.append(int(admission.read_text()))
    monkeypatch.setattr(stage, "run", fake_run)
    monkeypatch.setattr(sys, "argv", [module, *argv])
    stage.main()
    assert observed == [os.getpid()]
    assert not admission.exists()


def test_preflight_report_keeps_warnings_separate(admission, monkeypatch, tmp_path, capsys):
    from stages import preflight
    monkeypatch.setattr(preflight, "ROOT", tmp_path)
    for name in ("locked_model", "snapshot"):
        monkeypatch.setattr(preflight, name, lambda *a: "test")
    for name in ("bnb", "disk", "frozen"):
        monkeypatch.setattr(preflight, name, lambda: "test")
    monkeypatch.setattr(sys, "argv", ["preflight", "--out", "report.json"])
    with pytest.raises(SystemExit) as result:
        preflight.main()
    assert result.value.code == 0
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["passed"]
    assert report["warnings"]
    assert "WARNING" in capsys.readouterr().out
