"""Contract checks for the repository-expansion policy and its wiring (Issue #87)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT
from tests.support.shared_policy_wiring import (
    ChangelogRecordsPolicyMixin,
    SharedPolicyWiring,
    SharedPolicyWiringMixin,
)

POLICY = REPO_ROOT / "shared" / "policies" / "repository-expansion.md"
REVIEW_SCOPE = REPO_ROOT / "shared" / "policies" / "review-scope.md"
EVIDENCE = REPO_ROOT / "shared" / "policies" / "evidence.md"
REVIEW_SUMMARY = REPO_ROOT / "shared" / "templates" / "review-summary.md"


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").replace("**", "").replace("`", ""))


class RepositoryExpansionPolicyContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = POLICY.read_text(encoding="utf-8")
        self.norm = _norm(POLICY)

    def test_enumerates_every_expansion_trigger(self) -> None:
        for trigger in (
            "Call-site trigger",
            "Interface/contract trigger",
            "Migration/schema trigger",
            "Config-consumer trigger",
        ):
            self.assertIn(trigger, self.text)

    def test_ring_based_bounded_expansion(self) -> None:
        self.assertIn("## Bounded, ring-based expansion", self.text)
        for token in (
            "ring 0",
            "ring 1",
            "ring 2",
            "ring 3",
            "Stop at the first ring",
        ):
            self.assertIn(token, self.norm)

    def test_ceiling_scales_with_change_risk_depth(self) -> None:
        self.assertIn("## Expansion bound scales with change-risk depth", self.text)
        self.assertIn("change-risk-signals.md", self.text)
        self.assertIn("a ceiling, not a target", self.norm)
        self.assertIn("never forces expansion out to ring 3", self.norm)

    def test_determinism_section(self) -> None:
        self.assertIn("## Determinism", self.text)
        self.assertIn("no run-to-run variance", self.norm)

    def test_expansion_decisions_are_reported(self) -> None:
        self.assertIn("## Expansion decisions are reported", self.text)
        self.assertIn("never in the primary human-facing body", self.norm)
        self.assertIn('still emits the classification, as "none"', self.norm)

    def test_machine_readable_model(self) -> None:
        self.assertIn("repository_expansion:", self.text)
        self.assertIn("ring_reached:", self.text)

    def test_non_goals_and_ownership_boundary(self) -> None:
        self.assertIn("## Non-goals and ownership boundary", self.text)
        self.assertIn("Not a merge gate.", self.text)
        self.assertIn("No cross-repository expansion.", self.text)
        self.assertIn("Not a repository-wide audit.", self.text)

    def test_not_a_second_scope_or_evidence_model(self) -> None:
        self.assertIn("## Not a second scope or evidence model", self.text)
        self.assertIn("never lowers the evidence bar", self.norm)

    def test_always_active_no_toggle(self) -> None:
        self.assertIn("## Activation", self.text)
        self.assertIn("always active", self.norm)
        self.assertIn("no caller option to disable it", self.norm)


class RepositoryExpansionWiringTests(
    ChangelogRecordsPolicyMixin, SharedPolicyWiringMixin, unittest.TestCase
):
    wiring = SharedPolicyWiring(
        basename="repository-expansion.md",
        issue="#87",
        runbook_markers=(
            "Resolve repository expansion",
            "Expansion decisions are reported",
            "Non-goals and ownership boundary",
        ),
        local_template_markers=(
            "Repository expansion:",
        ),
        github_template_markers=(
            "repository_expansion_triggers:",
        ),
    )

    def test_review_scope_section_precedes_technology_neutrality(self) -> None:
        text = REVIEW_SCOPE.read_text(encoding="utf-8")
        heading = text.index("## Repository expansion")
        neutrality = text.index("## Technology neutrality")
        self.assertLess(heading, neutrality)
        self.assertIn("repository-expansion.md", text)

    def test_evidence_ties_scaling_to_the_triggers(self) -> None:
        norm = _norm(EVIDENCE)
        self.assertIn("repository-expansion.md", EVIDENCE.read_text(encoding="utf-8"))
        self.assertIn("bounded, ring-based procedure", norm)

    def test_review_summary_routes_it_to_subordinate_metadata(self) -> None:
        norm = _norm(REVIEW_SUMMARY)
        self.assertIn("repository-expansion.md", REVIEW_SUMMARY.read_text(encoding="utf-8"))
        self.assertIn("one exception to consumer-gating", norm)
        self.assertIn("never as a finding and never in a way that implies a verdict", norm)


if __name__ == "__main__":
    unittest.main()
