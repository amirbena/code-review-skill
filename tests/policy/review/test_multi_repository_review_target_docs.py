#!/usr/bin/env python3
"""Contract: skills/local-code-review/policies/multi-repository-review-target.md
as the single canonical multi-repository Review Target composition rule
(Issue #556, epic #555).

Asserts the Skill's SKILL.md and runbook wire in the optional
repository-roots input and the new policy at the correct point (after
step 0's validation, before the implementation-focused review), that the
epic's "membership is authorization" invariant and the N=1
backward-compatibility guarantee are stated in the canonical file, and
that the shared policies it extends (repository-expansion.md,
architectural-placement.md, repository-instructions.md,
finding-rendering.md) carry the narrow clauses this issue adds without
forking a second copy of the new policy's prose. Prose checks only — the
deterministic validation/composition logic has its own reference model
and tests in tests/reference/review/multi_repository_review_target.py and
tests/unit/review/test_multi_repository_review_target.py.
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import (
    LOCAL_RUNBOOK,
    LOCAL_SKILL_DIR,
    LOCAL_SKILL_MD,
)
from tests.support.policy_docs import load_normalized_text as _text

MULTI_REPO_POLICY = LOCAL_SKILL_DIR / "policies/multi-repository-review-target.md"
REPOSITORY_STATE = LOCAL_SKILL_DIR / "policies/repository-state.md"
LOCAL_REPORT_TEMPLATE = LOCAL_SKILL_DIR / "templates/local-review-report.md"
REPOSITORY_EXPANSION = REPO_ROOT / "shared/policies/repository-expansion.md"
ARCHITECTURAL_PLACEMENT = REPO_ROOT / "shared/policies/architectural-placement.md"
REPOSITORY_INSTRUCTIONS = REPO_ROOT / "shared/policies/repository-instructions.md"
FINDING_TEMPLATE = REPO_ROOT / "shared/templates/finding.md"
FINDING_RENDERING = REPO_ROOT / "shared/templates/finding-rendering.md"


class CanonicalPolicyDefinesTheInvariantTests(unittest.TestCase):
    """The Skill-own policy is the single owner of the composition contract."""

    def setUp(self) -> None:
        self.text = _text(MULTI_REPO_POLICY)

    def test_membership_is_authorization_invariant_present(self) -> None:
        self.assertIn("membership is authorization", self.text.lower())
        self.assertIn("never add a repository to the target", self.text)

    def test_n_equals_one_default_unchanged(self) -> None:
        self.assertIn("this policy does not apply, is not loaded, and changes nothing", self.text)

    def test_no_synthetic_shared_base(self) -> None:
        self.assertIn("No synthetic shared Git base or shared SHA is ever invented", self.text)

    def test_duplicate_alias_detection_fails_closed(self) -> None:
        self.assertIn("Fail closed", self.text)
        self.assertIn("git rev-parse --git-common-dir", self.text.replace("`", ""))

    def test_unresolved_member_narrows_never_fails_whole_review(self) -> None:
        self.assertIn("narrows", self.text)
        self.assertIn("never fails the entire review", self.text)

    def test_instruction_isolation_stated(self) -> None:
        self.assertIn(
            "applies only to files under that member's own root, and never to a sibling member's files",
            self.text,
        )

    def test_repo_qualified_location_reuses_existing_identity_field(self) -> None:
        self.assertIn("finding-stable-identity.md", self.text)
        self.assertIn("repo-alias", self.text)

    def test_non_goals_match_issue_556(self) -> None:
        for phrase in (
            "Automatic sibling-repository discovery",
            "External repository cloning or fetching",
            "Repository-intelligence graph behavior",
            "Stateful cross-repository GitHub PR review machinery",
        ):
            self.assertIn(phrase, self.text)


class SkillWiringTests(unittest.TestCase):
    def test_skill_md_references_the_policy(self) -> None:
        self.assertIn("multi-repository-review-target.md", _text(LOCAL_SKILL_MD))

    def test_skill_md_states_default_unchanged_when_omitted(self) -> None:
        text = _text(LOCAL_SKILL_MD)
        self.assertIn("When omitted (the default)", text)

    def test_runbook_references_the_policy(self) -> None:
        self.assertIn("multi-repository-review-target.md", _text(LOCAL_RUNBOOK))

    def test_runbook_step_zero_precedes_step_one(self) -> None:
        text = _text(LOCAL_RUNBOOK)
        step_zero = text.find("0. If, and only if, the caller supplied a repository-roots list")
        step_one = text.find("1. Verify the target is a valid Git repository")
        self.assertGreater(step_zero, -1)
        self.assertGreater(step_one, step_zero)

    def test_runbook_composition_runs_once_after_per_member_steps(self) -> None:
        text = _text(LOCAL_RUNBOOK)
        step_zero = text.find("0. If, and only if, the caller supplied a repository-roots list")
        base_policy_step = text.find("8e. Check review-base policy compliance")
        review_step = text.find("9. Review the complete delta against")
        self.assertGreater(base_policy_step, step_zero)
        self.assertGreater(review_step, base_policy_step)


class SharedPolicyExtensionTests(unittest.TestCase):
    """The shared policies this issue extends carry the narrow clauses,
    without forking a second copy of the new policy's own prose."""

    def test_repository_expansion_clarifies_non_member_boundary(self) -> None:
        text = _text(REPOSITORY_EXPANSION)
        self.assertIn("already-admitted member repositories", text)
        self.assertIn("multi-repository-review-target.md", text)

    def test_architectural_placement_allows_sibling_member_ring(self) -> None:
        text = _text(ARCHITECTURAL_PLACEMENT)
        self.assertIn("already-admitted member repository", text)

    def test_repository_instructions_states_isolation(self) -> None:
        text = _text(REPOSITORY_INSTRUCTIONS)
        self.assertIn("independently for each", text)
        self.assertIn("never to a sibling member's files", text)

    def test_finding_rendering_defines_repo_alias_prefix(self) -> None:
        text = _text(FINDING_RENDERING)
        self.assertIn("repo-alias", text)
        self.assertIn("leading", text.lower())

    def test_finding_template_points_to_rendering_not_a_new_field(self) -> None:
        text = _text(FINDING_TEMPLATE)
        self.assertIn("not a new finding field", text)


class NoForkedCopyTests(unittest.TestCase):
    """Neither repository-state.md nor the report template redefines the
    composition contract itself — they reference it."""

    def test_repository_state_does_not_redefine_composition(self) -> None:
        text = _text(REPOSITORY_STATE)
        self.assertNotIn("## Validation and normalization of supplied roots", text)
        self.assertIn("multi-repository-review-target.md", text)

    def test_report_template_references_not_redefines(self) -> None:
        text = _text(LOCAL_REPORT_TEMPLATE)
        self.assertIn("multi-repository-review-target.md", text)
        self.assertNotIn("## Validation and normalization of supplied roots", text)


if __name__ == "__main__":
    unittest.main()
