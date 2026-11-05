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
    frontmatter_version,
    stamp_frontmatter_version,
    stamp_skill_md,
)

SKILL = "---\nname: x\nversion: 1.50.2\ndescription: d\n---\n\nBody.\n"


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


class InsertMissingTests(unittest.TestCase):
    def test_a_missing_version_line_is_only_inserted_when_asked(self) -> None:
        source = "---\nname: x\ndescription: y\n---\nBody\n"
        with self.assertRaises(ValueError):
            stamp_frontmatter_version(source, "3.0.0")
        stamped = stamp_frontmatter_version(source, "3.0.0", insert_missing=True)
        self.assertEqual(stamp_frontmatter_version(stamped, "3.1.0", insert_missing=True).count("version:"), 1)


class CrlfTests(unittest.TestCase):
    """Windows checkouts carry CRLF; reading and stamping must tolerate it and keep it."""

    CRLF_SKILL = SKILL.replace("\n", "\r\n")

    def test_reads_the_version_from_a_crlf_file(self) -> None:
        self.assertEqual(frontmatter_version(self.CRLF_SKILL), "1.50.2")

    def test_stamping_changes_only_the_version_line_and_keeps_crlf(self) -> None:
        stamped = stamp_frontmatter_version(self.CRLF_SKILL, "1.54.0")
        self.assertEqual(stamped, self.CRLF_SKILL.replace("1.50.2", "1.54.0"))
        self.assertNotIn("\n", stamped.replace("\r\n", ""))

    def test_a_crlf_file_without_a_version_line_is_still_refused(self) -> None:
        with self.assertRaises(ValueError):
            stamp_frontmatter_version("---\r\nname: x\r\n---\r\nBody\r\n", "1.54.0")

    def test_the_cli_stamps_a_crlf_skill_md_byte_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp) / "SKILL.md"
            skill.write_bytes(self.CRLF_SKILL.encode("utf-8"))
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["stamp-release-version", str(skill), "--version", "1.54.0"])
            self.assertEqual(code, 0)
            self.assertEqual(skill.read_bytes(), self.CRLF_SKILL.replace("1.50.2", "1.54.0").encode("utf-8"))


class StampPackagedCopyTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.skill = Path(tmp.name) / "SKILL.md"
        self.skill.write_text(SKILL, encoding="utf-8")

    def _run(self, *extra: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["stamp-release-version", str(self.skill), *extra])
        return code, out.getvalue()

    def test_the_release_tag_version_replaces_any_committed_value(self) -> None:
        # Any later tag stamps every packaged Skill with that tag's version, regardless of the source value.
        for tag_version in ("3.0.0", "3.1.0"):
            self.skill.write_text(SKILL, encoding="utf-8")
            self.assertEqual(stamp_skill_md(self.skill, tag_version), (tag_version, "1.50.2"))
            self.assertEqual(frontmatter_version(self.skill.read_text(encoding="utf-8")), tag_version)

    def test_cli_notes_a_differing_committed_value_and_exits_zero(self) -> None:
        code, out = self._run("--version", "1.54.0")
        self.assertEqual(code, 0)
        self.assertIn("note: committed SKILL.md version 1.50.2 differs from the release tag 1.54.0", out)

    def test_a_matching_version_is_left_untouched_and_not_noted(self) -> None:
        before = self.skill.read_bytes()
        code, out = self._run("--version", "1.50.2")
        self.assertEqual(code, 0)
        self.assertNotIn("note:", out)
        self.assertEqual(self.skill.read_bytes(), before)

    def test_without_a_release_version_the_file_is_left_as_committed(self) -> None:
        before = self.skill.read_bytes()
        self.assertEqual(self._run()[0], 0)
        self.assertEqual(self.skill.read_bytes(), before)

    def test_a_never_released_skill_stays_unversioned_without_a_release_version(self) -> None:
        # ADR §11: no v2.x label borrowed from CHANGELOG, Git or anywhere else.
        source = "---\nname: x\ndescription: y\n---\nBody\n"
        self.skill.write_text(source, encoding="utf-8")
        self.assertEqual(stamp_skill_md(self.skill, None), (None, None))
        self.assertEqual(self.skill.read_text(encoding="utf-8"), source)

    def test_the_release_tag_version_is_inserted_where_the_line_is_missing(self) -> None:
        self.skill.write_text("---\nname: x\ndescription: y\n---\nBody\n", encoding="utf-8")
        self.assertEqual(stamp_skill_md(self.skill, "3.0.0"), ("3.0.0", None))
        self.assertEqual(self.skill.read_text(encoding="utf-8"), "---\nname: x\nversion: 3.0.0\ndescription: y\n---\nBody\n")

    def test_a_non_strict_release_version_is_refused(self) -> None:
        code, _ = self._run("--version", "v3.0.0")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
