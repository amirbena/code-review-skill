"""Contract checks for the large-PR-partitioning policy and its wiring (Issue #88)."""

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

POLICY = REPO_ROOT / "shared" / "policies" / "large-pr-partitioning.md"
REVIEW_SCOPE = REPO_ROOT / "shared" / "policies" / "review-scope.md"
EVIDENCE = REPO_ROOT / "shared" / "policies" / "evidence.md"
REVIEW_SUMMARY = REPO_ROOT / "shared" / "templates" / "review-summary.md"


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").replace("**", "").replace("`", ""))


class LargePrPartitioningPolicyContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = POLICY.read_text(encoding="utf-8")
        self.norm = _norm(POLICY)

    def test_activation_is_conditional_not_always_on(self) -> None:
        self.assertIn("## Activation", self.text)
        self.assertIn("conditional", self.norm)
        self.assertIn("not always-active", self.norm)

    def test_partitioning_threshold_is_authoritative(self) -> None:
        self.assertIn("## Partitioning threshold", self.text)
        self.assertIn("1200", self.text)
        self.assertIn("60", self.text)
        self.assertIn("change-risk-signals.md", self.text)

    def test_partition_construction_ordering(self) -> None:
        self.assertIn("## Partition construction", self.text)
        for token in (
            "Seed by directory",
            "Coherence merge",
            "Per-partition size cap",
            "Size-floor merge",
            "Oversized-partition flag",
        ):
            self.assertIn(token, self.text)

    def test_coherence_merge_is_evidence_based(self) -> None:
        self.assertIn("review-scope.md", self.text)
        self.assertIn("Related changes as one unit", self.text)
        self.assertIn("evidence-based, not name- or directory-based", self.norm)

    def test_per_partition_review_unchanged_policy_stack(self) -> None:
        self.assertIn("## Per-partition review", self.text)
        self.assertIn("computed once, for the", self.norm)

    def test_aggregation_and_cross_partition_dedup(self) -> None:
        self.assertIn("## Aggregation and cross-partition de-duplication", self.text)
        self.assertIn("root-cause-consolidation.md", self.text)
        self.assertIn("never affects the result", self.norm)

    def test_relationship_to_parallel_review(self) -> None:
        self.assertIn("## Relationship to parallel-review.md", self.text)
        self.assertIn("parallel-review.md", self.text)
        self.assertIn("independent axes and compose", self.norm)

    def test_determinism_section(self) -> None:
        self.assertIn("## Determinism", self.text)

    def test_reporting_is_conditional(self) -> None:
        self.assertIn("## Reporting", self.text)
        self.assertIn("conditional", self.norm)
        self.assertIn("carries no partitioning line at all", self.norm)

    def test_machine_readable_model(self) -> None:
        self.assertIn("large_pr_partitioning:", self.text)
        self.assertIn("activated:", self.text)

    def test_limits_section_states_its_limits(self) -> None:
        self.assertIn("## Limits", self.text)
        self.assertIn("stays oversized", self.norm)
        self.assertIn("not exhaustive", self.norm)

    def test_non_goals_and_ownership_boundary(self) -> None:
        self.assertIn("## Non-goals and ownership boundary", self.text)
        self.assertIn("Not a merge gate.", self.text)
        self.assertIn("No PR splitting.", self.text)
        self.assertIn("Never produces a shallower review.", self.text)

    def test_not_a_second_scope_or_evidence_model(self) -> None:
        self.assertIn("## Not a second scope or evidence model", self.text)
        self.assertIn("never lowers the evidence bar", self.norm)


class LargePrPartitioningWiringTests(
    ChangelogRecordsPolicyMixin, SharedPolicyWiringMixin, unittest.TestCase
):
    wiring = SharedPolicyWiring(
        basename="large-pr-partitioning.md",
        issue="#88",
        runbook_markers=(
            "Partition large changes",
            "never changes",
        ),
        local_template_markers=(
            "Large-PR partitioning:",
        ),
        github_template_markers=(
            "large_pr_partitioning:",
            "omitted entirely when inactive",
        ),
    )

    def test_review_scope_has_a_partitioning_section(self) -> None:
        text = REVIEW_SCOPE.read_text(encoding="utf-8")
        self.assertIn("## Large-change partitioning", text)
        self.assertIn("large-pr-partitioning.md", text)

    def test_evidence_ties_partitioning_to_the_same_standard(self) -> None:
        norm = _norm(EVIDENCE)
        self.assertIn("large-pr-partitioning.md", EVIDENCE.read_text(encoding="utf-8"))
        self.assertIn("coherent review units", norm)

    def test_review_summary_documents_the_conditional_field(self) -> None:
        norm = _norm(REVIEW_SUMMARY)
        self.assertIn("large-pr-partitioning.md", REVIEW_SUMMARY.read_text(encoding="utf-8"))
        self.assertIn("conditional on activation rather than consumer-gated", norm)

    def test_skill_entrypoint_line_ceilings_account_for_the_new_policy_line(self) -> None:
        guard_test = (
            REPO_ROOT / "tests" / "policy" / "governance" / "test_skill_entrypoint_guards.py"
        ).read_text(encoding="utf-8")
        self.assertIn("#88", guard_test)


class LargePrPartitioningDocsTests(unittest.TestCase):
    def test_architecture_no_longer_calls_partitioning_still_open(self) -> None:
        text = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertNotIn("large-change partitioning and\nreview stopping criteria", text)


if __name__ == "__main__":
    unittest.main()
