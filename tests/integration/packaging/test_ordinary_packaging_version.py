"""Ordinary local/PR packaging (issue #496): with no release being published,
`package-skills.sh` derives each archive's SKILL.md version from the release
authority instead of copying a possibly stale committed literal, and fails
closed when the authority is missing. Also pins that the authority resolves
correctly at real release tags.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

import tests.unit.package_domain._shared  # noqa: F401 - sys.path wiring

from package_domain.version import frontmatter_version, newest_release_version
from tests.support.paths import REPO_ROOT

PACKAGE = "scripts/packaging/package-skills.sh"
MANIFEST = json.loads((REPO_ROOT / "scripts/packaging/package-manifest.json").read_text(encoding="utf-8"))
SKILLS = {key: (skill["name"], skill["archive"]) for key, skill in MANIFEST["skills"].items()}
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
TOOLS_PRESENT = all(shutil.which(tool) for tool in ("bash", "zip", "python3"))
NEWEST = newest_release_version((REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))


def _copy(rel: str, dest_root: Path) -> None:
    src, dest = REPO_ROOT / rel, dest_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        shutil.copy2(src, dest)


@unittest.skipUnless(TOOLS_PRESENT, "needs bash, zip, and python3")
class OrdinaryPackagingVersionTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for rel in ("skills", "shared", "scripts", "capabilities", "docs", "LICENSE", "CHANGELOG.md"):
            _copy(rel, self.root)

    def _set_committed_version(self, version: str) -> None:
        for name, _archive in SKILLS.values():
            path = self.root / "skills" / name / "SKILL.md"
            path.write_text(
                re.sub(r"(?m)^version: \S+$", f"version: {version}", path.read_text(encoding="utf-8"), count=1),
                encoding="utf-8",
            )

    def _package(self) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / PACKAGE), "all"], capture_output=True, text=True, cwd=self.root, env=ENV
        )

    def _archive_version(self, archive: str) -> str | None:
        with zipfile.ZipFile(self.root / "dist" / archive) as zf:
            return frontmatter_version(zf.read("SKILL.md").decode("utf-8"))

    def test_a_stale_committed_version_never_reaches_the_archives(self) -> None:
        self._set_committed_version("0.0.1")
        result = self._package()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for _name, archive in SKILLS.values():
            self.assertEqual(self._archive_version(archive), NEWEST)
        self.assertIn("note: committed SKILL.md version 0.0.1 differs", result.stdout)

    def test_a_current_committed_version_packages_without_a_note(self) -> None:
        self._set_committed_version(NEWEST)
        result = self._package()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("note:", result.stdout)
        for _name, archive in SKILLS.values():
            self.assertEqual(self._archive_version(archive), NEWEST)

    def test_the_version_follows_the_authority_not_the_committed_value(self) -> None:
        (self.root / "CHANGELOG.md").write_text(
            "# Changelog\n\n## Unreleased\n\n## v7.8.9 — 2026-01-01\n\n- x\n", encoding="utf-8"
        )
        result = self._package()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for _name, archive in SKILLS.values():
            self.assertEqual(self._archive_version(archive), "7.8.9")

    def test_a_missing_authority_fails_closed_with_no_archive(self) -> None:
        (self.root / "CHANGELOG.md").unlink()
        result = self._package()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("release authority", result.stderr)
        self.assertFalse(list((self.root / "dist").glob("*.zip")) if (self.root / "dist").exists() else [])

    def test_an_authority_without_a_release_heading_fails_closed(self) -> None:
        (self.root / "CHANGELOG.md").write_text("# Changelog\n\n## Unreleased\n\n- x\n", encoding="utf-8")
        result = self._package()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no '## vX.Y.Z' release heading", result.stderr)


class ReleaseAuthorityAtTagsTests(unittest.TestCase):
    """A tree checked out at a release tag resolves to exactly that tag's version."""

    def test_recent_release_tags_resolve_to_their_own_version(self) -> None:
        try:
            tags = subprocess.run(
                ["git", "tag", "--list", "v[0-9]*", "--sort=-v:refname"],
                capture_output=True, text=True, cwd=REPO_ROOT, check=True,
            ).stdout.split()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git is unavailable")
        tags = [t for t in tags if re.fullmatch(r"v\d+\.\d+\.\d+", t)][:3]
        if not tags:
            self.skipTest("no release tags in this checkout")
        for tag in tags:
            with self.subTest(tag=tag):
                changelog = subprocess.run(
                    ["git", "show", f"{tag}:CHANGELOG.md"], capture_output=True, text=True, cwd=REPO_ROOT, check=True
                ).stdout
                self.assertEqual(newest_release_version(changelog), tag[1:])


if __name__ == "__main__":
    unittest.main()
