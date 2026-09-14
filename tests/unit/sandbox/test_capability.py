"""Unit tests for scripts/sandbox/capability.py (Issue #302)."""

from __future__ import annotations

import unittest
from unittest import mock

from scripts.sandbox import capability


class DetectPrimitiveTests(unittest.TestCase):
    def test_returns_none_when_nothing_is_available(self) -> None:
        with mock.patch.object(capability, "_PROBES", ()):
            self.assertIsNone(capability.detect_primitive())

    def test_prefers_docker_over_native_primitives(self) -> None:
        probes = (
            (capability.Primitive.DOCKER, lambda: True),
            (capability.Primitive.MACOS_SEATBELT, lambda: True),
        )
        with mock.patch.object(capability, "_PROBES", probes):
            self.assertEqual(capability.detect_primitive(), capability.Primitive.DOCKER)

    def test_falls_through_to_next_probe_when_first_is_unavailable(self) -> None:
        probes = (
            (capability.Primitive.DOCKER, lambda: False),
            (capability.Primitive.MACOS_SEATBELT, lambda: True),
        )
        with mock.patch.object(capability, "_PROBES", probes):
            self.assertEqual(capability.detect_primitive(), capability.Primitive.MACOS_SEATBELT)

    def test_available_primitives_lists_every_present_probe(self) -> None:
        probes = (
            (capability.Primitive.DOCKER, lambda: True),
            (capability.Primitive.MACOS_SEATBELT, lambda: False),
            (capability.Primitive.LINUX_BWRAP, lambda: True),
        )
        with mock.patch.object(capability, "_PROBES", probes):
            self.assertEqual(
                capability.available_primitives(),
                (capability.Primitive.DOCKER, capability.Primitive.LINUX_BWRAP),
            )


class ProbeFunctionTests(unittest.TestCase):
    def test_docker_unavailable_when_binary_missing(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            self.assertFalse(capability._docker_available())

    def test_docker_unavailable_when_daemon_unreachable(self) -> None:
        with mock.patch("shutil.which", return_value="/usr/local/bin/docker"):
            with mock.patch("subprocess.run", side_effect=OSError("no daemon")):
                self.assertFalse(capability._docker_available())

    def test_docker_probe_invokes_the_resolved_absolute_path_not_a_bare_command(self) -> None:
        # A host where docker only resolves via a PATH entry outside
        # docker_client_env()'s fixed list (Homebrew on Apple Silicon, a
        # Linux snap, ...) must still be detected: shutil.which() finds
        # it via the real ambient PATH, and that resolved path — not the
        # bare string "docker" — must be what actually gets executed.
        with mock.patch("shutil.which", return_value="/opt/homebrew/bin/docker"):
            with mock.patch("subprocess.run") as run:
                run.return_value = mock.Mock(returncode=0)
                self.assertTrue(capability._docker_available())
        self.assertEqual(run.call_args.args[0][0], "/opt/homebrew/bin/docker")

    def test_docker_probe_uses_the_same_env_as_docker_client_env(self) -> None:
        # Detection and actual execution (docker_runner.run) must agree on
        # environment, or a host can pass detection and then fail to run.
        with mock.patch("shutil.which", return_value="/usr/local/bin/docker"):
            with mock.patch("subprocess.run") as run:
                run.return_value = mock.Mock(returncode=0)
                capability._docker_available()
        self.assertEqual(run.call_args.kwargs["env"], capability.docker_client_env())

    def test_no_isolation_primitive_never_falls_back_silently(self) -> None:
        """A None result is the fail-closed signal callers must respect."""
        with mock.patch.object(capability, "_PROBES", ()):
            self.assertIsNone(capability.detect_primitive())
            self.assertEqual(capability.available_primitives(), ())


class ResolveDockerBinTests(unittest.TestCase):
    def test_returns_the_real_ambient_path_resolution(self) -> None:
        with mock.patch("shutil.which", return_value="/opt/homebrew/bin/docker"):
            self.assertEqual(capability.resolve_docker_bin(), "/opt/homebrew/bin/docker")

    def test_returns_none_when_docker_is_not_on_the_ambient_path(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            self.assertIsNone(capability.resolve_docker_bin())

    def test_is_the_single_source_docker_runner_and_docker_available_both_use(self) -> None:
        # docker_runner.py imports this exact function rather than
        # resolving its own path — the consolidation this test locks in.
        from scripts.sandbox import docker_runner

        self.assertIs(docker_runner.resolve_docker_bin, capability.resolve_docker_bin)


class DockerClientEnvTests(unittest.TestCase):
    def test_docker_host_is_passed_through_when_set(self) -> None:
        with mock.patch.dict("os.environ", {"DOCKER_HOST": "ssh://example"}, clear=False):
            self.assertEqual(capability.docker_client_env()["DOCKER_HOST"], "ssh://example")

    def test_docker_config_is_passed_through_when_set(self) -> None:
        with mock.patch.dict("os.environ", {"DOCKER_CONFIG": "/custom/docker"}, clear=False):
            self.assertEqual(capability.docker_client_env()["DOCKER_CONFIG"], "/custom/docker")

    def test_unset_passthrough_vars_are_absent_not_empty(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            env = capability.docker_client_env()
        for name in capability._DOCKER_ENV_PASSTHROUGH:
            self.assertNotIn(name, env)

    def test_always_carries_a_minimal_path(self) -> None:
        with mock.patch.dict("os.environ", {}, clear=True):
            env = capability.docker_client_env()
        self.assertIn("PATH", env)

    def test_no_other_ambient_variables_leak_through(self) -> None:
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "leak-me"}, clear=False):
            env = capability.docker_client_env()
        self.assertNotIn("GITHUB_TOKEN", env)
