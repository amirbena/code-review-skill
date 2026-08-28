#!/usr/bin/env python3
"""Semantic drift guards for Issue #38 presentation contracts."""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT


INVOCATION = REPO_ROOT / "shared/policies/invocation-options.md"
SUMMARY = REPO_ROOT / "shared/templates/review-summary.md"
LOCAL = REPO_ROOT / "skills/local-code-review/templates/local-review-report.md"
GITHUB = REPO_ROOT / "skills/github-pr-review/templates/external-review-summary.md"
PR_TEMPLATE = REPO_ROOT / ".github/PULL_REQUEST_TEMPLATE.md"


class InvocationPolicyTests(unittest.TestCase):
    def test_precedence_and_isolation_are_canonical(self) -> None:
        text = INVOCATION.read_text(encoding="utf-8")
        normalized = re.sub(r"\s+", " ", text)
        for token in (
            "explicit canonical false",
            "explicit canonical true",
            "unambiguous natural-language value",
            "Skill default",
            "Start every invocation",
        ):
            self.assertIn(token, normalized)
        self.assertIn("mediation parity", text)

    def test_detail_precedence_and_defaults_are_documented(self) -> None:
        text = INVOCATION.read_text(encoding="utf-8")
        normalized = re.sub(r"\s+", " ", text)
        self.assertIn("finding-level decision > invocation option > Skill default", text)
        self.assertIn("local Skill defaults it to `true`", normalized)
        self.assertIn("GitHub Skill defaults it to `false`", normalized)


class SummaryPresentationTests(unittest.TestCase):
    def test_opening_is_assessment_and_safety_first(self) -> None:
        shared = SUMMARY.read_text(encoding="utf-8")
        self.assertIn("overall assessment, merge/proceed safety", shared)
        self.assertIn("Avoid mechanical", shared)

    def test_clean_examples_are_compact_without_findings_section(self) -> None:
        for path in (LOCAL, GITHUB):
            text = path.read_text(encoding="utf-8")
            clean = text.split("or, when clean:", 1)[-1].split("or, clean while", 1)[0]
            if path == GITHUB:
                clean = re.search(r"```markdown\n(.*?)\n```", text, re.S).group(1)
            self.assertNotIn("### Findings", clean)


class PullRequestTemplateTests(unittest.TestCase):
    def test_template_has_concise_agent_readable_structure(self) -> None:
        text = PR_TEMPLATE.read_text(encoding="utf-8")
        headings = re.findall(r"^## (.+)$", text, re.M)
        self.assertEqual(
            headings,
            ["What changed", "Why", "Behavior and contracts", "Governance and distribution", "Validation", "Reviewer focus"],
        )
        self.assertLess(len(text.splitlines()), 50)

    def test_required_governance_traceability_remains(self) -> None:
        text = PR_TEMPLATE.read_text(encoding="utf-8")
        for concept in (
            "Governance impact",
            "Policy / documentation impact",
            "Packaging / portability impact",
            "reviewer ownership",
            "invocation approval",
            "severity/decision",
            "mutation",
            "HEAD/SHA safety",
        ):
            self.assertIn(concept, text)


if __name__ == "__main__":
    unittest.main()
