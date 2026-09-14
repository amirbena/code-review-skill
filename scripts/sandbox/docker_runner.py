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


def _force_remove(container_name: str) -> None:
    subprocess.run(
        ["docker", "rm", "-f", container_name],
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
    docker_bin = shutil.which("docker") or "docker"
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
        )
    finally:
        _force_remove(container_name)
    return result
