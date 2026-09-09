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
