"""GPU admission uses free memory and an exclusive repo-local Aether PID lock."""
from contextlib import contextmanager
import errno
import os
from pathlib import Path
import subprocess
import sys
import time

from stages.common import ROOT

LOCK_PATH = ROOT / "logs/gpu.lock"
MIN_FREE_MIB = 10 * 1024


def smi(*args):
    return subprocess.check_output(["nvidia-smi", *args], text=True, timeout=20).strip()


def pid_alive(pid):
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE only; never terminate a process
        if not handle:
            return ctypes.get_last_error() != 87  # nonexistent PID; access denied counts as alive
        try:
            return kernel.WaitForSingleObject(handle, 0) != 0
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


@contextmanager
def lock_transaction(path):
    """Serialize stale-lock replacement and removal, including simultaneous starters.

    The tiny sidecar stays on disk; its OS lock is released even if a process crashes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock.guard").open("a+b") as guard:
        if guard.seek(0, 2) == 0:
            guard.write(b"0")
            guard.flush()
        deadline = time.monotonic() + 5
        while True:
            try:
                guard.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(guard.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)
        try:
            yield
        finally:
            guard.seek(0)
            if os.name == "nt":
                msvcrt.locking(guard.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(guard, fcntl.LOCK_UN)


def active_pid(path):
    if not path.exists():
        return None
    try:
        pid = int(path.read_text(encoding="ascii").strip())
        if pid <= 0:
            raise ValueError()
    except ValueError:
        raise ValueError(f"Invalid Aether GPU lock {path}; inspect it before starting a job") from None
    return pid if pid_alive(pid) else None


def gpu_idle():
    with lock_transaction(LOCK_PATH):
        pid = active_pid(LOCK_PATH)
        if pid is not None:
            raise ValueError(f"Aether GPU job already running (PID {pid})")
    return "No live Aether GPU lock (dead PIDs ignored)"


def gpu_free(threshold=MIN_FREE_MIB):
    free = [int(x) for x in smi("--query-gpu=memory.free", "--format=csv,noheader,nounits").splitlines()]
    if not free or free[0] < threshold:
        raise ValueError(f"GPU 0 needs at least {threshold / 1024:g} GiB free; MiB free: {free}")
    return {"free_mib": free, "minimum_mib": threshold}


def gpu_process_warnings():
    try:
        processes = smi("--query-compute-apps=pid,process_name", "--format=csv,noheader")
    except (OSError, subprocess.SubprocessError) as exc:
        return [f"GPU process names unavailable ({type(exc).__name__}); admission uses memory and the Aether lock"]
    if processes:
        return [f"GPU processes may include Windows desktop or unreadable apps; informational only:\n{processes}"]
    return []


@contextmanager
def gpu_job():
    """Reserve the GPU before checking memory; release on success or Python exceptions."""
    pid = os.getpid()
    with lock_transaction(LOCK_PATH):
        other = active_pid(LOCK_PATH)
        if other is not None:
            raise ValueError(f"Aether GPU job already running (PID {other})")
        LOCK_PATH.write_text(str(pid), encoding="ascii")
    try:
        gpu_free()
        for warning in gpu_process_warnings():
            print(f"WARNING {warning}", flush=True)
        yield
    finally:
        with lock_transaction(LOCK_PATH):
            if LOCK_PATH.exists() and LOCK_PATH.read_text(encoding="ascii").strip() == str(pid):
                LOCK_PATH.unlink()


def main():
    # Stage 5 runs the evaluator IN this process so the recorded PID owns the GPU,
    # even if its orchestrating parent exits unexpectedly.
    import runpy
    module, *args = sys.argv[1:]
    if module not in {"eval.baseline", "eval.repair", "eval.constrained"}:
        raise ValueError("Only Aether evaluation modules can use this runner")
    sys.argv = [module, *args]
    with gpu_job():
        runpy.run_module(module, run_name="__main__")


if __name__ == "__main__":
    main()
