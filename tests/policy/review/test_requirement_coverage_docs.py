"""Contract checks for requirement-coverage documentation and wiring."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
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

    def test_policy_distinguishes_ambiguity_from_proven_non_applicability(self) -> None:
        text = POLICY.read_text(encoding="utf-8")
        self.assertIn("no entry carries unresolved `ambiguity`", text)
        self.assertIn("that modifier makes\naggregate coverage incomplete", text)
        self.assertIn("affirmative evidence that it does not apply", text)

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


class RequirementCoverageRenderingTests(unittest.TestCase):
    def test_shared_contract_preserves_coverage_in_every_mode(self) -> None:
        text = (ROOT / "shared" / "templates" / "review-summary.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("semantic invariant across findings, clean, structured", text)
        human = text.split("## Concise human-style summary (opt-in)", 1)[1]
        self.assertIn("requirement coverage", human)
        self.assertIn("overall signal", human)
        self.assertIn("every requirement/status", human)

    def test_github_clean_findings_and_human_renderings_keep_coverage(self) -> None:
        text = (
            ROOT
            / "skills"
            / "github-pr-review"
            / "templates"
            / "external-review-summary.md"
        ).read_text(encoding="utf-8")
        clean, remainder = text.split("## Review with findings", 1)
        findings, human = remainder.split("## Concise human-style body (opt-in)", 1)
        self.assertIn("### Requirement coverage", clean)
        self.assertIn("### Requirement coverage", findings)
        self.assertIn("**Requirement coverage:**", human)

    def test_local_clean_findings_and_human_renderings_keep_coverage(self) -> None:
        text = (
            ROOT
            / "skills"
            / "local-code-review"
            / "templates"
            / "local-review-report.md"
        ).read_text(encoding="utf-8")
        findings, clean_and_human = text.split("or, when clean:", 1)
        self.assertIn("### Requirement coverage", findings)
        self.assertIn("include the full conditional\nRequirement coverage", clean_and_human)
        human = text.split("**Concise human-style output (opt-in).**", 1)[1]
        self.assertIn("remains visible with its overall signal\n  and every requirement/status", human)

    def test_inert_coverage_remains_absent(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        shared = (ROOT / "shared" / "templates" / "review-summary.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("When coverage was inert, every mode omits", policy)
        self.assertIn("absent when no authoritative task contract", shared)


if __name__ == "__main__":
    unittest.main()
