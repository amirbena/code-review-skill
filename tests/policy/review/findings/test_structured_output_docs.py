#!/usr/bin/env python3
"""Documentation-contract checks for github-pr-review structured output (Issue #70).

Pins that the packaged policy populates every PR-shaped schema field, uses
the schema's own enum values, and stays off the publication path.

Run with:
    python3 -m unittest tests.policy.review.findings.test_structured_output_docs
"""

from __future__ import annotations

import json
import unittest

from tests.support.paths import REPO_ROOT

POLICY = REPO_ROOT / "skills" / "github-pr-review" / "policies" / "structured-output.md"
OUTPUT_POLICY = REPO_ROOT / "skills" / "github-pr-review" / "policies" / "review-output.md"
SCHEMA = REPO_ROOT / "docs" / "review-result" / "review-result.schema.json"


class StructuredOutputPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = POLICY.read_text(encoding="utf-8")
        self.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_every_reviewed_state_field_is_populated(self) -> None:
        for key in self.schema["properties"]["reviewed_state"]["required"]:
            self.assertIn(f"`reviewed_state.{key}`", self.text)

    def test_decision_fields_and_skill_value_are_populated(self) -> None:
        for token in ("`decision.derived`", "`decision.outcome`", "`skill`"):
            self.assertIn(token, self.text)
        self.assertIn("github-pr-review", self.schema["properties"]["skill"]["enum"])

    def test_decision_values_match_schema_enums(self) -> None:
        decision = self.schema["properties"]["decision"]["properties"]
        for value in decision["outcome"]["enum"]:
            self.assertIn(f"`{value}`", self.text)

    def test_not_a_commit_status_and_not_published(self) -> None:
        self.assertIn("review-status-enforcement.md", self.text)
        self.assertIn("never an input to the publication payload", self.text)
        self.assertNotIn("structured-output", OUTPUT_POLICY.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
