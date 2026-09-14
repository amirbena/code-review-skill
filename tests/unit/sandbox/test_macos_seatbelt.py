"""Unit tests for scripts/sandbox/macos_seatbelt.py profile generation (Issue #302).

Tests the generated SBPL text directly — no sandbox-exec invocation, so
these run on any host. Seatbelt resolves a conflicting rule by *last
declared rule wins*, not by path specificity (verified empirically; see
the module docstring) — these tests pin that ordering so a future edit
cannot silently invert it.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from scripts.sandbox import macos_seatbelt


def _rule_index(lines: list[str], substring: str) -> int:
    for i, line in enumerate(lines):
        if substring in line:
            return i
    raise AssertionError(f"no rule contains {substring!r} in:\n" + "\n".join(lines))


class BuildProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace_root = Path("/private/tmp/crs-sandbox-test-workspace")

    def test_network_is_denied(self) -> None:
        profile = macos_seatbelt.build_profile(self.workspace_root, ())
        self.assertIn("(deny network*)", profile)

    def test_workspace_write_is_allowed(self) -> None:
        profile = macos_seatbelt.build_profile(self.workspace_root, ())
        self.assertIn(f'(allow file-write* (subpath "{self.workspace_root}"))', profile)

    def test_workspace_write_allow_is_declared_after_the_broad_write_deny(self) -> None:
        # SBPL: last declared rule wins. The broad "/" write-deny must come
        # first so the narrower workspace allow (declared after) is the one
        # that actually applies — reversing this order silently breaks
        # writes into the ephemeral workspace.
        lines = macos_seatbelt.build_profile(self.workspace_root, ()).splitlines()
        deny_all_writes = _rule_index(lines, '(deny file-write* (subpath "/"))')
        allow_workspace_write = _rule_index(
            lines, f'(allow file-write* (subpath "{self.workspace_root}"))'
        )
        self.assertLess(deny_all_writes, allow_workspace_write)

    def test_denied_read_roots_are_declared_before_system_read_allows(self) -> None:
        lines = macos_seatbelt.build_profile(self.workspace_root, ()).splitlines()
        deny_users = _rule_index(lines, '(deny file-read* (subpath "/Users"))')
        allow_usr = _rule_index(lines, '(allow file-read* (subpath "/usr"))')
        self.assertLess(deny_users, allow_usr)

    def test_workspace_read_allow_is_declared_after_the_denied_scratch_roots(self) -> None:
        # The ephemeral workspace commonly lives inside a denied scratch
        # root (e.g. /private/var/folders); its own read-allow must be the
        # *last* matching rule so it wins despite that.
        lines = macos_seatbelt.build_profile(self.workspace_root, ()).splitlines()
        deny_scratch = _rule_index(lines, '(deny file-read* (subpath "/private/var/folders"))')
        allow_workspace_read = lines.index(
            f'(allow file-read* (subpath "{self.workspace_root}"))'
        )
        self.assertLess(deny_scratch, allow_workspace_read)
        # And it must be the last rule touching file-read* altogether, so
        # no later rule can shadow it back out.
        self.assertEqual(
            allow_workspace_read,
            max(i for i, line in enumerate(lines) if "file-read*" in line and "allow" in line),
        )

    def test_read_only_input_is_allowed_and_declared_last(self) -> None:
        extra = Path("/private/tmp/crs-extra-input")
        lines = macos_seatbelt.build_profile(self.workspace_root, (extra,)).splitlines()
        allow_extra = _rule_index(lines, f'(allow file-read* (subpath "{extra}"))')
        self.assertEqual(allow_extra, len(lines) - 1)

    def test_always_denied_roots_that_exist_on_this_host_are_all_present(self) -> None:
        profile = macos_seatbelt.build_profile(self.workspace_root, ())
        for root in macos_seatbelt._ALWAYS_DENIED_READ_ROOTS:
            if Path(root).is_dir():
                with self.subTest(root=root):
                    self.assertIn(f'(deny file-read* (subpath "{root}"))', profile)

    def test_path_with_double_quote_is_escaped(self) -> None:
        tricky = Path('/private/tmp/has"quote')
        profile = macos_seatbelt.build_profile(tricky, ())
        self.assertIn('has\\"quote', profile)
        self.assertNotIn('has"quote', profile)
