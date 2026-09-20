"""Tests for scripts/packaging/package_domain/version.py — release-version
resolution and SKILL.md version stamping shared by both packaging scripts (issue #496)."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import tests.unit.package_domain._shared  # noqa: F401 - sys.path wiring

from package_domain import main
from package_domain.version import (
    ReleaseVersionError,
    frontmatter_version,
    newest_release_version,
    resolve_release_version,
    stamp_frontmatter_version,
    stamp_skill_md_from_authority,
)

CHANGELOG = """\
# Changelog

## Unreleased

### Fixed

- Something pending (#1).

## v1.54.0 — 2026-09-20

### Fixed

- Shipped.

## v1.53.0 — 2026-09-18
"""

SKILL = "---\nname: x\nversion: 1.50.2\ndescription: d\n---\n\nBody.\n"


class NewestReleaseVersionTests(unittest.TestCase):
    def test_takes_the_newest_release_heading_and_ignores_unreleased(self) -> None:
        self.assertEqual(newest_release_version(CHANGELOG), "1.54.0")

    def test_no_release_heading_is_none(self) -> None:
        self.assertIsNone(newest_release_version("# Changelog\n\n## Unreleased\n\n- x\n"))

    def test_heading_must_be_a_strict_version(self) -> None:
        for text in ("## v1.2\n", "## v01.2.3\n", "## v1.2.3-rc1\n", "## 1.2.3\n", "### v1.2.3\n"):
            self.assertIsNone(newest_release_version(text), text)


class ResolveReleaseVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_resolves_from_the_file(self) -> None:
        path = self.dir / "CHANGELOG.md"
        path.write_text(CHANGELOG, encoding="utf-8")
        self.assertEqual(resolve_release_version(path), "1.54.0")

    def test_missing_file_fails_closed(self) -> None:
        with self.assertRaises(ReleaseVersionError):
            resolve_release_version(self.dir / "CHANGELOG.md")

    def test_file_without_a_release_heading_fails_closed(self) -> None:
        path = self.dir / "CHANGELOG.md"
        path.write_text("# Changelog\n\n## Unreleased\n", encoding="utf-8")
        with self.assertRaises(ReleaseVersionError):
            resolve_release_version(path)


class StampTests(unittest.TestCase):
    def test_reads_and_stamps_only_the_frontmatter_version(self) -> None:
        self.assertEqual(frontmatter_version(SKILL), "1.50.2")
        self.assertEqual(stamp_frontmatter_version(SKILL, "1.54.0"), SKILL.replace("1.50.2", "1.54.0"))

    def test_refuses_a_non_strict_version(self) -> None:
        for bad in ("v1.54.0", "1.54", "01.2.3", "1.54.0-rc1", ""):
            with self.assertRaises(ValueError, msg=bad):
                stamp_frontmatter_version(SKILL, bad)

    def test_refuses_a_skill_md_without_a_version_line(self) -> None:
        with self.assertRaises(ValueError):
            stamp_frontmatter_version("---\nname: x\n---\nBody\n", "1.54.0")


class StampFromAuthorityTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.skill = self.dir / "SKILL.md"
        self.changelog = self.dir / "CHANGELOG.md"
        self.skill.write_text(SKILL, encoding="utf-8")
        self.changelog.write_text(CHANGELOG, encoding="utf-8")

    def _run(self) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["stamp-release-version", str(self.skill), str(self.changelog)])
        return code, out.getvalue(), err.getvalue()

    def test_a_stale_committed_version_is_replaced_with_a_note(self) -> None:
        version, previous = stamp_skill_md_from_authority(self.skill, self.changelog)
        self.assertEqual((version, previous), ("1.54.0", "1.50.2"))
        self.assertEqual(frontmatter_version(self.skill.read_text(encoding="utf-8")), "1.54.0")

    def test_cli_reports_the_stale_value_and_exits_zero(self) -> None:
        code, out, _ = self._run()
        self.assertEqual(code, 0)
        self.assertIn("note: committed SKILL.md version 1.50.2 differs", out)
        self.assertIn("packaged with 1.54.0", out)

    def test_a_matching_version_is_left_untouched_and_not_noted(self) -> None:
        self.skill.write_text(SKILL.replace("1.50.2", "1.54.0"), encoding="utf-8")
        before = self.skill.read_bytes()
        code, out, _ = self._run()
        self.assertEqual(code, 0)
        self.assertNotIn("note:", out)
        self.assertEqual(self.skill.read_bytes(), before)

    def test_cli_fails_closed_without_a_release_authority(self) -> None:
        self.changelog.unlink()
        code, _, err = self._run()
        self.assertEqual(code, 1)
        self.assertIn("release authority", err)
        self.assertEqual(frontmatter_version(self.skill.read_text(encoding="utf-8")), "1.50.2")

    def test_cli_fails_closed_when_the_changelog_has_no_release_heading(self) -> None:
        self.changelog.write_text("# Changelog\n\n## Unreleased\n", encoding="utf-8")
        code, _, err = self._run()
        self.assertEqual(code, 1)
        self.assertIn("no '## vX.Y.Z' release heading", err)

    def test_cli_fails_when_the_skill_md_has_no_version_line(self) -> None:
        self.skill.write_text("---\nname: x\n---\nBody\n", encoding="utf-8")
        code, _, err = self._run()
        self.assertEqual(code, 1)
        self.assertIn("version", err)


if __name__ == "__main__":
    unittest.main()
