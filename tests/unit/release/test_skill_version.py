"""Tests for the Skill frontmatter version stamp and archive verification (issue #496)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.unit.release._shared import rw  # noqa: F401  (puts scripts/release on sys.path)

from release_lib import skill_version as sv

SKILL_TEMPLATE = "---\nname: {name}\nversion: {version}\ndescription: Example.\n---\n\nBody.\nversion: 0.0.1\n"

MANIFEST = {
    "schema_version": 1,
    "skills": {
        "local": {"name": "local-code-review", "archive": "local-code-review-skill.zip"},
        "github": {"name": "github-pr-review", "archive": "github-pr-review-skill.zip"},
    },
}


def _write_repo(root: Path, version: str = "1.50.2") -> None:
    manifest = root / sv.PACKAGE_MANIFEST
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps(MANIFEST), encoding="utf-8")
    for skill in MANIFEST["skills"].values():
        path = root / "skills" / skill["name"] / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text(SKILL_TEMPLATE.format(name=skill["name"], version=version), encoding="utf-8")


def _write_archive(dist: Path, archive: str, skill_md: str | None) -> None:
    dist.mkdir(exist_ok=True)
    with zipfile.ZipFile(dist / archive, "w") as zf:
        zf.writestr("LICENSE", "license")
        if skill_md is not None:
            zf.writestr("SKILL.md", skill_md)


def _run(root: Path, *argv: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = rw.main(["--repo-root", str(root), *argv])
    return code, out.getvalue()


class FrontmatterVersionTests(unittest.TestCase):
    def test_reads_the_frontmatter_version_only(self) -> None:
        self.assertEqual(sv.frontmatter_version(SKILL_TEMPLATE.format(name="x", version="1.2.3")), "1.2.3")

    def test_no_version_or_no_frontmatter_is_none(self) -> None:
        self.assertIsNone(sv.frontmatter_version("---\nname: x\n---\nversion: 1.2.3\n"))
        self.assertIsNone(sv.frontmatter_version("version: 1.2.3\n"))

    def test_stamp_replaces_only_the_frontmatter_line(self) -> None:
        text = SKILL_TEMPLATE.format(name="x", version="1.50.2")
        stamped = sv.stamp_frontmatter_version(text, "1.54.0")
        self.assertEqual(stamped, text.replace("version: 1.50.2", "version: 1.54.0"))
        self.assertIn("\nversion: 0.0.1\n", stamped)

    def test_stamp_is_idempotent(self) -> None:
        text = SKILL_TEMPLATE.format(name="x", version="1.54.0")
        self.assertEqual(sv.stamp_frontmatter_version(text, "1.54.0"), text)

    def test_stamp_refuses_a_skill_md_with_no_version_line(self) -> None:
        with self.assertRaises(ValueError):
            sv.stamp_frontmatter_version("---\nname: x\n---\nBody\n", "1.54.0")

    def test_stamp_refuses_a_non_semver_version(self) -> None:
        text = SKILL_TEMPLATE.format(name="x", version="1.50.2")
        for bad in ("v1.54.0", "1.54", "1.54.0-rc1", ""):
            with self.assertRaises(ValueError, msg=bad):
                sv.stamp_frontmatter_version(text, bad)


class StampSkillVersionsTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        _write_repo(self.root)

    def test_stamps_both_skills(self) -> None:
        changed = sv.stamp_skill_versions(self.root, "1.54.0")
        self.assertEqual(len(changed), 2)
        for skill in MANIFEST["skills"].values():
            text = (self.root / "skills" / skill["name"] / "SKILL.md").read_text(encoding="utf-8")
            self.assertEqual(sv.frontmatter_version(text), "1.54.0")

    def test_second_stamp_changes_nothing(self) -> None:
        sv.stamp_skill_versions(self.root, "1.54.0")
        self.assertEqual(sv.stamp_skill_versions(self.root, "1.54.0"), [])

    def test_cli_stamps_and_rejects_a_bad_version(self) -> None:
        code, out = _run(self.root, "stamp-skill-version", "--version", "1.54.0")
        self.assertEqual(code, 0)
        self.assertIn("Stamped version 1.54.0", out)
        code, out = _run(self.root, "stamp-skill-version", "--version", "v1.55.0")
        self.assertEqual(code, 1)
        self.assertIn("::error::", out)

    def test_cli_fails_when_a_skill_has_no_version_line(self) -> None:
        (self.root / "skills" / "local-code-review" / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
        code, out = _run(self.root, "stamp-skill-version", "--version", "1.54.0")
        self.assertEqual(code, 1)
        self.assertIn("::error::", out)


class VerifyArchiveVersionsTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        _write_repo(self.root)
        self.dist = self.root / "dist"

    def _archives(self, local: str | None, github: str | None) -> None:
        for skill, version in (("local", local), ("github", github)):
            meta = MANIFEST["skills"][skill]
            body = None if version is None else SKILL_TEMPLATE.format(name=meta["name"], version=version)
            _write_archive(self.dist, meta["archive"], body)

    def test_matching_versions_pass(self) -> None:
        self._archives("1.54.0", "1.54.0")
        self.assertEqual(sv.verify_archive_versions(self.root, self.dist, "1.54.0"), [])
        code, out = _run(self.root, "verify-archive-versions", "--version", "1.54.0")
        self.assertEqual(code, 0)
        self.assertIn("1.54.0", out)

    def test_stale_local_archive_fails_closed(self) -> None:
        self._archives("1.50.2", "1.54.0")
        problems = sv.verify_archive_versions(self.root, self.dist, "1.54.0")
        self.assertEqual(len(problems), 1)
        self.assertIn("local-code-review-skill.zip", problems[0])
        self.assertIn("'1.50.2'", problems[0])
        code, out = _run(self.root, "verify-archive-versions", "--version", "1.54.0")
        self.assertEqual(code, 1)
        self.assertIn("::error::local-code-review-skill.zip", out)

    def test_stale_github_archive_fails_closed(self) -> None:
        self._archives("1.54.0", "1.50.2")
        code, out = _run(self.root, "verify-archive-versions", "--version", "1.54.0")
        self.assertEqual(code, 1)
        self.assertIn("::error::github-pr-review-skill.zip", out)

    def test_both_stale_reports_both(self) -> None:
        self._archives("1.50.2", "1.50.2")
        self.assertEqual(len(sv.verify_archive_versions(self.root, self.dist, "1.54.0")), 2)

    def test_archive_without_a_version_fails_closed(self) -> None:
        self._archives("1.54.0", None)
        problems = sv.verify_archive_versions(self.root, self.dist, "1.54.0")
        self.assertEqual(len(problems), 1)
        self.assertIn("None", problems[0])

    def test_missing_archive_fails_closed(self) -> None:
        self._archives("1.54.0", "1.54.0")
        (self.dist / "github-pr-review-skill.zip").unlink()
        code, out = _run(self.root, "verify-archive-versions", "--version", "1.54.0")
        self.assertEqual(code, 1)
        self.assertIn("missing", out)

    def test_corrupt_archive_fails_closed(self) -> None:
        self._archives("1.54.0", "1.54.0")
        (self.dist / "local-code-review-skill.zip").write_bytes(b"not a zip")
        code, out = _run(self.root, "verify-archive-versions", "--version", "1.54.0")
        self.assertEqual(code, 1)
        self.assertIn("::error::", out)

    def test_invalid_expected_version_is_refused(self) -> None:
        self._archives("1.54.0", "1.54.0")
        code, _ = _run(self.root, "verify-archive-versions", "--version", "v1.54.0")
        self.assertEqual(code, 1)

    def test_verification_reads_the_archive_not_the_source_tree(self) -> None:
        sv.stamp_skill_versions(self.root, "1.54.0")
        self._archives("1.50.2", "1.50.2")
        self.assertEqual(len(sv.verify_archive_versions(self.root, self.dist, "1.54.0")), 2)


if __name__ == "__main__":
    unittest.main()
