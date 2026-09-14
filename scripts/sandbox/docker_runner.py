"""Docker-container primitive: its own network/mount/pid namespace and cgroup limits.

The container is disposable (``--rm``) and additionally force-removed after
every run by name, so a client-side kill on timeout can never leave a live
container behind.
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from pathlib import Path

from scripts.sandbox.boundary import SandboxRequest
from scripts.sandbox.capability import docker_client_env
from scripts.sandbox.process_exec import BoundedRunResult, run_bounded
from scripts.sandbox.workspace import SandboxWorkspace

DEFAULT_IMAGE = "python:3.12-slim"


def _resolve_docker_bin() -> str:
    """Resolve docker's absolute path once, via the real ambient PATH.

    Every docker invocation in this module uses this resolved path as
    argv[0] rather than the bare string "docker" — docker_client_env()'s
    PATH is a fixed, minimal list for the *env* the docker process itself
    runs with, and must not double as the lookup path for finding docker
    in the first place. A host where docker lives outside that fixed list
    (Homebrew on Apple Silicon, a Linux snap, a nix profile, ...) would
    otherwise pass detection (shutil.which uses the real ambient PATH) and
    then fail every actual invocation (bare "docker" resolved only against
    the fixed list) — including _force_remove, silently leaving a
    container behind.
    """
    return shutil.which("docker") or "docker"


def _force_remove(container_name: str) -> None:
    subprocess.run(
        [_resolve_docker_bin(), "rm", "-f", container_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=docker_client_env(),
        timeout=15,
    )


def run(
    request: SandboxRequest, workspace: SandboxWorkspace, image: str = DEFAULT_IMAGE
) -> BoundedRunResult:
    container_name = f"crs-sandbox-{uuid.uuid4().hex[:12]}"
    mounts = ["-v", f"{workspace.work_copy.resolve()}:/workspace:rw"]
    for index, extra in enumerate(request.read_only_inputs):
        mounts += ["-v", f"{Path(extra).resolve()}:/ro/{index}:ro"]

    limits = request.limits
    docker_bin = _resolve_docker_bin()
    docker_argv = (
        docker_bin,
        "run",
        "--rm",
        "--name",
        container_name,
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        str(limits.max_processes),
        "--memory",
        str(limits.memory_bytes),
        "--memory-swap",
        str(limits.memory_bytes),
        "--cpus",
        "1",
        "--user",
        "65534:65534",
        *mounts,
        "-w",
        f"/workspace/{request.cwd_relative}".rstrip("/."),
        "-e",
        "HOME=/tmp",
        "-e",
        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        image,
        *request.argv,
    )
    try:
        result = run_bounded(
            docker_argv,
            cwd=str(workspace.root),
            env=docker_client_env(),
            limits=limits,
            growth_watch_dir=str(workspace.work_copy),
            # The docker CLI client's own CPU/memory/process needs are
            # unrelated to the sandbox budget; the container's payload is
            # already bounded above via --memory/--cpus/--pids-limit.
            apply_resource_limits=False,
        )
    finally:
        _force_remove(container_name)
    return result
