"""Tests for scripts/release_worthiness.py CHANGELOG.md Unreleased-section coverage detection."""

from __future__ import annotations

import unittest
from tests.support.paths import REPO_ROOT
from tests.unit.release._shared import COVERED_CHANGELOG, PLACEHOLDER_CHANGELOG, rw

class ChangelogCoverageTests(unittest.TestCase):
    def test_placeholder_only_is_not_covered(self) -> None:
        self.assertFalse(rw.unreleased_has_coverage(PLACEHOLDER_CHANGELOG))

    def test_bullet_entry_is_covered(self) -> None:
        self.assertTrue(rw.unreleased_has_coverage(COVERED_CHANGELOG))

    def test_missing_unreleased_heading_is_not_covered(self) -> None:
        self.assertFalse(rw.unreleased_has_coverage("# Changelog\n\n## v1.0.0 — 2026-01-01\n\n- x\n"))

    def test_star_bullets_count(self) -> None:
        text = "# Changelog\n\n## Unreleased\n\n* Did a thing.\n\n## v1.0.0 — 2026-01-01\n"
        self.assertTrue(rw.unreleased_has_coverage(text))

    def test_real_repository_changelog_is_parseable(self) -> None:
        text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        # Should not raise and returns a bool for the current file.
        self.assertIn(rw.unreleased_has_coverage(text), (True, False))


if __name__ == "__main__":
    unittest.main()
