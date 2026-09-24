"""Release-version invariant for the Skill archives (issue #496): the real
`verify-skill-archives.sh --expect-version` gate fails closed on a mismatch,
and stamp → package → verify produces archives reporting the release version.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.integration.packaging._shared import TEMP_ROOT_INPUTS
from tests.support.paths import REPO_ROOT

SCRIPT = "scripts/release/verify-skill-archives.sh"
MANIFEST = json.loads((REPO_ROOT / "scripts/packaging/package-manifest.json").read_text(encoding="utf-8"))
ARCHIVES = {key: skill["archive"] for key, skill in MANIFEST["skills"].items()}
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
TOOLS_PRESENT = all(shutil.which(tool) for tool in ("bash", "unzip", "zip", "python3"))


def _copy(rel: str, dest_root: Path) -> None:
    src = REPO_ROOT / rel
    dest = dest_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    else:
        shutil.copy2(src, dest)


def _skill_md(name: str, version: str) -> str:
    return f"---\nname: {name}\nversion: {version}\ndescription: Example.\n---\n\nBody.\n"


@unittest.skipUnless(TOOLS_PRESENT, "needs bash, unzip, zip, and python3")
class VerifyScriptExpectVersionTests(unittest.TestCase):
    """Runs the real helper against a minimal tree holding hand-built archives."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for rel in (SCRIPT, "scripts/release/release_worthiness.py", "scripts/release/release_lib",
                    "scripts/packaging/package-manifest.json", "scripts/packaging/package_manifest.py",
                    "scripts/packaging/package_domain"):
            _copy(rel, self.root)

    def _build_archives(self, versions: dict[str, str]) -> None:
        dist = self.root / "dist"
        dist.mkdir(exist_ok=True)
        for key, archive in ARCHIVES.items():
            with zipfile.ZipFile(dist / archive, "w") as zf:
                zf.writestr("SKILL.md", _skill_md(MANIFEST["skills"][key]["name"], versions[key]))

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self.root / SCRIPT), *args], capture_output=True, text=True, cwd=self.root,
            env=ENV,
        )

    def test_matching_versions_pass(self) -> None:
        self._build_archives({"local": "1.54.0", "github": "1.54.0"})
        result = self._run("--expect-version", "1.54.0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_stale_archive_blocks_the_release(self) -> None:
        for stale in ("local", "github"):
            with self.subTest(stale=stale):
                self._build_archives({"local": "1.54.0", "github": "1.54.0", stale: "1.50.2"})
                result = self._run("--expect-version", "1.54.0")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(ARCHIVES[stale], result.stdout + result.stderr)
                self.assertNotIn("Verified", result.stdout)

    def test_without_expect_version_the_version_is_not_checked(self) -> None:
        self._build_archives({"local": "1.50.2", "github": "1.50.2"})
        self.assertEqual(self._run().returncode, 0)

    def test_expect_version_requires_a_value(self) -> None:
        self._build_archives({"local": "1.54.0", "github": "1.54.0"})
        self.assertEqual(self._run("--expect-version").returncode, 2)


@unittest.skipUnless(TOOLS_PRESENT, "needs bash, unzip, zip, and python3")
class StampPackageVerifyTests(unittest.TestCase):
    """The release sequence (roll → stamp → package → verify) on a copy of the real sources."""

    VERSION = "9.8.7"

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for rel in TEMP_ROOT_INPUTS:
            if rel != "CHANGELOG.md":  # each test writes its own rolled changelog
                _copy(rel, self.root)

    def _roll_changelog(self, version: str) -> None:
        (self.root / "CHANGELOG.md").write_text(
            f"# Changelog\n\n## Unreleased\n\n## v{version} — 2026-01-01\n\n### Fixed\n\n- x\n", encoding="utf-8"
        )

    def _sh(self, *cmd: str) -> subprocess.CompletedProcess:
        return subprocess.run(list(cmd), capture_output=True, text=True, cwd=self.root, env=ENV)

    def test_rolled_and_stamped_tree_packages_archives_reporting_the_release_version(self) -> None:
        self._roll_changelog(self.VERSION)
        stamp = self._sh("python3", "scripts/release/release_worthiness.py", "stamp-skill-version",
                         "--version", self.VERSION)
        self.assertEqual(stamp.returncode, 0, stamp.stdout + stamp.stderr)
        result = self._sh(SCRIPT, "--build", "--expect-version", self.VERSION)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("note:", result.stdout)

    def test_release_build_whose_changelog_was_not_rolled_to_the_planned_version_is_blocked(self) -> None:
        self._roll_changelog("9.8.6")
        result = self._sh(SCRIPT, "--build", "--expect-version", self.VERSION)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"expected release version '{self.VERSION}'", result.stdout)
        self.assertNotIn("Verified", result.stdout)


if __name__ == "__main__":
    unittest.main()
