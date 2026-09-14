"""Unit tests for scripts/sandbox/process_exec.py (Issue #302).

Runs real (unsandboxed) subprocesses to test the bounding mechanics in
isolation from any primitive; primitive-specific containment is covered by
tests/integration/sandbox.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.sandbox.boundary import SandboxLimits
from scripts.sandbox.process_exec import run_bounded

PY = sys.executable


class RunBoundedTests(unittest.TestCase):
    def test_successful_command_reports_exit_code_and_stdout(self) -> None:
        result = run_bounded(
            (PY, "-c", "print('ok')"), cwd=".", env={}, limits=SandboxLimits(wall_clock_seconds=10)
        )
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout.strip(), "ok")
        self.assertFalse(result.timed_out)

    def test_nonzero_exit_is_reported_not_raised(self) -> None:
        result = run_bounded(
            (PY, "-c", "import sys; sys.exit(3)"),
            cwd=".", env={}, limits=SandboxLimits(wall_clock_seconds=10),
        )
        self.assertEqual(result.exit_code, 3)

    def test_wall_clock_budget_terminates_a_long_running_command(self) -> None:
        result = run_bounded(
            (PY, "-c", "import time; time.sleep(30)"),
            cwd=".", env={}, limits=SandboxLimits(wall_clock_seconds=1),
        )
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_code)
        self.assertLess(result.duration_seconds, 10)

    def test_output_budget_truncates_a_flooding_command(self) -> None:
        result = run_bounded(
            (PY, "-c", "import sys\nwhile True:\n    sys.stdout.write('x' * 65536)"),
            cwd=".", env={},
            limits=SandboxLimits(wall_clock_seconds=10, max_output_bytes=10_000),
        )
        self.assertTrue(result.output_truncated)
        self.assertLessEqual(len(result.stdout.encode()), 10_000)

    def test_filesystem_growth_budget_terminates_a_flooding_writer(self) -> None:
        watch_dir = Path(tempfile.mkdtemp())
        try:
            script = (
                "f=open('bloat.bin','wb')\n"
                "while True:\n    f.write(b'0'*1048576); f.flush()"
            )
            result = run_bounded(
                (PY, "-c", script),
                cwd=str(watch_dir), env={},
                limits=SandboxLimits(wall_clock_seconds=10, max_filesystem_growth_bytes=3_000_000),
                growth_watch_dir=str(watch_dir),
            )
            self.assertTrue(result.filesystem_growth_exceeded)
            self.assertIsNone(result.exit_code)
        finally:
            shutil.rmtree(watch_dir, ignore_errors=True)

    def test_no_process_survives_an_undetached_background_child(self) -> None:
        """A background process that stays in the launched group is always killed.

        This is the ordinary SBOX-011 case: a validation command starts a
        background helper/daemon without itself racing to escape process
        tracking. The narrower "detaches via setsid before the very first
        poll" sub-case is a documented, best-effort limitation on a
        primitive without its own PID namespace — see
        test_process_group_kill_catches_a_fork_that_does_not_detach and the
        module docstring on _expand_descendants.
        """
        marker = Path(tempfile.mkdtemp()) / "marker.txt"
        script = (
            "import subprocess, time\n"
            f"subprocess.Popen(['sh', '-c', \"echo alive > {marker}; sleep 30\"])\n"
            "time.sleep(0.2)\n"
        )
        try:
            run_bounded((PY, "-c", script), cwd=".", env={}, limits=SandboxLimits(wall_clock_seconds=5))
            self.assertTrue(marker.exists())
            found = self._pgrep(str(marker))
            self.assertEqual(found, [], f"background descendant survived teardown: {found}")
        finally:
            shutil.rmtree(marker.parent, ignore_errors=True)

    @staticmethod
    def _pgrep(needle: str) -> list[str]:
        import subprocess

        output = subprocess.run(
            ["ps", "-A", "-o", "command"], capture_output=True, text=True, timeout=5
        ).stdout
        return [line for line in output.splitlines() if needle in line]
