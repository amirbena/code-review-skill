"""Contract checks for the review-stopping-criteria policy and its wiring
(Issue #89)."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

POLICY = REPO_ROOT / "shared" / "policies" / "review-stopping-criteria.md"
REVIEW_SCOPE = REPO_ROOT / "shared" / "policies" / "review-scope.md"
EVIDENCE = REPO_ROOT / "shared" / "policies" / "evidence.md"
SEVERITY = REPO_ROOT / "shared" / "policies" / "severity.md"
SHARED_README = REPO_ROOT / "shared" / "policies" / "README.md"
REVIEW_SUMMARY = REPO_ROOT / "shared" / "templates" / "review-summary.md"
MANIFEST = REPO_ROOT / "scripts" / "package-manifest.json"


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


class ReviewStoppingCriteriaWiringTests(unittest.TestCase):
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

    def test_shared_readme_has_a_policy_map_row(self) -> None:
        self.assertIn("review-stopping-criteria.md", SHARED_README.read_text(encoding="utf-8"))

    def test_review_summary_documents_the_decision_overriding_field(self) -> None:
        norm = _norm(REVIEW_SUMMARY)
        self.assertIn("review-stopping-criteria.md", REVIEW_SUMMARY.read_text(encoding="utf-8"))
        self.assertIn("is the one field in this block that is not merely", norm)

    def test_packaged_in_the_one_shared_manifest(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        destinations = [entry["destination"] for entry in manifest["shared_files"]]
        self.assertIn("shared/policies/review-stopping-criteria.md", destinations)

    def test_both_skills_load_and_list_the_policy(self) -> None:
        for path in (
            REPO_ROOT / "skills" / "local-code-review" / "SKILL.md",
            REPO_ROOT / "skills" / "github-pr-review" / "SKILL.md",
            REPO_ROOT / "skills" / "local-code-review" / "metadata" / "skill.yaml",
            REPO_ROOT / "skills" / "github-pr-review" / "metadata" / "skill.yaml",
            REPO_ROOT / "skills" / "local-code-review" / "runbooks" / "local-review.md",
            REPO_ROOT / "skills" / "github-pr-review" / "runbooks" / "active-pr-review.md",
            REPO_ROOT / "skills" / "github-pr-review" / "runbooks" / "passive-pr-review.md",
            REPO_ROOT / "skills" / "local-code-review" / "templates" / "local-review-report.md",
            REPO_ROOT / "skills" / "github-pr-review" / "templates" / "external-review-summary.md",
        ):
            with self.subTest(path=path):
                self.assertIn("review-stopping-criteria.md", path.read_text(encoding="utf-8"))

    def test_all_three_runbooks_have_a_dedicated_coverage_step(self) -> None:
        for path in (
            REPO_ROOT / "skills" / "local-code-review" / "runbooks" / "local-review.md",
            REPO_ROOT / "skills" / "github-pr-review" / "runbooks" / "active-pr-review.md",
            REPO_ROOT / "skills" / "github-pr-review" / "runbooks" / "passive-pr-review.md",
        ):
            with self.subTest(path=path):
                norm = _norm(path)
                self.assertIn("Evaluate review coverage", norm)

    def test_local_report_renders_coverage_and_incomplete_decision(self) -> None:
        text = (
            REPO_ROOT
            / "skills"
            / "local-code-review"
            / "templates"
            / "local-review-report.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Coverage:", text)
        self.assertIn("REVIEW INCOMPLETE", text)

    def test_github_template_renders_coverage_and_incomplete_decision(self) -> None:
        text = (
            REPO_ROOT
            / "skills"
            / "github-pr-review"
            / "templates"
            / "external-review-summary.md"
        ).read_text(encoding="utf-8")
        self.assertIn("coverage:", text)
        self.assertIn("REVIEW INCOMPLETE", text)

    def test_skill_entrypoint_line_ceilings_account_for_the_new_policy_line(self) -> None:
        guard_test = (
            REPO_ROOT / "tests" / "policy" / "governance" / "test_skill_entrypoint_guards.py"
        ).read_text(encoding="utf-8")
        self.assertIn("#89", guard_test)


class ReviewStoppingCriteriaDocsTests(unittest.TestCase):
    def test_architecture_and_comparison_and_feature_index_mention_it(self) -> None:
        for path in (
            REPO_ROOT / "docs" / "ARCHITECTURE.md",
            REPO_ROOT / "docs" / "CODE_REVIEW_COMPARISON.md",
            REPO_ROOT / "docs" / "features" / "README.md",
        ):
            with self.subTest(path=path):
                self.assertIn("review-stopping-criteria.md", path.read_text(encoding="utf-8"))

    def test_feature_index_lists_it_as_not_a_feature_guide(self) -> None:
        text = (REPO_ROOT / "docs" / "features" / "README.md").read_text(encoding="utf-8")
        not_a_guide = text.split("## Not a feature guide", 1)[1]
        self.assertIn("review-stopping-criteria.md", not_a_guide)

    def test_architecture_no_longer_calls_it_still_open(self) -> None:
        text = (REPO_ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
        self.assertNotIn("still-open concern", text)


if __name__ == "__main__":
    unittest.main()
