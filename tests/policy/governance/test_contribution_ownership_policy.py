#!/usr/bin/env python3
"""Structural coverage for the contribution-ownership model: the canonical
policy exists and is repository-development only, AGENTS.md routes to it
with a short invariant, policies/README.md maps it, and CONTRIBUTING.md
carries the human-facing Good First Issue vs Contributor-owned guidance
that links back to the canonical policy.
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT

AGENTS = REPO_ROOT / "AGENTS.md"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
POLICY = REPO_ROOT / "policies" / "contribution-ownership-policy.md"
POLICIES_README = REPO_ROOT / "policies" / "README.md"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("**", "").replace("`", ""))


class CanonicalPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = POLICY.read_text(encoding="utf-8")
        self.norm = _norm(self.raw)

    def test_policy_exists_and_is_repository_development_only(self) -> None:
        self.assertTrue(POLICY.is_file())
        self.assertIn("not packaged into either Skill archive", self.norm)

    def test_policy_rejects_patch_size_as_the_criterion(self) -> None:
        self.assertIn("never diff size alone", self.norm)
        self.assertIn("blast radius", self.norm.lower())

    def test_policy_defines_the_four_classes_by_label(self) -> None:
        for label in ("maintainer-led", "good first issue", "contributor-owned", "type:infrastructure"):
            self.assertIn(label, self.norm, f"policy does not name the {label!r} label")

    def test_policy_covers_the_required_operational_sections(self) -> None:
        for needle in (
            "How an agent classifies",
            "Epic decomposition",
            "Ambiguous cases",
            "assign",
        ):
            self.assertIn(needle.lower(), self.norm.lower(), needle)


class SharedContractExceptionTests(unittest.TestCase):
    """The narrow exception: bounded implementation of an already-canonical
    shared/cross-Skill contract may be Contributor-owned, while defining or
    altering shared semantics — and any unresolved semantic, compatibility,
    security, or governance decision — always stays Maintainer-led.
    """

    def setUp(self) -> None:
        self.raw = POLICY.read_text(encoding="utf-8")
        self.norm = _norm(self.raw)

    def test_default_rule_is_preserved(self) -> None:
        self.assertIn(
            "defining or altering shared/cross-skill semantics is always maintainer-led",
            self.norm.lower(),
        )

    def test_exception_is_named_and_narrow(self) -> None:
        self.assertIn("touching a shared/cross-skill contract without redefining it", self.norm.lower())
        self.assertIn("merely touching", self.norm.lower())

    def test_exception_requires_all_five_criteria(self) -> None:
        for needle in (
            "canonical semantic owner",
            "does not grant authority to redefine",
            "ordinary engineering choices",
            "deterministic conformance",
            "maintainer / codeowners review remains required",
        ):
            self.assertIn(needle.lower(), self.norm.lower(), needle)

    def test_unresolved_semantic_or_governance_decisions_stay_maintainer_led(self) -> None:
        self.assertIn(
            "if any semantic, compatibility, security, or governance decision",
            self.norm.lower(),
        )
        self.assertIn("stays maintainer-led no", self.norm.lower())

    def test_maintainer_review_stays_required_regardless_of_classification(self) -> None:
        # Criterion 5 plus the explicit "not delegation of architectural
        # ownership" framing: contributor execution never removes the
        # maintainer/CODEOWNERS review step.
        self.assertIn("maintainer/codeowners review", self.norm.lower())
        self.assertIn("not delegation of architectural ownership", self.norm.lower())

    def test_no_new_ownership_label_is_introduced(self) -> None:
        for forbidden in ("maintainer-decision", "contributor-execution", "maintainer-review-required"):
            self.assertNotIn(forbidden, self.norm.lower())
        # Still only the pre-existing four labels are used anywhere in the policy.
        for label in ("maintainer-led", "good first issue", "contributor-owned"):
            self.assertIn(label, self.norm)

    def test_good_first_issue_is_a_separate_suitability_judgment(self) -> None:
        # `good first issue` is composed independently (e.g. via Type:
        # Infrastructure) and is never implied merely by Contributor-owned
        # or by the shared-contract exception.
        self.assertIn("not another name for `good first issue`".replace("`", ""), self.norm.lower())

    def test_ambiguous_shared_contract_case_defaults_conservative(self) -> None:
        self.assertIn("unclear whether all five shared-contract exception criteria hold", self.norm.lower())
        self.assertIn(
            "the exception requires every criterion",
            self.norm.lower(),
        )

    def test_epic_decomposition_diagram_covers_a_single_bounded_child_issue(self) -> None:
        self.assertIn("maintainer-owned canonical contract", self.norm.lower())
        self.assertIn("bounded issue that cannot redefine it", self.norm.lower())
        self.assertIn("contributor-owned implementation", self.norm.lower())


class AgentsRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = AGENTS.read_text(encoding="utf-8")

    def test_agents_states_a_short_invariant(self) -> None:
        self.assertIn("Contribution ownership and Issue classification.", self.raw)

    def test_agents_routes_to_the_canonical_policy(self) -> None:
        self.assertIn("](policies/contribution-ownership-policy.md)", self.raw)

    def test_agents_does_not_inline_the_taxonomy(self) -> None:
        norm = _norm(self.raw)
        # The class definitions live in the policy, not AGENTS.md.
        self.assertNotIn("Automation Good First Issue", norm)
        self.assertNotIn("blast radius, coupling to review semantics, and validation difficulty", norm.lower())


class PoliciesReadmeTests(unittest.TestCase):
    def test_readme_maps_the_new_policy(self) -> None:
        self.assertIn("](contribution-ownership-policy.md)", POLICIES_README.read_text(encoding="utf-8"))


class ContributingGuidanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = CONTRIBUTING.read_text(encoding="utf-8")
        self.norm = _norm(self.raw)

    def test_has_a_contribution_paths_section(self) -> None:
        self.assertIn("## Contribution paths", self.raw)

    def test_explains_good_first_issue_and_contributor_owned(self) -> None:
        for label in ("good first issue", "contributor-owned", "maintainer-led"):
            self.assertIn(label, self.norm)

    def test_states_the_two_non_equivalences(self) -> None:
        self.assertIn("Good First Issue != unimportant", self.raw)
        self.assertIn("Contributor-owned != maintainer-only", self.raw)

    def test_links_back_to_the_canonical_policy(self) -> None:
        self.assertIn("policies/contribution-ownership-policy.md", self.raw)

    def test_policy_remains_canonical_over_contributing(self) -> None:
        self.assertIn("canonical", self.norm.lower())


if __name__ == "__main__":
    unittest.main()
