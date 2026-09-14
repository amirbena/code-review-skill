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

    def test_no_isolation_primitive_never_falls_back_silently(self) -> None:
        """A None result is the fail-closed signal callers must respect."""
        with mock.patch.object(capability, "_PROBES", ()):
            self.assertIsNone(capability.detect_primitive())
            self.assertEqual(capability.available_primitives(), ())
