"""Contract checks for requirement-coverage documentation and wiring."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "shared" / "policies" / "requirement-coverage.md"


class RequirementCoverageDocumentationTests(unittest.TestCase):
    def test_policy_defines_schema_states_and_inert_behavior(self) -> None:
        text = POLICY.read_text(encoding="utf-8")
        for token in (
            "requirement_coverage:",
            "implemented",
            "partially_evidenced",
            "not_evidenced",
            "not_applicable",
            "no activating contract is supplied",
            "keyword overlap",
        ):
            self.assertIn(token, text)

    def test_policy_separates_completeness_from_severity_and_decision(self) -> None:
        text = POLICY.read_text(encoding="utf-8")
        self.assertIn("Coverage is an assessment, not a fourth severity", text)
        self.assertIn("Decision` remains derived only from finalized P0/P1 findings", text)

    def test_both_skills_and_report_templates_are_wired(self) -> None:
        paths = (
            ROOT / "skills" / "local-code-review" / "SKILL.md",
            ROOT / "skills" / "github-pr-review" / "SKILL.md",
            ROOT / "skills" / "local-code-review" / "runbooks" / "local-review.md",
            ROOT / "skills" / "github-pr-review" / "runbooks" / "passive-pr-review.md",
            ROOT / "skills" / "github-pr-review" / "runbooks" / "active-pr-review.md",
            ROOT / "skills" / "local-code-review" / "metadata" / "skill.yaml",
            ROOT / "skills" / "github-pr-review" / "metadata" / "skill.yaml",
            ROOT / "skills" / "local-code-review" / "templates" / "local-review-report.md",
            ROOT / "skills" / "github-pr-review" / "templates" / "external-review-summary.md",
        )
        for path in paths:
            with self.subTest(path=path):
                self.assertIn("requirement-coverage.md", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
