#!/usr/bin/env python3
"""Cutover from an integration branch (`release/v3`): the squash commit on
`main` expands into its child PRs' release intent, sync commits stay out, and
commits pulled in by a main -> branch sync stay out.

Contract: docs/RELEASE.md, "Integration branches".
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest

from tests.support.paths import REPO_ROOT
from tests.unit.release.test_changelog_generation import (
    PLACEHOLDER,
    SKILL,
    DOCS,
    _body,
    _merged,
    _PatchedRepoCase,
)

sys.path.insert(0, str(REPO_ROOT / "scripts" / "release"))

import release_worthiness as rw  # noqa: E402
from release_lib.changelog_generation import ChangelogGenerationError, collect_entries, compose_unreleased  # noqa: E402
from release_lib.semver_policy import classify_semver_impact  # noqa: E402
from release_lib.semver_version import derive_next_version  # noqa: E402

CUTOVER_SHA = "c" * 40
CHILD_A, CHILD_B, CHILD_DOCS, SYNC_PR = "a" * 40, "b" * 40, "d" * 40, "e" * 40
RELEASED = "f" * 40


def _cutover_pr(body: str) -> dict:
    pr = _merged(900, CUTOVER_SHA, body)
    pr["head"] = {"ref": "release/v3", "repo": {"full_name": "o/r"}}
    pr["base"] = {"ref": "main", "repo": {"full_name": "o/r"}}
    return pr


def _child(number: int, sha: str, body: str, base: str = "release/v3") -> dict:
    pr = _merged(number, sha, body)
    pr["base"] = {"ref": base}
    return pr


class _CutoverRepo:
    """Scripted main history (one cutover squash commit) plus the PR's commit listing."""

    def __init__(self, listing, prs, files, *, released=()):
        self.listing, self.prs, self.files, self.released = listing, prs, files, set(released)

    def git(self, args, repo_root):  # noqa: ANN001
        a = list(args)
        if a[:1] == ["log"]:
            return f"{CUTOVER_SHA}\x1fv3 cutover (#900)\n"
        if a[:2] == ["diff", "--name-only"]:
            return f"{SKILL}\n"
        if a[:2] == ["merge-base", "--is-ancestor"]:
            if a[2] in self.released:
                return ""
            raise subprocess.CalledProcessError(1, ["git", *a])
        raise AssertionError(f"unexpected git call: {a}")

    def gh(self, args, repo_root):  # noqa: ANN001
        a = list(args)
        path = a[a.index("api") + 1 if "--paginate" not in a else a.index("--paginate") + 1]
        parts = path.split("/")
        if parts[-1] == "commits":
            return "".join(f"{sha}\x1f{subject}\n" for sha, subject in self.listing)
        if parts[-1] == "files":
            return "".join(f"{p}\n" for p in self.files[int(parts[-2])])
        number = int(parts[-1])
        if number not in self.prs:
            raise subprocess.CalledProcessError(1, ["gh", *a])
        return json.dumps(self.prs[number])


class CutoverExpansionTests(_PatchedRepoCase):
    def _use(self, **overrides):
        prs = {
            900: _cutover_pr(_body("Breaking", "Review Core replaces the monolithic Skills")),
            11: _child(11, CHILD_A, _body("Added", "Mini-skill registry")),
            12: _child(12, CHILD_B, _body("Fixed", "Registry ordering")),
            13: _child(13, CHILD_DOCS, _body("Added", "Docs only")),
            700: _child(700, SYNC_PR, _body("Fixed", "Already released"), base="main"),
        }
        listing = [
            (CHILD_A, "feat: registry (#11)"),
            ("1" * 40, "Merge branch 'main' into release/v3"),
            (SYNC_PR, "fix: released on main (#700)"),
            (RELEASED, "fix: released earlier (#650)"),
            (CHILD_B, "fix: ordering (#12)"),
            (CHILD_DOCS, "docs: notes (#13)"),
        ]
        files = {11: [SKILL], 12: [SKILL], 13: [DOCS]}
        repo = _CutoverRepo(overrides.get("listing", listing), overrides.get("prs", prs), files, released=[RELEASED])
        rw.gitgh._git, rw.gitgh._gh = repo.git, repo.gh
        return repo

    def test_cutover_expands_child_entries_and_excludes_sync_commits(self) -> None:
        self._use()
        entries = collect_entries(self.root, "v2.4.0")
        self.assertEqual(sorted(e.pr_number for e in entries), [11, 12, 900])
        self.assertEqual({e.pr_number: e.category for e in entries}, {900: "Breaking", 11: "Added", 12: "Fixed"})

    def test_dry_run_yields_one_major_v3_with_breaking_and_child_entries(self) -> None:
        self._use()
        text = compose_unreleased(PLACEHOLDER, collect_entries(self.root, "v2.4.0"))
        self.assertEqual(classify_semver_impact(text), "major")
        self.assertEqual(derive_next_version("v2.4.0", "major"), "3.0.0")
        self.assertLess(text.index("### Breaking"), text.index("### Added"))
        for ref in ("(#900)", "(#11)", "(#12)"):
            self.assertIn(ref, text)
        for ref in ("(#700)", "(#650)", "(#13)"):
            self.assertNotIn(ref, text)

    def test_child_without_valid_intent_fails_closed(self) -> None:
        repo = self._use()
        repo.prs[12] = _child(12, CHILD_B, "no intent here")
        with self.assertRaises(ChangelogGenerationError) as ctx:
            collect_entries(self.root, "v2.4.0")
        self.assertIn("PR #12", str(ctx.exception))

    def test_truncated_commit_listing_fails_closed(self) -> None:
        self._use(listing=[("%040x" % i, f"x (#{1000 + i})") for i in range(250)])
        with self.assertRaises(ChangelogGenerationError):
            collect_entries(self.root, "v2.4.0")

    def test_fork_branch_named_like_an_integration_branch_is_not_expanded(self) -> None:
        repo = self._use()
        repo.prs[900]["head"] = {"ref": "release/v3", "repo": {"full_name": "fork/r"}}
        self.assertEqual([e.pr_number for e in collect_entries(self.root, "v2.4.0")], [900])


if __name__ == "__main__":
    unittest.main()
