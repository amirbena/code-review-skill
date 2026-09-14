"""Bounded, non-interactive subprocess execution shared by every primitive.

Applies the resource ceilings from SandboxLimits and tears down the whole
process group plus every tracked descendant — see _expand_descendants for
the one documented residual gap on a primitive without its own PID
namespace. Output is read incrementally and capped so an output-flooding
payload cannot grow this process's own memory past budget before it is
killed.
"""

from __future__ import annotations

import os
import resource
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass

from scripts.sandbox.boundary import SandboxLimits


@dataclass
class BoundedRunResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    output_truncated: bool
    filesystem_growth_exceeded: bool
    duration_seconds: float


def _all_pid_ppid_pairs() -> list[tuple[int, int]]:
    try:
        output = subprocess.run(
            ["ps", "-A", "-o", "pid=,ppid="],
            capture_output=True, text=True, timeout=5,
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    pairs = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) == 2:
            try:
                pairs.append((int(parts[0]), int(parts[1])))
            except ValueError:
                continue
    return pairs


def _expand_descendants(known: set[int]) -> set[int]:
    """Add any process whose ppid chain resolves into ``known`` right now.

    A best-effort sweep against a daemonizing child that re-parents via its
    own setsid before this catches it — see docs/threat-model note on
    SBOX-011 for the acknowledged limit on primitives without a PID
    namespace (native Seatbelt).
    """
    pairs = _all_pid_ppid_pairs()
    changed = True
    while changed:
        changed = False
        for pid, ppid in pairs:
            if ppid in known and pid not in known:
                known.add(pid)
                changed = True
    return known


def _dir_size_bytes(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                continue
    return total


def _preexec(limits: SandboxLimits) -> None:
    # New session/process group so the whole descendant tree can be killed
    # as a unit; RLIMIT_NPROC is a delta over the current usage so this
    # never starves unrelated processes already owned by the same user.
    try:
        os.setsid()
    except OSError:
        pass
    current_nproc = resource.getrlimit(resource.RLIMIT_NPROC)[0]
    budget = current_nproc + limits.max_processes if current_nproc > 0 else limits.max_processes
    for rlimit, value in (
        (resource.RLIMIT_CPU, limits.cpu_seconds),
        (resource.RLIMIT_AS, limits.memory_bytes),
        (resource.RLIMIT_NPROC, budget),
    ):
        try:
            resource.setrlimit(rlimit, (value, value))
        except (ValueError, OSError):
            continue


def _kill_process_group(process: subprocess.Popen, known_descendants: set[int]) -> None:
    own_pgid = os.getpgrp()
    if process.poll() is None:
        try:
            child_pgid = os.getpgid(process.pid)
        except (ProcessLookupError, OSError):
            child_pgid = None
        # Only kill the process group if setsid actually put the child in
        # its own group — never send SIGKILL to this caller's own group.
        if child_pgid is not None and child_pgid != own_pgid:
            try:
                os.killpg(child_pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                pass
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    # Final sweep: kill any tracked descendant individually — catches a
    # daemonizing child that detached into its own session before the
    # group kill above could reach it.
    for pid in _expand_descendants(known_descendants):
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            continue


def run_bounded(
    argv: tuple[str, ...],
    cwd: str,
    env: dict[str, str],
    limits: SandboxLimits,
    growth_watch_dir: str | None = None,
) -> BoundedRunResult:
    start = time.monotonic()
    process = subprocess.Popen(
        list(argv),
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=lambda: _preexec(limits),
        start_new_session=True,
    )
    known_descendants = {process.pid}
    # A forked grandchild shares its parent's pgid only until it calls its
    # own setsid() to detach — typically within milliseconds of forking.
    # Poll tightly right away to catch it (via the ppid chain) while it is
    # still traceable, before that detach can race ahead of us.
    burst_until = start + 0.5
    while time.monotonic() < burst_until and process.poll() is None:
        _expand_descendants(known_descendants)
        time.sleep(0.005)

    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    buffers: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}
    total_bytes = 0
    truncated = False
    timed_out = False
    growth_exceeded = False
    deadline = start + limits.wall_clock_seconds
    next_growth_check = start

    open_streams = {"stdout", "stderr"}
    while open_streams:
        now = time.monotonic()
        remaining = deadline - now
        if remaining <= 0:
            timed_out = True
            break
        if growth_watch_dir is not None and now >= next_growth_check:
            next_growth_check = now + 1.0
            if _dir_size_bytes(growth_watch_dir) > limits.max_filesystem_growth_bytes:
                growth_exceeded = True
                break
        _expand_descendants(known_descendants)
        for key, _mask in selector.select(timeout=min(0.25, remaining)):
            stream = key.data
            chunk = os.read(key.fileobj.fileno(), 65536)
            if not chunk:
                selector.unregister(key.fileobj)
                open_streams.discard(stream)
                continue
            total_bytes += len(chunk)
            if total_bytes > limits.max_output_bytes:
                truncated = True
                remaining_budget = limits.max_output_bytes - (total_bytes - len(chunk))
                if remaining_budget > 0:
                    buffers[stream].extend(chunk[:remaining_budget])
                break
            buffers[stream].extend(chunk)
        if truncated:
            break
        if process.poll() is not None and not open_streams:
            break

    selector.close()
    _kill_process_group(process, known_descendants)
    process.stdout.close()
    process.stderr.close()
    duration = time.monotonic() - start

    exit_code = None if (timed_out or truncated or growth_exceeded) else process.returncode
    return BoundedRunResult(
        exit_code=exit_code,
        stdout=bytes(buffers["stdout"]).decode("utf-8", "replace"),
        stderr=bytes(buffers["stderr"]).decode("utf-8", "replace"),
        timed_out=timed_out,
        output_truncated=truncated,
        filesystem_growth_exceeded=growth_exceeded,
        duration_seconds=duration,
    )
