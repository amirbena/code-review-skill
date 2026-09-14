"""Unit tests for scripts/sandbox/linux_bwrap.py argv construction (Issue #302).

Mocks run_bounded to capture the constructed bwrap argv without invoking
the real binary — these run on any host, Linux or not, since bwrap is
never actually available here (see tests/integration/sandbox for the
disclosed lack of a live Linux host to prove real containment).
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.sandbox import linux_bwrap
from scripts.sandbox.boundary import SandboxLimits, SandboxRequest
from scripts.sandbox.process_exec import BoundedRunResult
from scripts.sandbox.workspace import prepare_workspace


def _bounded() -> BoundedRunResult:
    return BoundedRunResult(
        exit_code=0, stdout="", stderr="", timed_out=False,
        output_truncated=False, filesystem_growth_exceeded=False, duration_seconds=0.1,
    )


class LinuxBwrapArgvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = Path(tempfile.mkdtemp())
        (self.source / "app.py").write_text("value = 1\n")
        self.workspace = prepare_workspace(self.source)
        self.addCleanup(self.workspace.teardown)
        self.addCleanup(shutil.rmtree, self.source, True)

    def _run(self, request: SandboxRequest):
        with mock.patch.object(linux_bwrap, "run_bounded", return_value=_bounded()) as run_bounded:
            linux_bwrap.run(request, self.workspace)
        return run_bounded.call_args

    def test_every_namespace_is_unshared(self) -> None:
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        args, _ = self._run(request)
        self.assertIn("--unshare-all", args[0])

    def test_dies_with_parent_and_runs_in_a_new_session(self) -> None:
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        args, _ = self._run(request)
        argv = args[0]
        self.assertIn("--die-with-parent", argv)
        self.assertIn("--new-session", argv)

    def test_work_copy_is_bind_mounted_read_write_at_workspace(self) -> None:
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        args, _ = self._run(request)
        argv = args[0]
        bind_index = argv.index("--bind")
        self.assertEqual(argv[bind_index + 1], str(self.workspace.work_copy.resolve()))
        self.assertEqual(argv[bind_index + 2], "/workspace")

    def test_read_only_inputs_are_ro_bound(self) -> None:
        extra = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, extra, True)
        request = SandboxRequest(
            argv=("true",), source_dir=self.source, read_only_inputs=(extra,), limits=SandboxLimits()
        )
        args, _ = self._run(request)
        argv = args[0]
        extra_index = argv.index(str(extra.resolve()))
        self.assertEqual(argv[extra_index - 1], "--ro-bind")
        self.assertEqual(argv[extra_index + 1], "/ro/0")

    def test_system_roots_are_ro_bound_only_when_present_on_this_host(self) -> None:
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        args, _ = self._run(request)
        argv = args[0]
        for root in linux_bwrap._SYSTEM_RO_BINDS:
            with self.subTest(root=root):
                if Path(root).is_dir():
                    self.assertIn(root, argv)
                else:
                    self.assertNotIn(root, argv)

    def test_home_and_path_are_set_to_sandbox_values(self) -> None:
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        args, _ = self._run(request)
        argv = args[0]
        self.assertIn("HOME", argv)
        self.assertEqual(argv[argv.index("HOME") + 1], "/home/sandbox")
        self.assertIn("PATH", argv)

    def test_the_admitted_command_is_the_final_argv_and_is_passed_through_unmodified(self) -> None:
        request = SandboxRequest(
            argv=("python3", "-c", "print(1)"), source_dir=self.source, limits=SandboxLimits()
        )
        args, _ = self._run(request)
        argv = args[0]
        self.assertEqual(argv[-3:], ("python3", "-c", "print(1)"))

    def test_no_network_sharing_flag_is_ever_present(self) -> None:
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        args, _ = self._run(request)
        argv = args[0]
        self.assertNotIn("--share-net", argv)
