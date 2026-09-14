"""Platform isolation-primitive detection.

Never assumes a primitive is present; every check actually probes the host.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from enum import Enum


class Primitive(Enum):
    """A concrete, testable isolation mechanism this host can provide."""

    MACOS_SEATBELT = "macos-seatbelt"
    DOCKER = "docker"
    LINUX_BWRAP = "linux-bwrap"


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
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
