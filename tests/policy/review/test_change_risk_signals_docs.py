"""Contract checks for the change-risk signals policy and its wiring (Issue #86)."""

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

POLICY = REPO_ROOT / "shared" / "policies" / "change-risk-signals.md"
REVIEW_SCOPE = REPO_ROOT / "shared" / "policies" / "review-scope.md"
EVIDENCE = REPO_ROOT / "shared" / "policies" / "evidence.md"
REVIEW_SUMMARY = REPO_ROOT / "shared" / "templates" / "review-summary.md"


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").replace("**", "").replace("`", ""))


class ChangeRiskPolicyContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = POLICY.read_text(encoding="utf-8")
        self.norm = _norm(POLICY)

    def test_enumerates_every_issue_signal_with_a_tier(self) -> None:
        for signal in (
            "Auth / access-control change",
            "Migration / schema change",
            "Concurrency change",
            "Public API contract change",
            "Sensitive-path change",
            "Infra / config change",
            "Diff size",
        ):
            self.assertIn(signal, self.text)

    def test_deterministic_seven_step_classification_ordering(self) -> None:
        self.assertIn("## Classification ordering", self.text)
        for token in (
            "1. Detect",
            "2. Deduplicate",
            "3. Resolve",
            "highest applicable tier",
            "two or more independent resolved occurrences",
            "exactly one",
            "no occurrences",
        ):
            self.assertIn(token, self.norm)

    def test_dedup_never_downgrades_the_resolved_tier(self) -> None:
        self.assertIn(
            "Deduplication in step 2 must never lower the tier an occurrence resolves to",
            self.norm,
        )
        self.assertIn(
            "Overlapping labels on one fact do not reach deep", self.norm
        )

    def test_authoritative_diff_size_thresholds_with_ge_semantics(self) -> None:
        self.assertIn("## Diff-size thresholds", self.text)
        for token in ("≥ 150", "≥ 600", "≥ 10", "≥ 30"):
            self.assertIn(token, self.text)
        self.assertIn("at or above the number", self.norm)
        self.assertIn("149 activates nothing", self.norm)
        self.assertIn("exclude files classified non-reviewable", self.norm)
        self.assertIn(
            "never evidence that a change is defective", self.norm
        )

    def test_depth_only_conservative_tie_break_is_scoped(self) -> None:
        self.assertIn("## Depth-only conservative tie-break", self.text)
        self.assertIn("selects the higher review-effort level", self.norm)
        self.assertIn(
            "does not strengthen any finding's evidence label, severity, confidence, or applicability",
            self.norm,
        )
        self.assertIn(
            "can terminate a reasoning pass without a finding", self.norm
        )
        self.assertIn(
            "Ambiguity may cause more review; it never produces a stronger defect claim",
            self.norm,
        )

    def test_machine_model_and_rationale_emission(self) -> None:
        self.assertIn("change_risk:", self.text)
        self.assertIn("## Rationale emission", self.text)
        self.assertIn("emits the classification with its result", self.norm)
        self.assertIn("standard classification is still emitted", self.norm)
        self.assertIn("never in the primary human-facing body", self.norm)

    def test_non_goals_and_downstream_ownership_boundary(self) -> None:
        self.assertIn("## Non-goals and ownership boundary", self.text)
        self.assertIn("Not a merge gate.", self.text)
        self.assertIn("Never skips review.", self.text)
        self.assertIn("No PR splitting.", self.text)
        # #86 classifies only; #87/#88/#89 own what the levels do.
        self.assertIn("repository expansion", self.norm)
        self.assertIn("large-change partitioning", self.norm)
        self.assertIn("review stopping criteria", self.norm)

    def test_not_a_second_scope_or_evidence_model(self) -> None:
        self.assertIn("## Not a second scope or evidence model", self.text)
        self.assertIn("adds no second scope model and no second evidence", self.norm)
        self.assertIn("never lowers the bar for reporting a finding", self.norm)

    def test_always_active_no_toggle(self) -> None:
        self.assertIn("## Activation", self.text)
        self.assertIn("always active", self.norm)
        self.assertIn("no caller option to disable it", self.norm)


class ChangeRiskWiringTests(
    ChangelogRecordsPolicyMixin, SharedPolicyWiringMixin, unittest.TestCase
):
    wiring = SharedPolicyWiring(
        basename="change-risk-signals.md",
        issue="#86",
        runbook_markers=(
            "Classify change-risk depth",
            "Rationale emission",
            "Non-goals and ownership boundary",
        ),
        local_template_markers=(
            "Change-risk depth: <standard | elevated | deep>",
            "Change-risk signals:",
        ),
        github_template_markers=(
            "change_risk_depth:",
            "change_risk_signals:",
        ),
    )

    def test_review_scope_section_precedes_technology_neutrality(self) -> None:
        text = REVIEW_SCOPE.read_text(encoding="utf-8")
        heading = text.index("## Change-risk signals and review depth")
        neutrality = text.index("## Technology neutrality")
        self.assertLess(heading, neutrality)
        self.assertIn("not a second scope model", _norm(REVIEW_SCOPE))
        self.assertIn("change-risk-signals.md", text)

    def test_evidence_ties_scaling_to_the_depth_label(self) -> None:
        norm = _norm(EVIDENCE)
        self.assertIn("change-risk-signals.md", EVIDENCE.read_text(encoding="utf-8"))
        self.assertIn("standard / elevated / deep review-depth classification", norm)
        self.assertIn("tunes how much effort a review spends looking", norm)

    def test_review_summary_routes_it_to_subordinate_metadata(self) -> None:
        norm = _norm(REVIEW_SUMMARY)
        self.assertIn("change-risk-signals.md", REVIEW_SUMMARY.read_text(encoding="utf-8"))
        self.assertIn("always emitted in this subordinate block", norm)
        self.assertIn("one exception to consumer-gating", norm)
        self.assertIn("never as a finding and never in a way that implies a verdict", norm)


if __name__ == "__main__":
    unittest.main()
