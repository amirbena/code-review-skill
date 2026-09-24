"""Tests for the #509 distribution publish/verify commands, against a real local bare remote."""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.unit.release._shared import rw

SRC = "amirbena/code-review-skill"
SHA = "a" * 40
IDENT = ["--git-name", "bot", "--git-email", "bot@example.com"]


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


class DistributionTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.remote = self.tmp / "remote.git"
        _git(self.tmp, "init", "--bare", "-b", "main", str(self.remote))
        seed = self.tmp / "seed"
        seed.mkdir()
        _git(seed, "init", "-b", "main")
        _git(seed, "-c", "user.name=h", "-c", "user.email=h@x", "commit", "--allow-empty", "-m", "bootstrap")
        _git(seed, "push", str(self.remote), "main")
        self.repo = self.tmp / "repo"
        self._make_repo()
        self.dist = self.repo / "dist"
        self._make_build("body")

    def _make_repo(self) -> None:
        (self.repo / "scripts" / "packaging").mkdir(parents=True)
        (self.repo / "LICENSE").write_text("MIT\n")
        (self.repo / "scripts" / "packaging" / "package-manifest.json").write_text(
            json.dumps({"skills": {"a": {"name": "a", "archive": "a-skill.zip"}}})
        )

    def _make_build(self, body: str) -> None:
        tree = self.dist / "skills" / "a"
        tree.mkdir(parents=True, exist_ok=True)
        (tree / "SKILL.md").write_text(body)
        import hashlib

        files = {"SKILL.md": hashlib.sha256(body.encode()).hexdigest()}
        (self.dist / "skills-manifest.json").write_text(json.dumps({"skills": {"a": {"files": files}}}))
        with zipfile.ZipFile(self.dist / "a-skill.zip", "w") as zf:
            zf.writestr("SKILL.md", body)

    def _run(self, command: str, version: str = "1.0.0", extra: list[str] | None = None) -> tuple[int, str]:
        argv = [
            "--repo-root", str(self.repo), command, "--version", version, "--source-commit", SHA,
            "--source-repository", SRC, "--remote", str(self.remote), "--dist", str(self.dist),
        ]
        if command == "distribution-publish":
            argv += IDENT
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = rw.main(argv + (extra or []))
        return code, out.getvalue()

    def _tags(self) -> str:
        return _git(self.remote, "tag", "--list")

    def test_publish_tags_commit_with_trailers_and_verifies(self) -> None:
        code, out = self._run("distribution-publish")
        self.assertEqual(code, 0, out)
        self.assertEqual(self._tags().split(), ["v1.0.0"])
        files = _git(self.remote, "ls-tree", "-r", "--name-only", "v1.0.0").split()
        self.assertEqual(sorted(files), ["DISTRIBUTION.json", "LICENSE", "README.md", "skills/a/SKILL.md"])
        message = _git(self.remote, "log", "-1", "--format=%B", "v1.0.0")
        self.assertIn(f"Source-Commit: {SHA}", message)
        self.assertIn("Source-Tag: v1.0.0", message)
        self.assertIn(f"Source-Repository: {SRC}", message)
        self.assertEqual(self._run("distribution-verify")[0], 0)

    def test_rerun_with_identical_content_is_a_noop(self) -> None:
        self._run("distribution-publish")
        head = _git(self.remote, "rev-parse", "main")
        code, out = self._run("distribution-publish")
        self.assertEqual(code, 0, out)
        self.assertIn("unchanged", out)
        self.assertEqual(_git(self.remote, "rev-parse", "main"), head)

    def test_rerun_with_different_content_fails_without_mutation(self) -> None:
        self._run("distribution-publish")
        head, tag = _git(self.remote, "rev-parse", "main"), _git(self.remote, "rev-parse", "v1.0.0")
        self._make_build("changed")
        code, out = self._run("distribution-publish")
        self.assertEqual(code, 1)
        self.assertIn("different content", out)
        self.assertEqual(_git(self.remote, "rev-parse", "main"), head)
        self.assertEqual(_git(self.remote, "rev-parse", "v1.0.0"), tag)

    def test_lagging_tag_is_completed_without_a_second_commit(self) -> None:
        self._run("distribution-publish")
        head = _git(self.remote, "rev-parse", "main")
        _git(self.remote, "tag", "-d", "v1.0.0")
        code, out = self._run("distribution-publish")
        self.assertEqual(code, 0, out)
        self.assertIn("tagged", out)
        self.assertEqual(_git(self.remote, "rev-parse", "main"), head)
        self.assertEqual(self._run("distribution-verify")[0], 0)

    def test_rejected_push_leaves_no_tag(self) -> None:
        (self.remote / "hooks" / "pre-receive").write_text("#!/bin/sh\nexit 1\n")
        (self.remote / "hooks" / "pre-receive").chmod(0o755)
        code, out = self._run("distribution-publish")
        self.assertEqual(code, 1)
        self.assertIn("rejected", out)
        self.assertEqual(self._tags(), "")

    def test_older_version_is_refused_when_main_carries_a_newer_one(self) -> None:
        self._run("distribution-publish", "1.1.0")
        head = _git(self.remote, "rev-parse", "main")
        code, out = self._run("distribution-publish", "1.0.0")
        self.assertEqual(code, 1)
        self.assertIn("older content", out)
        self.assertEqual(_git(self.remote, "rev-parse", "main"), head)
        self.assertEqual(self._tags().split(), ["v1.1.0"])

    def test_unorderable_tip_tag_fails_closed(self) -> None:
        clone = self.tmp / "clone"
        _git(self.tmp, "clone", "-q", str(self.remote), str(clone))
        _git(clone, "-c", "user.name=h", "-c", "user.email=h@x", "commit", "--allow-empty", "-m",
             "x\n\nSource-Tag: vnext")
        _git(clone, "push", "-q", "origin", "main")
        head = _git(self.remote, "rev-parse", "main")
        code, out = self._run("distribution-publish")
        self.assertEqual(code, 1)
        self.assertIn("cannot order", out)
        self.assertEqual(_git(self.remote, "rev-parse", "main"), head)
        self.assertEqual(self._tags(), "")

    def test_verify_detects_content_mismatch_and_missing_tag(self) -> None:
        self.assertEqual(self._run("distribution-verify")[0], 1)
        self._run("distribution-publish")
        self._make_build("changed")
        code, out = self._run("distribution-verify")
        self.assertEqual(code, 1)
        self.assertIn("differs from the build", out)

    def test_zip_not_built_from_tree_is_refused(self) -> None:
        with zipfile.ZipFile(self.dist / "a-skill.zip", "w") as zf:
            zf.writestr("SKILL.md", "other")
        code, out = self._run("distribution-publish")
        self.assertEqual(code, 1)
        self.assertIn("was not built from", out)
        self.assertEqual(self._tags(), "")


if __name__ == "__main__":
    unittest.main()
