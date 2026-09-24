"""Unit tests for scripts/sandbox/runner.py orchestration (Issue #302).

Mocks the primitive-specific run() functions so this file stays fast and
focused on dispatch/result-mapping; real containment is proven by
tests/integration/sandbox.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.sandbox import capability, runner
from scripts.sandbox.boundary import Outcome, SandboxLimits, SandboxRequest
from scripts.sandbox.process_exec import BoundedRunResult


def _bounded(**overrides) -> BoundedRunResult:
    base = dict(
        exit_code=0, stdout="", stderr="", timed_out=False,
        output_truncated=False, filesystem_growth_exceeded=False, duration_seconds=0.1,
    )
    base.update(overrides)
    return BoundedRunResult(**base)


class SandboxRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source_dir = Path(tempfile.mkdtemp())
        (self.source_dir / "app.py").write_text("value = 1\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.source_dir, ignore_errors=True)

    def _request(self) -> SandboxRequest:
        return SandboxRequest(argv=("true",), source_dir=self.source_dir, limits=SandboxLimits())

    def test_no_primitive_available_returns_unavailable_and_never_runs(self) -> None:
        run_instance = runner.SandboxRunner(primitive=None)
        result = run_instance.run(self._request())
        self.assertEqual(result.outcome, Outcome.UNAVAILABLE)
        self.assertIn("no isolation primitive", result.reason)

    def test_successful_run_maps_to_executed(self) -> None:
        with mock.patch.dict(
            runner._DISPATCH, {capability.Primitive.MACOS_SEATBELT: lambda req, ws: _bounded(exit_code=0)}
        ):
            run_instance = runner.SandboxRunner(primitive=capability.Primitive.MACOS_SEATBELT)
            result = run_instance.run(self._request())
        self.assertEqual(result.outcome, Outcome.EXECUTED)
        self.assertTrue(result.source_integrity_verified)

    def test_nonzero_exit_maps_to_failed(self) -> None:
        with mock.patch.dict(
            runner._DISPATCH, {capability.Primitive.MACOS_SEATBELT: lambda req, ws: _bounded(exit_code=1)}
        ):
            run_instance = runner.SandboxRunner(primitive=capability.Primitive.MACOS_SEATBELT)
            result = run_instance.run(self._request())
        self.assertEqual(result.outcome, Outcome.FAILED)

    def test_timeout_maps_to_failed_with_budget_reason(self) -> None:
        with mock.patch.dict(
            runner._DISPATCH,
            {capability.Primitive.MACOS_SEATBELT: lambda req, ws: _bounded(exit_code=None, timed_out=True)},
        ):
            run_instance = runner.SandboxRunner(primitive=capability.Primitive.MACOS_SEATBELT)
            result = run_instance.run(self._request())
        self.assertEqual(result.outcome, Outcome.FAILED)
        self.assertIn("wall-clock", result.reason)

    def test_missing_executable_maps_to_unavailable(self) -> None:
        def _raise(req, ws):
            raise FileNotFoundError("sandbox-exec")

        with mock.patch.dict(runner._DISPATCH, {capability.Primitive.MACOS_SEATBELT: _raise}):
            run_instance = runner.SandboxRunner(primitive=capability.Primitive.MACOS_SEATBELT)
            result = run_instance.run(self._request())
        self.assertEqual(result.outcome, Outcome.UNAVAILABLE)

    def _run_with(self, primitive: capability.Primitive, bounded: BoundedRunResult):
        with mock.patch.dict(runner._DISPATCH, {primitive: lambda req, ws: bounded}):
            return runner.SandboxRunner(primitive=primitive).run(self._request())

    def test_payload_launch_failure_maps_to_unavailable_not_failed(self) -> None:
        """#535: the launcher could not exec the payload, so no test ran."""
        cases = (
            (capability.Primitive.MACOS_SEATBELT, 71,
             "sandbox-exec: execvp() of 'pytest' failed: No such file or directory\n"),
            (capability.Primitive.LINUX_BWRAP, 1,
             "bwrap: execvp pytest: No such file or directory\n"),
            (capability.Primitive.DOCKER, 127,
             'docker: Error response from daemon: failed to create task for container: '
             'exec: "pytest": executable file not found in $PATH: unknown.\n'),
        )
        for primitive, exit_code, stderr in cases:
            with self.subTest(primitive=primitive):
                result = self._run_with(primitive, _bounded(exit_code=exit_code, stderr=stderr))
                self.assertEqual(result.outcome, Outcome.UNAVAILABLE)
                self.assertIn("could not launch", result.reason)
                self.assertIsNone(result.exit_code)

    def test_started_payload_failure_stays_failed(self) -> None:
        cases = (
            (capability.Primitive.MACOS_SEATBELT, 1, "FAILED tests/test_app.py::test_value\n", ""),
            (capability.Primitive.MACOS_SEATBELT, 71, "some unrelated error\n", ""),
            (capability.Primitive.MACOS_SEATBELT, 71,
             "sandbox-exec: execvp() of 'pytest' failed: No such file or directory\n", "collected 3 items\n"),
            (capability.Primitive.LINUX_BWRAP, 2, "bwrap: execvp pytest: No such file or directory\n", ""),
            (capability.Primitive.DOCKER, 127, "sh: 1: tool: not found\n", ""),
        )
        for primitive, exit_code, stderr, stdout in cases:
            with self.subTest(primitive=primitive, exit_code=exit_code, stderr=stderr):
                result = self._run_with(
                    primitive, _bounded(exit_code=exit_code, stderr=stderr, stdout=stdout)
                )
                self.assertEqual(result.outcome, Outcome.FAILED)
                self.assertEqual(result.exit_code, exit_code)

    def test_source_integrity_violation_never_reported_as_executed(self) -> None:
        with mock.patch.dict(
            runner._DISPATCH, {capability.Primitive.MACOS_SEATBELT: lambda req, ws: _bounded(exit_code=0)}
        ):
            with mock.patch("scripts.sandbox.runner.verify_source_unchanged", return_value=False):
                run_instance = runner.SandboxRunner(primitive=capability.Primitive.MACOS_SEATBELT)
                result = run_instance.run(self._request())
        self.assertEqual(result.outcome, Outcome.FAILED)
        self.assertIn("integrity", result.reason)

    def test_workspace_is_torn_down_even_when_the_run_raises(self) -> None:
        captured_workspace = {}

        def _raise(req, ws):
            captured_workspace["root"] = ws.root
            raise RuntimeError("boom")

        with mock.patch.dict(runner._DISPATCH, {capability.Primitive.MACOS_SEATBELT: _raise}):
            run_instance = runner.SandboxRunner(primitive=capability.Primitive.MACOS_SEATBELT)
            with self.assertRaises(RuntimeError):
                run_instance.run(self._request())
        self.assertFalse(captured_workspace["root"].exists())
