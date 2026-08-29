#!/usr/bin/env python3
"""Lightweight entry-contract guards for both SKILL.md files.

Scope note — these are deliberately *additive* and non-overlapping with
the rules' canonical owners:

* the detailed normative wording for the review-action / self-review
  boundary is pinned against ``policies/review-action-authorization.md``
  and ``policies/review-authority.md`` (and, for the entrypoint surface,
  ``tests/policy/test_review_action_authorization_docs.py``);
* the per-invocation approval contract is pinned against
  ``policies/invocation-approval.md`` and the metadata validator's SKILL
  marker set.

This module only adds what nothing else guards: that the slimmed
entrypoints still *link* their canonical policies (rather than quietly
re-absorbing them), a couple of boundary phrases that must stay visible
at the top of the file, soft line ceilings, and an anti-re-expansion
check on fenced flow blocks.
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT

LOCAL_SKILL = REPO_ROOT / "skills/local-code-review/SKILL.md"
GITHUB_SKILL = REPO_ROOT / "skills/github-pr-review/SKILL.md"

# Soft ceilings: the final slimmed size plus a small maintenance margin,
# well below the pre-refactor size (local 374, github 490). Raising one
# should be a deliberate, reviewed act — not something a drive-by edit
# does silently. Intermediate refactor sizes are not encoded here.
LOCAL_MAX_LINES = 260
GITHUB_MAX_LINES = 350


def _norm(path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class SoftLineCeilings(unittest.TestCase):
    def test_local_skill_stays_slim(self) -> None:
        n = len(LOCAL_SKILL.read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(
            n,
            LOCAL_MAX_LINES,
            f"local SKILL.md grew to {n} lines (ceiling {LOCAL_MAX_LINES}); "
            "move detail to its canonical policy instead of re-expanding the "
            "entrypoint",
        )

    def test_github_skill_stays_slim(self) -> None:
        n = len(GITHUB_SKILL.read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(
            n,
            GITHUB_MAX_LINES,
            f"github-pr-review SKILL.md grew to {n} lines (ceiling "
            f"{GITHUB_MAX_LINES}); move detail to its canonical policy "
            "instead of re-expanding the entrypoint",
        )

    def test_no_giant_ascii_flow_diagram_returns(self) -> None:
        # The old entrypoints carried 40-60 line arrow-per-line flow
        # diagrams that duplicated the runbooks. A compact block is fine;
        # a huge one is the smell we are guarding against.
        for path in (LOCAL_SKILL, GITHUB_SKILL):
            longest = 0
            for block in re.findall(
                r"```text\n(.*?)\n```", path.read_text("utf-8"), re.S
            ):
                longest = max(longest, len(block.splitlines()))
            self.assertLessEqual(
                longest,
                24,
                f"{path.name} has a {longest}-line fenced flow block; keep the "
                "entrypoint flow compact and let the runbook carry the detail",
            )


class LocalEntrypointStillLinksItsCanonicalPolicies(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(LOCAL_SKILL)

    def test_prominent_boundaries_still_named_at_the_entrypoint(self) -> None:
        # Marker-level only; the binding definitions live in the linked
        # policies. Approval wording is already covered by the metadata
        # validator, so it is not re-asserted here.
        self.assertIn("REVIEW ALREADY OWNED", self.t)
        self.assertIn("REVIEW CLEAN", self.t)
        self.assertIn("CHANGES REQUIRED", self.t)
        self.assertIn("mechanical", self.t.lower())
        for verb in ("edit files", "apply patches", "commit", "push", "create branches"):
            self.assertIn(verb, self.t)

    def test_canonical_policies_are_linked_not_restated(self) -> None:
        for link in (
            "policies/invocation-approval.md",
            "policies/repository-state.md",
            "shared/policies/review-scope.md",
            "shared/policies/severity.md",
            "shared/policies/evidence.md",
            "shared/policies/git-safety.md",
            "shared/policies/review-ownership.md",
            "shared/policies/review-context.md",
            "shared/policies/review-evidence.md",
        ):
            self.assertIn(link, self.t)


class GithubEntrypointStillLinksItsCanonicalPolicies(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(GITHUB_SKILL)

    def test_entrypoint_only_boundary_phrases_stay_visible(self) -> None:
        # Non-overlapping with test_review_action_authorization_docs
        # (which owns the section-7 phrasing) — these are the specifics
        # that only the slimmed top-of-file "Safety boundaries" callout
        # carries.
        self.assertIn("authority separation", self.t)
        self.assertIn("not merely a different GitHub username", self.t)
        self.assertIn("informational", self.t.lower())
        self.assertIn("COMMENT", _norm(GITHUB_SKILL))
        self.assertIn("GitHub review mutation withheld: reviewer is the PR author", self.t)

    def test_canonical_policies_are_linked_not_restated(self) -> None:
        for link in (
            "policies/github-review.md",
            "policies/review-authority.md",
            "policies/review-action-authorization.md",
            "policies/review-output.md",
            "policies/reviewer-delta-review.md",
            "shared/policies/review-context.md",
            "shared/policies/review-evidence.md",
            "shared/policies/severity.md",
            "shared/policies/review-ownership.md",
        ):
            self.assertIn(link, self.t)


if __name__ == "__main__":
    unittest.main()
