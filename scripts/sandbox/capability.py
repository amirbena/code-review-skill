"""Platform isolation-primitive detection.

Never assumes a primitive is present; every check actually probes the host.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from enum import Enum


class Primitive(Enum):
    """A concrete, testable isolation mechanism this host can provide."""

    MACOS_SEATBELT = "macos-seatbelt"
    DOCKER = "docker"
    LINUX_BWRAP = "linux-bwrap"


# Passed through from the ambient environment when set, so a host that
# needs one of these to reach its Docker daemon (a non-default context
# such as Colima/OrbStack, or a relocated ~/.docker/config.json) behaves
# identically at detection time and at actual run time — see
# docker_client_env().
_DOCKER_ENV_PASSTHROUGH = (
    "DOCKER_HOST",
    "DOCKER_CONTEXT",
    "DOCKER_CONFIG",
    "DOCKER_TLS_VERIFY",
    "DOCKER_CERT_PATH",
)


def docker_client_env() -> dict[str, str]:
    """Minimal env for invoking the `docker` CLI itself.

    Used identically by _docker_available() (detection) and
    docker_runner.run() (actual execution) so the two never disagree: a
    host whose Docker CLI needs DOCKER_HOST/DOCKER_CONFIG/etc. to reach
    its daemon either passes both or neither, never "detected available"
    then fails to actually run.
    """
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"}
    for name in _DOCKER_ENV_PASSTHROUGH:
        value = os.environ.get(name)
        if value:
            env[name] = value
    return env


def resolve_docker_bin() -> str | None:
    """Resolve docker's absolute path once, via the real ambient PATH.

    The single source of truth for every docker invocation in this
    package (_docker_available() here, and docker_runner.py's run() and
    _force_remove()) — never the bare string "docker" resolved against
    docker_client_env()'s fixed, minimal PATH, which is an *execution*
    env, not a lookup path guaranteed to contain wherever this host's
    docker actually lives (Homebrew on Apple Silicon, a Linux snap, a nix
    profile, ...). A host where docker lives outside that fixed list
    would otherwise pass detection (shutil.which uses the real ambient
    PATH) and then fail every actual invocation.
    """
    return shutil.which("docker")


def _docker_available() -> bool:
    docker_bin = resolve_docker_bin()
    if docker_bin is None:
        return False
    try:
        result = subprocess.run(
            [docker_bin, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=docker_client_env(),
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _macos_seatbelt_available() -> bool:
    return platform.system() == "Darwin" and shutil.which("sandbox-exec") is not None


def _linux_bwrap_available() -> bool:
    return platform.system() == "Linux" and shutil.which("bwrap") is not None


# Ordered by isolation strength / portability, not detection cost. Docker's
# container boundary (own network namespace, cgroup limits, throwaway
# rootfs) is preferred over a native profile when both are available.
# `unshare` alone is deliberately excluded: without a hand-built mount
# namespace it cannot be verified to also confine the filesystem, and
# offering it would be exactly the silent isolation downgrade this runner
# must never perform.
_PROBES: tuple[tuple[Primitive, "callable"], ...] = (
    (Primitive.DOCKER, _docker_available),
    (Primitive.MACOS_SEATBELT, _macos_seatbelt_available),
    (Primitive.LINUX_BWRAP, _linux_bwrap_available),
)


def detect_primitive() -> Primitive | None:
    """Return the strongest isolation primitive this host actually has, or None."""
    for primitive, probe in _PROBES:
        if probe():
            return primitive
    return None


def available_primitives() -> tuple[Primitive, ...]:
    """All primitives this host has, strongest first — for diagnostics only."""
    return tuple(primitive for primitive, probe in _PROBES if probe())
