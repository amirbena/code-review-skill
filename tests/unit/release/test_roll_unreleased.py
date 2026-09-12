"""Tests for scripts/release_worthiness.py Unreleased-section roll and the changelog-section extraction command."""

from __future__ import annotations

import unittest
import contextlib
import io
import tempfile
from pathlib import Path

from tests.unit.release._shared import (
    COVERED_CHANGELOG,
    PLACEHOLDER_CHANGELOG,
    VERSIONED_CHANGELOG,
    rw,
)

class RollUnreleasedTests(unittest.TestCase):
    def test_rolls_entries_and_restores_placeholder(self) -> None:
        out = rw.roll_unreleased(COVERED_CHANGELOG, "1.0.3", "2026-09-01")
        self.assertIn("## v1.0.3 — 2026-09-01", out)
        self.assertIn("- Add release-worthiness automation (#104).", out)
        # Fresh placeholder is back above the new version section.
        head = out.split("## v1.0.3", 1)[0]
        self.assertIn("## Unreleased", head)

    def test_placeholder_after_roll_has_no_entries(self) -> None:
        out = rw.roll_unreleased(COVERED_CHANGELOG, "1.0.3", "2026-09-01")
        self.assertFalse(rw.unreleased_has_coverage(out))

    def test_refuses_when_no_entries(self) -> None:
        with self.assertRaises(ValueError):
            rw.roll_unreleased(PLACEHOLDER_CHANGELOG, "1.0.3", "2026-09-01")

    def test_refuses_bad_version(self) -> None:
        with self.assertRaises(ValueError):
            rw.roll_unreleased(COVERED_CHANGELOG, "v1.0.3", "2026-09-01")
        with self.assertRaises(ValueError):
            rw.roll_unreleased(COVERED_CHANGELOG, "1.0", "2026-09-01")

    def test_preserves_prior_release_section(self) -> None:
        out = rw.roll_unreleased(COVERED_CHANGELOG, "1.0.3", "2026-09-01")
        self.assertIn("## v1.0.2 — 2026-08-29", out)


class ChangelogSectionCommandTests(unittest.TestCase):
    def test_prints_version_section(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        cl = Path(tmp.name) / "CHANGELOG.md"
        cl.write_text(VERSIONED_CHANGELOG, encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = rw.main(["--changelog", str(cl), "changelog-section", "--version", "1.0.3"])
        self.assertEqual(rc, 0)
        self.assertIn("Release-worthiness automation (#104).", buf.getvalue())
        self.assertNotIn("Something shipped earlier.", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
