#!/usr/bin/env python3
"""Contract: shared/policies/review-base-policy.md as the single canonical
review-base compliance rule, wired identically into both Skills (#134).

Asserts both Skills reference the same shared policy at the correct point
in their own flow (right after base/topology resolution, before the
implementation-focused review step), that neither Skill forks a private
copy of its prose, and that the P0-before-implementation-findings and
fail-closed/HEAD-not-substituted invariants are stated in the canonical
file. Prose checks only — there is deliberately no second implementation
of the rule for either Skill (see policies/skill-development-policy.md,
"Runbook Design"); the deterministic resolution/comparison logic has its
own reference model and tests in
tests/reference/review/review_base_policy.py and
tests/unit/review/test_review_base_policy.py.
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import (
    GITHUB_ACTIVE_RUNBOOK,
    GITHUB_PASSIVE_RUNBOOK,
    GITHUB_REVIEW_INDEX,
    GITHUB_SKILL_DIR,
    GITHUB_SKILL_MD,
    LOCAL_RUNBOOK,
    LOCAL_SKILL_DIR,
    LOCAL_SKILL_MD,
)
from tests.support.policy_docs import load_normalized_text as _text

REVIEW_BASE_POLICY = REPO_ROOT / "shared/policies/review-base-policy.md"
SEVERITY = REPO_ROOT / "shared/policies/severity.md"
STACKED_PR_REVIEW = GITHUB_SKILL_DIR / "policies/stacked-pr-review.md"
REPOSITORY_STATE = LOCAL_SKILL_DIR / "policies/repository-state.md"
LOCAL_SKILL_YAML = LOCAL_SKILL_DIR / "metadata/skill.yaml"
GITHUB_SKILL_YAML = GITHUB_SKILL_DIR / "metadata/skill.yaml"


class CanonicalPolicyDefinesTheInvariantTests(unittest.TestCase):
    """The shared policy is the single owner of the invariant's substance."""

    def setUp(self) -> None:
        self.text = _text(REVIEW_BASE_POLICY)

    def test_repository_relative_no_hardcoded_branch_name(self) -> None:
        self.assertIn("repository-resolved review base", self.text)
        # Guard against a regression to a hardcoded assumption.
        self.assertNotIn("main branch is the review base", self.text)

    def test_head_never_substituted(self) -> None:
        self.assertIn(
            "Git HEAD is never substituted as the repository-resolved "
            "review base merely because it is HEAD",
            self.text,
        )

    def test_fail_closed_rule_present(self) -> None:
        self.assertIn("Fail-closed on an unresolved base", self.text)
        self.assertIn("emits nothing", self.text)

    def test_p0_before_implementation_findings(self) -> None:
        self.assertIn("Severity: P0", self.text)
        self.assertIn("Emitted before implementation findings", self.text)

    def test_stacked_pr_root_only_not_intermediate_layer(self) -> None:
        self.assertIn("never to an intermediate layer", self.text)

    def test_non_goals_match_issue_134(self) -> None:
        for phrase in (
            "Retargeting or editing a PR's base branch",
            "Changing GitHub branch protection, rulesets, or required checks",
            "General branch-naming validation unrelated to the review base",
            "Publishing a GitHub status/check for this outcome",
        ):
            self.assertIn(phrase, self.text)


class SeverityCrossReferenceTests(unittest.TestCase):
    def test_severity_references_review_base_policy_without_forking_it(self) -> None:
        text = _text(SEVERITY)
        self.assertIn("review-base-policy.md", text)
        self.assertIn(
            "mechanical decision derivation, which still runs exactly once",
            text,
        )
        self.assertNotIn("Fail-closed on an unresolved base", text)


