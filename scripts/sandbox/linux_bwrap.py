"""Linux bubblewrap (bwrap) primitive: unprivileged user+mount+net namespaces."""

from __future__ import annotations

import shutil
from pathlib import Path

from scripts.sandbox.boundary import SandboxRequest
from scripts.sandbox.process_exec import BoundedRunResult, run_bounded
from scripts.sandbox.workspace import SandboxWorkspace

_SYSTEM_RO_BINDS = ("/usr", "/bin", "/sbin", "/lib", "/lib64", "/etc/alternatives")


def run(request: SandboxRequest, workspace: SandboxWorkspace) -> BoundedRunResult:
    work_copy = workspace.work_copy.resolve()
    fake_home = workspace.root / "home"
    argv: list[str] = [
        shutil.which("bwrap") or "/usr/bin/bwrap",
        "--die-with-parent",
        "--new-session",
        "--unshare-all",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--bind",
        str(work_copy),
        "/workspace",
        "--bind",
        str(fake_home),
        "/home/sandbox",
        "--chdir",
        f"/workspace/{request.cwd_relative}".rstrip("/."),
    ]
    for root in _SYSTEM_RO_BINDS:
        if Path(root).is_dir():
            argv += ["--ro-bind", root, root]
    for index, extra in enumerate(request.read_only_inputs):
        resolved = str(Path(extra).resolve())
        argv += ["--ro-bind", resolved, f"/ro/{index}"]
    argv += ["--setenv", "HOME", "/home/sandbox"]
    argv += ["--setenv", "PATH", "/usr/bin:/bin:/usr/sbin:/sbin"]
    argv += list(request.argv)

    return run_bounded(
        tuple(argv),
        cwd=str(workspace.root),
        env={},
        limits=request.limits,
        growth_watch_dir=str(work_copy),
    )
