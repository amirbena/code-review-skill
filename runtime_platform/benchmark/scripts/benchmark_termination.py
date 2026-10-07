"""Catchable-termination handling for the benchmark process tree (Issue #660).

SIGTERM/SIGHUP become a `Terminated` exception in the main thread, so each level unwinds, stops the
process group it started, and leaves a best-effort `[terminated]` stderr line. Nothing here changes
timeouts, scoring or the stdout contract; SIGKILL cannot be caught, so on it no line is written.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
from contextlib import contextmanager
from typing import Callable, Iterator, Mapping, Sequence

TERMINATED_PREFIX = "[terminated]"
HANDLED_SIGNALS = tuple(s for s in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGHUP", None)) if s is not None)
# The parent waits longer than the child's own cleanup so the child can stop its review CLI first.
PARENT_GRACE_S = 15.0
CHILD_GRACE_S = 5.0
KILL_WAIT_S = 3.0


class Terminated(BaseException):
    """Raised by the signal handler; a BaseException so `except Exception` diagnostics never swallow it."""

    def __init__(self, signum: int, phase: str = "unknown", case: str | None = None) -> None:
        super().__init__(signum)
        self.signum = signum
        self.phase = phase  # snapshotted when the signal arrived, before unwinding restores outer state
        self.case = case

    def __str__(self) -> str:
        return f"terminated by {self.signal_name}"

    @property
    def signal_name(self) -> str:
        try:
            return signal.Signals(self.signum).name
        except ValueError:
            return str(self.signum)

    @property
    def exit_code(self) -> int:
        return 128 + self.signum


@contextmanager
def terminate_on_signal(where: Callable[[], tuple[str, str | None]] | None = None) -> Iterator[None]:
    """Turn the first catchable termination signal into `Terminated`; later ones are ignored mid-cleanup.

    `where` returns the current (phase, case), read at signal time.
    """
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    fired = False

    def handler(signum: int, _frame: object) -> None:
        nonlocal fired
        if fired:
            return
        fired = True
        phase, case = where() if where is not None else ("unknown", None)
        raise Terminated(signum, phase, case)  # no logging here: the handler may interrupt a held logging lock

    # A signal the launcher deliberately ignores (e.g. SIGHUP under nohup) stays ignored.
    managed = [sig for sig in HANDLED_SIGNALS if signal.getsignal(sig) is not signal.SIG_IGN]
    previous = {sig: signal.signal(sig, handler) for sig in managed}
    try:
        yield
    finally:
        for sig, old in previous.items():
            signal.signal(sig, old)


def terminated_line(exc: Terminated) -> str:
    return f"{TERMINATED_PREFIX} signal={exc.signal_name} phase={exc.phase} case={exc.case or 'unknown'}"


def _signal_group(proc: subprocess.Popen, sig: int) -> None:
    try:
        if hasattr(os, "killpg"):
            os.killpg(proc.pid, sig)  # the child was started as its own group leader
        elif sig == signal.SIGTERM:
            proc.terminate()
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError):
        pass


def _group_alive(proc: subprocess.Popen) -> bool:
    if not hasattr(os, "killpg"):
        return proc.poll() is None
    try:
        os.killpg(proc.pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def stop_process_tree(proc: subprocess.Popen, grace_s: float) -> None:
    """SIGTERM the child's process group, wait at most `grace_s`, then SIGKILL it; always bounded."""
    _signal_group(proc, signal.SIGTERM)
    try:
        proc.wait(timeout=grace_s)
    except subprocess.TimeoutExpired:
        pass
    # The leader may be gone while descendants linger; reap the leader, then force the group.
    if _group_alive(proc):
        _signal_group(proc, signal.SIGKILL)
    try:
        proc.wait(timeout=KILL_WAIT_S)
    except subprocess.TimeoutExpired:
        pass


def run_in_own_group(
    command: Sequence[str],
    *,
    cwd: str,
    timeout: float,
    env: Mapping[str, str] | None,
    grace_s: float = CHILD_GRACE_S,
) -> subprocess.CompletedProcess:
    """`subprocess.run(capture_output=True, text=True)` whose whole process group dies on timeout or termination."""
    proc = subprocess.Popen(
        list(command),
        cwd=cwd,
        env=None if env is None else dict(env),
        stdin=subprocess.DEVNULL,  # the new session has no controlling terminal to read from
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        stop_process_tree(proc, grace_s)
        exc.stdout, exc.stderr = None, None
        raise
    except BaseException:
        stop_process_tree(proc, grace_s)
        raise
    return subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
