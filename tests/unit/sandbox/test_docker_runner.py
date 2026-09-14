"""Unit tests for scripts/sandbox/docker_runner.py argv construction (Issue #302).

Mocks run_bounded and _force_remove to capture the constructed docker argv
without invoking the real binary — these run on any host, Docker or not.
Real containment (network/pids/memory actually enforced) is proven by
tests/integration/sandbox/test_adversarial_containment.py.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.sandbox import docker_runner
from scripts.sandbox.boundary import SandboxLimits, SandboxRequest
from scripts.sandbox.process_exec import BoundedRunResult
from scripts.sandbox.workspace import prepare_workspace


def _bounded() -> BoundedRunResult:
    return BoundedRunResult(
        exit_code=0, stdout="", stderr="", timed_out=False,
        output_truncated=False, filesystem_growth_exceeded=False, duration_seconds=0.1,
    )


class DockerRunnerArgvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = Path(tempfile.mkdtemp())
        (self.source / "app.py").write_text("value = 1\n")
        self.workspace = prepare_workspace(self.source)
        self.addCleanup(self.workspace.teardown)
        self.addCleanup(shutil.rmtree, self.source, True)

    def _run(self, request: SandboxRequest):
        with mock.patch.object(docker_runner, "run_bounded", return_value=_bounded()) as run_bounded:
            with mock.patch.object(docker_runner, "_force_remove"):
                docker_runner.run(request, self.workspace)
        return run_bounded.call_args

    def test_network_is_set_to_none(self) -> None:
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        args, _ = self._run(request)
        argv = args[0]
        self.assertIn("--network", argv)
        self.assertEqual(argv[argv.index("--network") + 1], "none")

    def test_capabilities_are_dropped_and_privilege_escalation_denied(self) -> None:
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        args, _ = self._run(request)
        argv = args[0]
        self.assertIn("--cap-drop", argv)
        self.assertEqual(argv[argv.index("--cap-drop") + 1], "ALL")
        self.assertIn("--security-opt", argv)
        self.assertEqual(argv[argv.index("--security-opt") + 1], "no-new-privileges")

    def test_runs_as_an_unprivileged_uid(self) -> None:
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        args, _ = self._run(request)
        argv = args[0]
        self.assertIn("--user", argv)
        self.assertNotEqual(argv[argv.index("--user") + 1], "0:0")

    def test_resource_limits_are_propagated_from_the_request(self) -> None:
        limits = SandboxLimits(max_processes=17, memory_bytes=123_456)
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=limits)
        args, _ = self._run(request)
        argv = args[0]
        self.assertEqual(argv[argv.index("--pids-limit") + 1], "17")
        self.assertEqual(argv[argv.index("--memory") + 1], "123456")
        self.assertEqual(argv[argv.index("--memory-swap") + 1], "123456")

    def test_work_copy_is_mounted_read_write_at_workspace(self) -> None:
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        args, _ = self._run(request)
        argv = args[0]
        mount = f"{self.workspace.work_copy.resolve()}:/workspace:rw"
        self.assertIn(mount, argv)

    def test_read_only_inputs_are_mounted_read_only(self) -> None:
        extra = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, extra, True)
        request = SandboxRequest(
            argv=("true",), source_dir=self.source, read_only_inputs=(extra,), limits=SandboxLimits()
        )
        args, _ = self._run(request)
        argv = args[0]
        self.assertIn(f"{extra.resolve()}:/ro/0:ro", argv)

    def test_the_admitted_command_is_the_final_argv_and_is_passed_through_unmodified(self) -> None:
        request = SandboxRequest(
            argv=("python3", "-c", "print(1)"), source_dir=self.source, limits=SandboxLimits()
        )
        args, _ = self._run(request)
        argv = args[0]
        self.assertEqual(argv[-3:], ("python3", "-c", "print(1)"))

    def test_container_is_force_removed_even_when_run_bounded_raises(self) -> None:
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        with mock.patch.object(docker_runner, "run_bounded", side_effect=RuntimeError("boom")):
            with mock.patch.object(docker_runner, "_force_remove") as force_remove:
                with self.assertRaises(RuntimeError):
                    docker_runner.run(request, self.workspace)
                force_remove.assert_called_once()

    def test_run_uses_the_same_client_env_as_capability_detection(self) -> None:
        # Detection (capability._docker_available) and execution must
        # agree, or a host needing DOCKER_HOST/DOCKER_CONFIG can pass
        # detection and then fail to actually run.
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        with mock.patch.object(docker_runner, "run_bounded", return_value=_bounded()) as run_bounded:
            with mock.patch.object(docker_runner, "_force_remove"):
                docker_runner.run(request, self.workspace)
        self.assertEqual(run_bounded.call_args.kwargs["env"], docker_runner.docker_client_env())

    def test_run_does_not_apply_client_side_resource_limits(self) -> None:
        # The docker CLI client's own CPU/memory/process needs are
        # unrelated to the sandbox budget — the container's payload is
        # already bounded via --memory/--cpus/--pids-limit above.
        # Applying RLIMIT_NPROC etc. to the client itself is not just
        # redundant but can break the client on a host with a low ambient
        # per-uid process ceiling.
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        with mock.patch.object(docker_runner, "run_bounded", return_value=_bounded()) as run_bounded:
            with mock.patch.object(docker_runner, "_force_remove"):
                docker_runner.run(request, self.workspace)
        self.assertFalse(run_bounded.call_args.kwargs["apply_resource_limits"])

    def test_docker_binary_is_resolved_to_an_absolute_path_not_a_bare_command(self) -> None:
        # A host where docker only resolves via a PATH entry outside
        # docker_client_env()'s fixed list must still work: the resolved
        # absolute path, not the bare string "docker", must be argv[0]
        # for both the main run and the force-remove teardown.
        request = SandboxRequest(argv=("true",), source_dir=self.source, limits=SandboxLimits())
        with mock.patch("shutil.which", return_value="/opt/homebrew/bin/docker"):
            with mock.patch.object(docker_runner, "run_bounded", return_value=_bounded()) as run_bounded:
                with mock.patch("subprocess.run") as force_remove_run:
                    docker_runner.run(request, self.workspace)
        self.assertEqual(run_bounded.call_args.args[0][0], "/opt/homebrew/bin/docker")
        force_remove_run.assert_called_once()
        self.assertEqual(force_remove_run.call_args.args[0][0], "/opt/homebrew/bin/docker")