class BothSkillsLoadTheSharedPolicyTests(unittest.TestCase):
    def test_local_skill_md_and_yaml_reference_it(self) -> None:
        self.assertIn("review-base-policy.md", _text(LOCAL_SKILL_MD))
        self.assertIn(
            "shared/policies/review-base-policy.md",
            LOCAL_SKILL_YAML.read_text(encoding="utf-8"),
        )

    def test_github_skill_md_and_yaml_reference_it(self) -> None:
        self.assertIn("review-base-policy.md", _text(GITHUB_SKILL_MD))
        self.assertIn(
            "shared/policies/review-base-policy.md",
            GITHUB_SKILL_YAML.read_text(encoding="utf-8"),
        )

    def test_local_runbook_checks_it_after_base_and_instruction_discovery(self) -> None:
        # The check must run after both step 2 (base resolution) and step 6
        # (repository-instruction discovery) — its explicit-statement signal
        # depends on discovery having already run — and before step 9 (the
        # implementation-focused review).
        text = _text(LOCAL_RUNBOOK)
        base_step = text.find("2. Resolve the base branch and base SHA")
        discovery_step = text.find("6. Discover applicable repository-local instructions")
        base_policy_step = text.find("8e. Check review-base policy compliance")
        review_step = text.find("9. Review the complete delta against")
        self.assertGreater(base_step, -1)
        self.assertGreater(discovery_step, base_step)
        self.assertGreater(base_policy_step, discovery_step)
        self.assertGreater(review_step, base_policy_step)

    def test_github_active_runbook_checks_it_after_topology_and_instruction_discovery(
        self,
    ) -> None:
        text = _text(GITHUB_ACTIVE_RUNBOOK)
        topology_step = text.find("resolve stack topology")
        discovery_step = text.find("8. Discover applicable repository-local instructions")
        base_policy_step = text.find("8d. Check review-base policy compliance")
        review_step = text.find("9. Review per")
        self.assertGreater(topology_step, -1)
        self.assertGreater(discovery_step, topology_step)
        self.assertGreater(base_policy_step, discovery_step)
        self.assertGreater(review_step, base_policy_step)

    def test_github_passive_runbook_checks_it_after_topology_and_instruction_discovery(
        self,
    ) -> None:
        text = _text(GITHUB_PASSIVE_RUNBOOK)
        topology_step = text.find("resolve stack topology")
        discovery_step = text.find("5. Discover applicable repository-local instructions")
        base_policy_step = text.find("5d. Check review-base policy compliance")
        review_step = text.find("6. Review the diff against")
        self.assertGreater(topology_step, -1)
        self.assertGreater(discovery_step, topology_step)
        self.assertGreater(base_policy_step, discovery_step)
        self.assertGreater(review_step, base_policy_step)

    def test_github_review_index_orders_it_after_repository_checkout(self) -> None:
        text = _text(GITHUB_REVIEW_INDEX)
        stacked_step = text.find("stacked-pr-review.md")
        checkout_step = text.find("repository-checkout.md")
        base_policy_step = text.find("review-base-policy.md")
        context_step = text.find("review-context.md")
        self.assertGreater(stacked_step, -1)
        self.assertGreater(checkout_step, stacked_step)
        self.assertGreater(base_policy_step, checkout_step)
        self.assertGreater(context_step, base_policy_step)


class NoForkedCopyTests(unittest.TestCase):
    """Neither Skill's own policy files fork the shared policy's prose."""

    def test_no_skill_policy_forks_the_canonical_heading(self) -> None:
        forbidden = "## Repository-resolved review base"
        for policy_dir in (LOCAL_SKILL_DIR / "policies", GITHUB_SKILL_DIR / "policies"):
            for policy_file in sorted(policy_dir.glob("*.md")):
                text = policy_file.read_text(encoding="utf-8")
                self.assertNotIn(
                    forbidden,
                    text,
                    f"{policy_file} must not fork {forbidden!r} from "
                    "shared/policies/review-base-policy.md",
                )

    def test_stacked_pr_review_references_but_does_not_redefine(self) -> None:
        text = _text(STACKED_PR_REVIEW)
        self.assertIn("review-base-policy.md", text)
        self.assertNotIn("## Repository-resolved review base", text)

    def test_repository_state_does_not_redefine_the_invariant(self) -> None:
        text = _text(REPOSITORY_STATE)
        self.assertNotIn("Fail-closed on an unresolved base", text)


if __name__ == "__main__":
    unittest.main()
