"""Tests for repairing stale SKILL.md versions in published archives (issue #497)."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tests.unit.release._shared import rw  # noqa: F401  (puts scripts/release on sys.path)

import repair_archive_versions as cli
from release_lib import archive_repair as ar

SKILL = "---\nname: {name}\nversion: {version}\ndescription: Example.\n---\n\nBody.\n"
ARCHIVES = {"local-code-review": "local-code-review-skill.zip", "github-pr-review": "github-pr-review-skill.zip"}
FAKE_PACKAGER = """#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p dist
for skill in local-code-review github-pr-review; do
  python3 -c "import sys, zipfile; z = zipfile.ZipFile('dist/' + sys.argv[1] + '-skill.zip', 'w'); z.write('skills/' + sys.argv[1] + '/SKILL.md', 'SKILL.md'); z.writestr('LICENSE', 'x')" "$skill"
done
"""


def _zip(path: Path, skill_md: str, extra: dict[str, str] | None = None) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("SKILL.md", skill_md)
        for name, body in (extra or {}).items():
            zf.writestr(name, body)
    return path


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, check=True, capture_output=True)


def _tagged_repo(root: Path, tag: str, changelog_version: str) -> None:
    (root / "scripts" / "packaging").mkdir(parents=True)
    (root / "scripts" / "packaging" / "package-manifest.json").write_text(
        json.dumps({"schema_version": 1, "skills": {k: {"name": n, "archive": a} for k, (n, a) in
                    zip(("local", "github"), ARCHIVES.items())}}), encoding="utf-8")
    (root / "scripts" / "packaging" / "package-skills.sh").write_text(FAKE_PACKAGER, encoding="utf-8")
    for name in ARCHIVES:
        (root / "skills" / name).mkdir(parents=True)
        (root / "skills" / name / "SKILL.md").write_text(SKILL.format(name=name, version="1.50.2"), encoding="utf-8")
    (root / "CHANGELOG.md").write_text(f"# Changelog\n\n## v{changelog_version} — 2026-01-01\n\n- x\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "release")
    _git(root, "tag", tag)


class CompareArchivesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def test_only_the_version_line_may_differ(self) -> None:
        old = _zip(self.tmp / "old.zip", SKILL.format(name="x", version="1.50.2"), {"a.md": "a"})
        new = _zip(self.tmp / "new.zip", SKILL.format(name="x", version="1.54.0"), {"a.md": "a"})
        self.assertEqual(ar.compare_archives(old, new, "1.54.0"), (True, []))

    def test_other_skill_md_or_file_differences_are_reported(self) -> None:
        old = _zip(self.tmp / "old.zip", SKILL.format(name="x", version="1.50.2"), {"a.md": "a"})
        new = _zip(self.tmp / "new.zip", SKILL.format(name="y", version="1.54.0"), {"a.md": "b"})
        self.assertEqual(ar.compare_archives(old, new, "1.54.0"), (True, ["SKILL.md", "a.md"]))

    def test_inventory_mismatch_is_reported(self) -> None:
        old = _zip(self.tmp / "old.zip", SKILL.format(name="x", version="1.50.2"), {"a.md": "a"})
        new = _zip(self.tmp / "new.zip", SKILL.format(name="x", version="1.54.0"), {"b.md": "a"})
        self.assertEqual(ar.compare_archives(old, new, "1.54.0"), (False, ["a.md", "b.md"]))

    def test_tag_must_be_a_release_tag(self) -> None:
        self.assertEqual(ar.release_version_from_tag("v1.54.0"), "1.54.0")
        for bad in ("1.54.0", "v1.54", "v01.2.3", "main"):
            with self.assertRaises((ar.RepairError, ValueError)):
                ar.release_version_from_tag(bad)


class ReconstructTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.repo, self.work = self.tmp / "repo", self.tmp / "work"

    def test_rebuilds_from_the_tag_with_only_the_version_stamped(self) -> None:
        _tagged_repo(self.repo, "v1.54.0", "1.54.0")
        record = ar.reconstruct(self.repo, "v1.54.0", self.work)
        self.assertEqual(record["expected_version"], "1.54.0")
        for archive in ARCHIVES.values():
            self.assertEqual(ar.archive_skill_version(self.work / "v1.54.0" / "rebuilt" / archive), "1.54.0")
        self.assertIn("version: 1.50.2", (self.repo / "skills" / "local-code-review" / "SKILL.md").read_text())
        self.assertEqual(subprocess.run(["git", "status", "--short"], cwd=self.repo, capture_output=True, text=True).stdout, "")

    def test_changelog_that_disagrees_with_the_tag_fails_closed(self) -> None:
        _tagged_repo(self.repo, "v1.54.0", "1.53.0")
        with self.assertRaisesRegex(ar.RepairError, "newest release heading"):
            ar.reconstruct(self.repo, "v1.54.0", self.work)
        self.assertFalse((self.work / "v1.54.0" / "rebuilt").exists())

    def test_missing_tag_fails_closed(self) -> None:
        _tagged_repo(self.repo, "v1.54.0", "1.54.0")
        with self.assertRaises(ar.RepairError):
            ar.reconstruct(self.repo, "v9.9.9", self.work)


class VerifyAndReplaceTests(unittest.TestCase):
    TAG = "v1.54.0"

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.repo, self.work = self.tmp / "repo", self.tmp / "work"
        self.repo.mkdir()
        _tagged_repo(self.repo, self.TAG, "1.54.0")
        ar.reconstruct(self.repo, self.TAG, self.work)
        self.published: dict[str, bytes] = {}
        for archive in ARCHIVES.values():
            stale = ar.stamp_frontmatter_version(
                zipfile.ZipFile(self.work / self.TAG / "rebuilt" / archive).read("SKILL.md").decode(), "1.50.2")
            self.published[archive] = _zip(self.tmp / f"pub-{archive}", stale, {"LICENSE": "x"}).read_bytes()
        self.uploads: list[str] = []

    def _download(self, _repo: Path, _tag: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        for archive, data in self.published.items():
            (dest / archive).write_bytes(data)

    def _digests(self, _repo: Path, _tag: str) -> dict[str, str]:
        return {a: ar.hashlib.sha256(d).hexdigest() for a, d in self.published.items()}

    def _upload(self, _repo: Path, _tag: str, archive: Path) -> None:
        self.uploads.append(archive.name)
        self.published[archive.name] = archive.read_bytes()

    def _patched(self):
        return mock.patch.multiple(ar, download_published=self._download, published_digests=self._digests)

    def test_verify_passes_when_only_the_version_differs(self) -> None:
        with self._patched():
            results = ar.verify(self.repo, self.TAG, self.work)
        self.assertTrue(ar.phase_ok(results))
        entry = results["local-code-review-skill.zip"]
        self.assertEqual((entry["published_version"], entry["rebuilt_version"]), ("1.50.2", "1.54.0"))
        self.assertEqual(self.uploads, [])

    def test_a_failing_archive_blocks_only_its_own_replacement(self) -> None:
        self.published["github-pr-review-skill.zip"] = _zip(
            self.tmp / "other.zip", SKILL.format(name="github-pr-review", version="1.50.2"), {"LICENSE": "different"}
        ).read_bytes()
        with self._patched():
            results = ar.verify(self.repo, self.TAG, self.work)
            self.assertFalse(ar.phase_ok(results))
            self.assertTrue(results["local-code-review-skill.zip"]["passed"])
            self.assertFalse(results["github-pr-review-skill.zip"]["passed"])
            outcome = ar.replace(self.repo, self.TAG, self.work, upload=self._upload)
        self.assertEqual(self.uploads, ["local-code-review-skill.zip"])
        self.assertIn("left untouched", outcome["github-pr-review-skill.zip"]["skipped"])

    def test_replace_rechecks_the_published_copy_and_records_the_replaced_digest(self) -> None:
        with self._patched():
            verified = ar.verify(self.repo, self.TAG, self.work)
            outcome = ar.replace(self.repo, self.TAG, self.work, upload=self._upload)
        self.assertTrue(ar.phase_ok(outcome))
        entry = outcome["local-code-review-skill.zip"]
        self.assertEqual(entry["replaced_sha256"], verified["local-code-review-skill.zip"]["published_sha256"])
        self.assertEqual((entry["published_version"], entry["inventory_match"]), ("1.54.0", True))

    def test_asset_changed_since_verification_is_not_replaced(self) -> None:
        with self._patched():
            ar.verify(self.repo, self.TAG, self.work)
            self.published["local-code-review-skill.zip"] += b"!"
            outcome = ar.replace(self.repo, self.TAG, self.work, upload=self._upload)
        self.assertNotIn("local-code-review-skill.zip", self.uploads)
        self.assertIn("changed since verification", outcome["local-code-review-skill.zip"]["skipped"])

    def test_replace_requires_prior_verification(self) -> None:
        with self._patched(), self.assertRaisesRegex(ar.RepairError, "run the previous phase"):
            ar.replace(self.repo, self.TAG, self.work, upload=self._upload)

    def test_cli_refuses_to_replace_without_explicit_confirmation(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.object(ar, "replace") as replace:
            code = cli.main(["--work-dir", str(self.work), "replace", self.TAG])
        self.assertEqual(code, 2)
        replace.assert_not_called()


if __name__ == "__main__":
    unittest.main()
