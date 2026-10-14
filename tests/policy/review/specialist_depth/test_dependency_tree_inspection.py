#!/usr/bin/env python3
"""Opt-in dependency tree inspection (Issue #730).

Contract: shared/policies/dependency-tree-inspection.md, routed from the
"Dependency / supply-chain deepening review" section of review-scope.md.
Prose checks only; there is no second implementation of the rules.
"""

from __future__ import annotations

import unittest

from tests.support.policy_docs import REVIEW_SCOPE, REPO_ROOT
from tests.support.policy_docs import load_normalized_text as _text

POLICY = REPO_ROOT / "shared/policies/dependency-tree-inspection.md"


class DependencyTreeInspectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY)

    def test_review_scope_routes_to_policy(self) -> None:
        self.assertIn("dependency-tree-inspection.md", _text(REVIEW_SCOPE))

    def test_activation_reuses_existing_signal(self) -> None:
        self.assertIn("reorder, whitespace, or comment-only", self.text)
        self.assertIn("Never routed by filename", self.text)

    def test_proposal_discloses_five_items_and_scoped_approval(self) -> None:
        for item in ("exact command", "working directory", "purpose",
                     "plugins or scripts", "filesystem, network, and credential"):
            self.assertIn(item, self.text)
        self.assertIn("Approval never overrides a sandbox", self.text)
        self.assertIn("carries to no other command", self.text)

    def test_supplied_output_is_data_and_nothing_executes(self) -> None:
        self.assertIn("executes nothing", self.text)
        self.assertIn("never instructions", self.text)

    def test_validation_head_only_and_gaps(self) -> None:
        self.assertIn("never treat it as a clean tree", self.text)
        self.assertIn("Base was not compared", self.text)
        self.assertIn("Context gap", self.text)
        self.assertIn("never creates a finding and never raises severity", self.text)

    def test_api_only_mode_is_workflow_2_only(self) -> None:
        self.assertIn("API-only mode", self.text)
        self.assertIn("offers Workflow 2 only", self.text)

    def test_confidence_follows_existing_mapping(self) -> None:
        self.assertIn("follows the existing mapping, never the tree's source", self.text)
        self.assertIn("provenance", self.text)

    def test_summary_template_renders_tree_evidence_gaps(self) -> None:
        summary = _text(REPO_ROOT / "shared/templates/review-summary.md")
        self.assertIn("dependency-tree evidence gap", summary)
        self.assertIn("the command that obtains valid evidence", summary)
        self.assertIn("one bullet per unresolved relationship", summary)


if __name__ == "__main__":
    unittest.main()
