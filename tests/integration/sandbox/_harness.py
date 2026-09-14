"""Shared harness for real, non-mocked sandbox integration tests.

Every test in this package exercises actual host isolation primitives
(macOS Seatbelt, Docker) with real hostile payloads. A primitive genuinely
absent from the host is reported as a skip, never folded into a pass.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.sandbox import capability
from scripts.sandbox.boundary import Outcome, SandboxLimits, SandboxRequest
from scripts.sandbox.runner import SandboxRunner

PRIMITIVES: tuple[capability.Primitive, ...] = capability.available_primitives()

# Command-launcher per primitive: Seatbelt runs the host's own interpreter,
# the Docker image supplies its own `python3` on PATH inside the container.
_PY_FOR_PRIMITIVE = {
    capability.Primitive.MACOS_SEATBELT: sys.executable,
    capability.Primitive.DOCKER: "python3",
}


@unittest.skipUnless(PRIMITIVES, "no sandbox isolation primitive available on this host")
class SandboxIntegrationCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp(prefix="crs-sandbox-src-")
        self.source_dir = Path(self._tmp)
        (self.source_dir / "app.py").write_text("value = 1\n")
        (self.source_dir / ".git").mkdir()
        (self.source_dir / ".git" / "config").write_text("[core]\n")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)

    def run_python(
        self,
        primitive: capability.Primitive,
        code: str,
        limits: SandboxLimits | None = None,
        read_only_inputs: tuple[Path, ...] = (),
    ):
        runner = SandboxRunner(primitive=primitive)
        request = SandboxRequest(
            argv=(_PY_FOR_PRIMITIVE[primitive], "-c", code),
            source_dir=self.source_dir,
            read_only_inputs=read_only_inputs,
            limits=limits or SandboxLimits(wall_clock_seconds=20),
        )
        return runner.run(request)

    def run_argv(
        self,
        primitive: capability.Primitive,
        argv: tuple[str, ...],
        limits: SandboxLimits | None = None,
    ):
        runner = SandboxRunner(primitive=primitive)
        request = SandboxRequest(
            argv=argv, source_dir=self.source_dir, limits=limits or SandboxLimits(wall_clock_seconds=20)
        )
        return runner.run(request)

    def assert_denied(self, result, msg: str = "") -> None:
        """The payload must never succeed — containment, denial, or termination only."""
        self.assertIn(result.outcome, (Outcome.FAILED, Outcome.UNAVAILABLE), msg or result.stderr)
        self.assertNotIn("PAYLOAD-SUCCEEDED", result.stdout, msg or "hostile payload marker leaked")


def host_process_names(pattern: str) -> list[str]:
    """Best-effort host process listing, used only to assert no persistence."""
    try:
        output = subprocess.run(
            ["ps", "-A", "-o", "command"], capture_output=True, text=True, timeout=10
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [line for line in output.splitlines() if pattern in line]
