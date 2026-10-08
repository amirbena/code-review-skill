"""Tests for the #509 distribution publish/verify commands, against a real local bare remote."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
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
        shutil.copytree(Path(__file__).resolve().parents[3] / "distribution", self.repo / "distribution")
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
        self.assertEqual(
            sorted(files),
            [
                ".claude-plugin/marketplace.json",
                "DISTRIBUTION.json",
                "LICENSE",
                "README.md",
                "plugin.json",
                "skills/a/SKILL.md",
            ],
        )
        message = _git(self.remote, "log", "-1", "--format=%B", "v1.0.0")
        self.assertIn(f"Source-Commit: {SHA}", message)
        self.assertIn("Source-Tag: v1.0.0", message)
        self.assertIn(f"Source-Repository: {SRC}", message)
        self.assertEqual(self._run("distribution-verify")[0], 0)

    def test_manifests_carry_the_release_version_and_leave_skills_untouched(self) -> None:
        self._run("distribution-publish", version="2.3.4")
        show = lambda p: _git(self.remote, "show", f"v2.3.4:{p}")  # noqa: E731
        plugin = json.loads(show("plugin.json"))
        market = json.loads(show(".claude-plugin/marketplace.json"))
        self.assertEqual(plugin["version"], "2.3.4")
        self.assertEqual(market["plugins"][0]["version"], "2.3.4")
        self.assertEqual(market["plugins"][0]["source"], "./")
        self.assertEqual(plugin["$schema"], "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json")
        self.assertEqual(show("skills/a/SKILL.md"), "body")

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

    def test_tag_push_rejected_after_branch_succeeds_leaves_branch_but_no_tag(self) -> None:
        # #559: branch push succeeds, tag push specifically fails -> no tag.
        (self.remote / "hooks" / "pre-receive").write_text(
            "#!/bin/sh\nwhile read old new ref; do case \"$ref\" in refs/tags/*) exit 1;; esac; done\n"
        )
        (self.remote / "hooks" / "pre-receive").chmod(0o755)
        code, out = self._run("distribution-publish")
        self.assertEqual(code, 1)
        self.assertIn("tag", out)
        self.assertIn("could not be created", out)
        # The branch commit landed -- the failure is specific to the tag.
        self.assertNotEqual(_git(self.remote, "rev-parse", "main").strip(), "")
        files = _git(self.remote, "ls-tree", "-r", "--name-only", "main").split()
        self.assertIn("skills/a/SKILL.md", files)
        self.assertEqual(self._tags(), "")
        # Without the tag, verification (and therefore finalization) cannot
        # succeed for this version.
        self.assertEqual(self._run("distribution-verify")[0], 1)
        # Recovery is not a side channel around the gate: a later run with
        # the hook lifted completes the tag without a second commit, and
        # then verification succeeds.
        (self.remote / "hooks" / "pre-receive").unlink()
        head = _git(self.remote, "rev-parse", "main")
        code, out = self._run("distribution-publish")
        self.assertEqual(code, 0, out)
        self.assertIn("tagged", out)
        self.assertEqual(_git(self.remote, "rev-parse", "main"), head)
        self.assertEqual(self._run("distribution-verify")[0], 0)

    def _reject_tags_hook(self, message: str) -> None:
        hook = self.remote / "hooks" / "pre-receive"
        hook.write_text(
            "#!/bin/sh\nwhile read old new ref; do case \"$ref\" in refs/tags/*) "
            f"echo '{message}' >&2; exit 1;; esac; done\n"
        )
        hook.chmod(0o755)

    def test_tag_push_failure_reports_status_stderr_and_remote_state(self) -> None:
        self._reject_tags_hook("remote: Bypassed rule violations for refs/tags/v1.0.0")
        code, out = self._run("distribution-publish")
        self.assertEqual(code, 1)
        self.assertIn("git push exit status: 1", out)
        self.assertIn("Bypassed rule violations", out)
        self.assertIn("not proof that a ruleset enforced", out)
        self.assertIn("missing: the tag push did not land", out)
        head = _git(self.remote, "rev-parse", "main").strip()
        self.assertIn(f"expected v1.0.0 -> {head}", out)
        self.assertIn("publisher identity: bot <bot@example.com>", out)
        self.assertEqual(self._tags(), "")  # fail closed, nothing retried or forced

    def test_tag_push_failure_with_ref_already_present_is_distinguished(self) -> None:
        from release_lib import distribution as dist

        head = _git(self.remote, "rev-parse", "main").strip()
        _git(self.remote, "tag", "v1.0.0", head)
        exc = dist.GitCommandError("git push failed: boom", 1, "boom")
        text = dist._tag_push_diagnostics(self.tmp, str(self.remote), "v1.0.0", head, exc, "bot")
        self.assertIn("present at the expected commit", text)
        other = dist._tag_push_diagnostics(self.tmp, str(self.remote), "v1.0.0", "b" * 40, exc, "bot")
        self.assertIn("DIFFERENT commit", other)

    def test_sanitize_output_redacts_credentials(self) -> None:
        import os
        from unittest import mock

        from release_lib import distribution as dist

        with mock.patch.dict(os.environ, {dist.TOKEN_ENV: "s3cr3tvalue"}):
            raw = (
                "fatal: https://x-access-token:ghs_abc123@github.com/o/r.git s3cr3tvalue "
                "AUTHORIZATION: basic eC1hY2Nlc3M6dG9r"
            )
            clean = dist.sanitize_output(raw)
        for leaked in ("s3cr3tvalue", "ghs_abc123", "eC1hY2Nlc3M6dG9r", "x-access-token:"):
            self.assertNotIn(leaked, clean)

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

    def test_verify_fails_closed_when_the_tag_is_not_reachable_from_remote_main(self) -> None:
        # #559: tag object reached the remote but main's ref never advanced.
        self._run("distribution-publish")
        tag_commit = _git(self.remote, "rev-parse", "v1.0.0").strip()
        _git(self.remote, "update-ref", "refs/heads/main", tag_commit + "^")
        code, out = self._run("distribution-verify")
        self.assertEqual(code, 1)
        self.assertIn("not reachable from remote 'main'", out)

    def test_verify_reads_the_remote_afresh_not_a_cached_local_checkout(self) -> None:
        # `verify` runs as a separate CLI call and must independently refetch.
        self._run("distribution-publish")
        # Advance the fake remote's main after publish, unrelated to it.
        clone = self.tmp / "post-publish-clone"
        _git(self.tmp, "clone", "-q", str(self.remote), str(clone))
        _git(clone, "-c", "user.name=h", "-c", "user.email=h@x", "commit", "--allow-empty", "-m", "unrelated")
        _git(clone, "push", "-q", "origin", "main")
        code, out = self._run("distribution-verify")
        self.assertEqual(code, 0, out)  # the tag is still an ancestor of the advanced tip: still valid

    def test_zip_not_built_from_tree_is_refused(self) -> None:
        with zipfile.ZipFile(self.dist / "a-skill.zip", "w") as zf:
            zf.writestr("SKILL.md", "other")
        code, out = self._run("distribution-publish")
        self.assertEqual(code, 1)
        self.assertIn("was not built from", out)
        self.assertEqual(self._tags(), "")


if __name__ == "__main__":
    unittest.main()
