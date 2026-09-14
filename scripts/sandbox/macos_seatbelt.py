"""macOS Seatbelt (sandbox-exec) primitive.

Rule order matters for SBPL: the *last* rule that matches an operation
wins, not the most specific one. Every deny below is therefore declared
before the narrower allow that carves an exception out of it.
"""

from __future__ import annotations

import os
from pathlib import Path

from scripts.sandbox.boundary import SandboxRequest
from scripts.sandbox.process_exec import BoundedRunResult, run_bounded
from scripts.sandbox.workspace import SandboxWorkspace

# Roots a process needs read access to merely to start (interpreter,
# shared libraries, locale data) — never anything containing a
# reviewer's own home-directory or scratch content.
_SYSTEM_READ_ROOTS = (
    "/usr",
    "/bin",
    "/sbin",
    "/System",
    "/Library",
    "/private/etc",
    "/private/var/db",
    "/private/var/select",
    "/dev",
    "/opt",
    "/Applications",
)

# Shared or per-user host state that must stay out of reach regardless of
# where it lives: other users' home directories, other mounted volumes,
# and — critically — the shared scratch/temp areas where an unrelated
# checkout, another process's temp files, or this host's own shared /tmp
# content live. The ephemeral workspace itself is carved back out with a
# narrower allow declared after these (see build_profile).
_ALWAYS_DENIED_READ_ROOTS = (
    "/Users",
    "/var/root",
    "/root",
    "/Library/Keychains",
    "/private/var/root",
    "/Volumes",
    "/private/var/folders",
    "/var/folders",
    "/private/tmp",
    "/tmp",
)


def _quote(path: str) -> str:
    return path.replace("\\", "\\\\").replace('"', '\\"')


def build_profile(
    workspace_root: Path, read_only_inputs: tuple[Path, ...]
) -> str:
    workspace_root = str(workspace_root.resolve())
    lines = [
        "(version 1)",
        "(allow default)",
        "(deny network*)",
        '(deny file-write* (subpath "/"))',
        f'(allow file-write* (subpath "{_quote(workspace_root)}"))',
    ]
    for root in _ALWAYS_DENIED_READ_ROOTS:
        if os.path.isdir(root):
            lines.append(f'(deny file-read* (subpath "{_quote(root)}"))')
    for root in _SYSTEM_READ_ROOTS:
        if os.path.isdir(root):
            lines.append(f'(allow file-read* (subpath "{_quote(root)}"))')
    # Declared last so it wins even though the ephemeral workspace itself
    # commonly lives inside a denied scratch root above.
    lines.append(f'(allow file-read* (subpath "{_quote(workspace_root)}"))')
    for extra in read_only_inputs:
        resolved = str(Path(extra).resolve())
        lines.append(f'(allow file-read* (subpath "{_quote(resolved)}"))')
    return "\n".join(lines) + "\n"


def _scrubbed_env(workspace: SandboxWorkspace) -> dict[str, str]:
    fake_home = workspace.root / "home"
    fake_tmp = workspace.root / "tmp"
    fake_tmp.mkdir(parents=True, exist_ok=True)
    return {
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": str(fake_home),
        "TMPDIR": str(fake_tmp),
        "LANG": "en_US.UTF-8",
    }


def run(request: SandboxRequest, workspace: SandboxWorkspace) -> BoundedRunResult:
    fake_home = workspace.root / "home"
    fake_tmp = workspace.root / "tmp"
    fake_home.mkdir(parents=True, exist_ok=True)
    fake_tmp.mkdir(parents=True, exist_ok=True)
    profile = build_profile(workspace.root, request.read_only_inputs)
    profile_path = workspace.root / "profile.sb"
    profile_path.write_text(profile)

    cwd = str((workspace.work_copy / request.cwd_relative).resolve())
    argv = ("/usr/bin/sandbox-exec", "-f", str(profile_path), *request.argv)
    return run_bounded(
        argv,
        cwd=cwd,
        env=_scrubbed_env(workspace),
        limits=request.limits,
        growth_watch_dir=str(workspace.root),
    )
