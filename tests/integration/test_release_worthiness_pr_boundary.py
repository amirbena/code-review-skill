#!/usr/bin/env python3
"""Real-git regression for the PR release-worthiness comparison boundary.

Contract: docs/RELEASE.md, "PR / push checks (read-only)".

A PR branch that has been synchronized with `main` must be assessed only
against what it itself contributes — the merge-base with the *current*
base branch — never against release-worthy history that entered the
branch through that sync/merge. Regression case: issue #215 / PR #214.
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))

import release_worthiness as rw  # noqa: E402

_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Boundary Test",
    "GIT_AUTHOR_EMAIL": "boundary@example.invalid",
    "GIT_COMMITTER_NAME": "Boundary Test",
    "GIT_COMMITTER_EMAIL": "boundary@example.invalid",
    "GIT_TERMINAL_PROMPT": "0",
}

_UNCOVERED_CHANGELOG = """\
# Changelog

## Unreleased

_Nothing yet._

## v1.0.0 — 2026-01-01

- prior release
"""

_COVERED_CHANGELOG = """\
# Changelog

## Unreleased

### Added

- The PR's own release-worthy change (#215).

## v1.0.0 — 2026-01-01

- prior release
"""


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env={**os.environ, **_GIT_ENV},
        check=True,
    )
    return proc.stdout.strip()


def _commit(work: Path, rel: str, content: str, message: str) -> str:
    (work / rel).parent.mkdir(parents=True, exist_ok=True)
    (work / rel).write_text(content, encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-m", message)
    return _git(work, "rev-parse", "HEAD")


class PrSyncedWithMainBoundaryTests(unittest.TestCase):
    """origin/main advances with a release-worthy change of its own; the PR
    branch merges that in. The PR must still be judged only on its own
    delta."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)

        origin = root / "origin.git"
        _git(root, "init", "--bare", "-b", "main", str(origin))
        self.work = root / "work"
        _git(root, "clone", str(origin), str(self.work))
        _git(self.work, "config", "commit.gpgsign", "false")

        _commit(self.work, "README.md", "start\n", "A: init")
        self.fork_point = _commit(self.work, "docs/x.md", "docs\n", "B: base")
        _git(self.work, "push", "origin", "main")

        # PR branch forks here; base.sha in the event payload is this commit.
        self.stale_base_sha = self.fork_point
        _git(self.work, "checkout", "-b", "feature")

        # main advances with a release-worthy Skill change and a rolled
        # CHANGELOG, then the PR branch synchronizes with it.
        _git(self.work, "checkout", "main")
        _commit(
            self.work,
            "skills/github-pr-review/runbooks/other.md",
            "unrelated skill work merged on main\n",
            "C: release-worthy change on main",
        )
        _git(self.work, "push", "origin", "main")
        self.current_main = _git(self.work, "rev-parse", "main")
        _git(self.work, "checkout", "feature")

    def _resolve_pr_base(self) -> str:
        out = Path(self._tmp.name) / "gh-out.txt"
        with contextlib.redirect_stdout(io.StringIO()):
            rc = rw.main([
                "--repo-root", str(self.work),
                "resolve-base-ref",
                "--event-name", "pull_request",
                "--pr-base-ref", "main",
                "--pr-base-sha", self.stale_base_sha,
                "--github-output", str(out),
            ])
        self.assertEqual(rc, 0)
        pairs = dict(
            line.split("=", 1)
            for line in out.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )
        return pairs["ref"]

    def _assess(self, base_ref: str, changelog_text: str) -> int:
        changelog = Path(self._tmp.name) / "CHANGELOG.md"
        changelog.write_text(changelog_text, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            return rw.main([
                "--repo-root", str(self.work),
                "--changelog", str(changelog),
                "assess",
                "--require-changelog",
                "--base-ref", base_ref,
                "--github-output", str(Path(self._tmp.name) / "assess-out.txt"),
            ])

    def test_docs_only_pr_is_not_dragged_release_worthy_by_synced_main(self) -> None:
        _commit(self.work, "docs/feature.md", "just docs\n", "D: docs-only PR change")
        _git(self.work, "merge", "--no-edit", "origin/main")

        # The stale payload base.sha still sees the Skill file that only
        # entered through the sync — the bug.
        stale = rw.classify_paths(rw.changed_files(self.work, self.stale_base_sha))
        self.assertTrue(stale.release_worthy)

        # The resolved base is the merge-base with current main (here:
        # main's tip, now an ancestor of the synced branch); the three-dot
        # diff against it is the PR's own delta only.
        base = self._resolve_pr_base()
        self.assertEqual(base, self.current_main)
        files = rw.changed_files(self.work, base)
        self.assertIn("docs/feature.md", files)
        self.assertNotIn("skills/github-pr-review/runbooks/other.md", files)
        self.assertFalse(rw.classify_paths(files).release_worthy)

    def test_release_worthy_pr_keeps_only_its_own_changelog_obligation(self) -> None:
        _commit(
            self.work,
            "skills/local-code-review/policies/new-rule.md",
            "this PR's own release-worthy change\n",
            "D: release-worthy PR change",
        )
        _git(self.work, "merge", "--no-edit", "origin/main")

        base = self._resolve_pr_base()
        self.assertEqual(base, self.current_main)
        files = rw.changed_files(self.work, base)
        self.assertIn("skills/local-code-review/policies/new-rule.md", files)
        self.assertNotIn("skills/github-pr-review/runbooks/other.md", files)
        self.assertTrue(rw.classify_paths(files).release_worthy)

    def test_synced_pr_with_matching_unreleased_coverage_passes_the_gate(self) -> None:
        # End-to-end: resolve-base-ref (synced branch) -> assess. The PR's
        # own release-worthy change is covered under `## Unreleased`, so the
        # gate passes even though newer `main` history was merged in.
        _commit(
            self.work,
            "skills/local-code-review/policies/new-rule.md",
            "this PR's own release-worthy change\n",
            "D: release-worthy PR change",
        )
        _git(self.work, "merge", "--no-edit", "origin/main")

        self.assertEqual(self._assess(self._resolve_pr_base(), _COVERED_CHANGELOG), 0)

    def test_synced_pr_with_its_own_uncovered_change_still_fails_closed(self) -> None:
        # End-to-end: the synced-in `main` history is excluded, but the PR's
        # own uncovered release-worthy change still fails the CHANGELOG gate.
        _commit(
            self.work,
            "skills/local-code-review/policies/new-rule.md",
            "this PR's own release-worthy change, with no changelog entry\n",
            "D: uncovered release-worthy PR change",
        )
        _git(self.work, "merge", "--no-edit", "origin/main")

        self.assertEqual(self._assess(self._resolve_pr_base(), _UNCOVERED_CHANGELOG), 1)

    def test_push_boundary_still_uses_the_previous_release_tag(self) -> None:
        # The accumulated-set boundary for main is unchanged: no PR base
        # branch is consulted, the previous v* tag is.
        _git(self.work, "checkout", "main")
        _git(self.work, "tag", "v9.9.9")
        _commit(self.work, "skills/local-code-review/policies/z.md", "later\n", "E: post-tag")
        out = Path(self._tmp.name) / "push-out.txt"
        with contextlib.redirect_stdout(io.StringIO()):
            rc = rw.main([
                "--repo-root", str(self.work),
                "resolve-base-ref",
                "--event-name", "push",
                "--pr-base-ref", "main",
                "--pr-base-sha", self.stale_base_sha,
                "--github-output", str(out),
            ])
        self.assertEqual(rc, 0)
        pairs = dict(
            line.split("=", 1)
            for line in out.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )
        self.assertEqual(pairs["ref"], "v9.9.9")


if __name__ == "__main__":
    unittest.main()
