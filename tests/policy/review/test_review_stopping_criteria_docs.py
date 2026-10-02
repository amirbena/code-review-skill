"""Contract checks for the review-stopping-criteria policy and its wiring
(Issue #89)."""

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

POLICY = REPO_ROOT / "shared" / "policies" / "review-stopping-criteria.md"
REVIEW_SCOPE = REPO_ROOT / "shared" / "policies" / "review-scope.md"
EVIDENCE = REPO_ROOT / "shared" / "policies" / "evidence.md"
SEVERITY = REPO_ROOT / "shared" / "policies" / "severity.md"
REVIEW_SUMMARY = REPO_ROOT / "shared" / "templates" / "review-summary.md"


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").replace("**", "").replace("`", ""))


class ReviewStoppingCriteriaPolicyContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = POLICY.read_text(encoding="utf-8")
        self.norm = _norm(POLICY)

    def test_coverage_section_scales_by_depth(self) -> None:
        self.assertIn("## Coverage", self.text)
        for token in ("standard", "elevated", "deep"):
            self.assertIn(token, self.text)
        self.assertIn("change-risk-signals.md", self.text)

    def test_coverage_scales_by_partitions_too(self) -> None:
        self.assertIn("large-pr-partitioning.md", self.text)
        self.assertIn("for every partition individually", self.norm)

    def test_incomplete_triggers_are_a_closed_set(self) -> None:
        self.assertIn("## Incomplete triggers", self.text)
        self.assertIn("closed set", self.norm)
        for token in (
            "A required pass could not be produced",
            "A partition could not be completed",
            "The complete Review Target could not be established",
            "A validation run the change's classified depth genuinely depends on",
        ):
            self.assertIn(token, self.text)

    def test_insufficient_evidence_stop_is_not_incomplete(self) -> None:
        self.assertIn("terminal outcome, not a coverage gap", self.norm)

    def test_labeling_never_presents_as_clean(self) -> None:
        self.assertIn("## Labeling", self.text)
        self.assertIn("must never present as clean", self.norm)
        self.assertIn("REVIEW INCOMPLETE", self.text)
        self.assertIn("never discards or hides a", self.norm)

    def test_review_incomplete_is_not_a_new_invented_value(self) -> None:
        self.assertIn("not a new value this policy invents", self.norm)
        self.assertIn("review-output.md", self.text)

    def test_machine_readable_model(self) -> None:
        self.assertIn("review_stopping_criteria:", self.text)
        self.assertIn("coverage: complete | incomplete", self.text)

    def test_non_goals_defer_github_enforcement_to_49(self) -> None:
        self.assertIn("## Non-goals and ownership boundary", self.text)
        self.assertIn("Not the GitHub enforcement/status mapping.", self.text)
        self.assertIn("review-status-enforcement.md", self.text)

    def test_shared_policy_never_links_into_a_skill_directory(self) -> None:
        # Packaging constraint: this file is packaged standalone into both
        # Skill archives, so it must never depend on the other Skill's
        # directory existing alongside it (see finding-rendering.md,
        # "Location source annotation").
        self.assertNotIn("skills/github-pr-review", self.text)
        self.assertNotIn("skills/local-code-review", self.text)

    def test_non_goals_defer_depth_and_partitioning(self) -> None:
        self.assertIn("Defers depth and partitioning.", self.text)
        self.assertIn("Defers each pass's own stop condition.", self.text)

    def test_never_lowers_evidence_bar(self) -> None:
        self.assertIn("Never lowers the evidence bar.", self.text)

    def test_not_a_second_scope_or_evidence_model(self) -> None:
        self.assertIn("## Not a second scope or evidence model", self.text)


class ReviewStoppingCriteriaWiringTests(
    SharedPolicyWiringMixin, unittest.TestCase
):
    wiring = SharedPolicyWiring(
        basename="review-stopping-criteria.md",
        issue="#89",
        runbook_markers=(
            "Evaluate review coverage",
        ),
        local_template_markers=(
            "Coverage:",
            "REVIEW INCOMPLETE",
        ),
        github_template_markers=(
            "coverage:",
            "REVIEW INCOMPLETE",
        ),
    )

    def test_review_scope_has_a_stopping_criteria_section(self) -> None:
        text = REVIEW_SCOPE.read_text(encoding="utf-8")
        self.assertIn("## Review stopping criteria", text)
        self.assertIn("review-stopping-criteria.md", text)

    def test_evidence_ties_coverage_to_the_same_standard(self) -> None:
        norm = _norm(EVIDENCE)
        self.assertIn("review-stopping-criteria.md", EVIDENCE.read_text(encoding="utf-8"))
        self.assertIn("never a finding's evidence bar", norm)

    def test_severity_notes_the_coverage_gated_override(self) -> None:
        norm = _norm(SEVERITY)
        self.assertIn("review-stopping-criteria.md", SEVERITY.read_text(encoding="utf-8"))
        self.assertIn("assumes the review that produced the finding set actually", norm)

    def test_review_summary_documents_the_decision_overriding_field(self) -> None:
        norm = _norm(REVIEW_SUMMARY)
        self.assertIn("review-stopping-criteria.md", REVIEW_SUMMARY.read_text(encoding="utf-8"))
        self.assertIn("is the one field in this block that is not merely", norm)

    def test_skill_entrypoint_line_ceilings_account_for_the_new_policy_line(self) -> None:
        guard_test = (
            REPO_ROOT / "tests" / "policy" / "governance" / "test_skill_entrypoint_guards.py"
        ).read_text(encoding="utf-8")
        self.assertIn("#89", guard_test)


class ReviewStoppingCriteriaDocsTests(unittest.TestCase):
    def test_architecture_no_longer_calls_it_still_open(self) -> None:
        text = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertNotIn("still-open concern", text)


if __name__ == "__main__":
    unittest.main()
