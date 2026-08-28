#!/usr/bin/env python3
"""Behavioral coverage for local and GitHub remediation output."""

from __future__ import annotations

import unittest

from tests.reference import remediation_guidance as rg


class RemediationGuidanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.structural = rg.Finding(
            "F1",
            "P1",
            "Parallel current-evidence ownership",
            "Reuse the canonical current-evidence classifier before historical conformance.",
            "Move classification to the shared test/reference owner; make both models consume it; preserve materiality and add composed reconciliation regressions.",
        )

    def test_local_default_off_has_no_full_prompt(self) -> None:
        review = rg.render_local([self.structural])
        self.assertNotIn("Implementation prompt:", review.rendered)
        self.assertEqual(review.decision, "CHANGES REQUIRED")

    def test_local_explicit_on_adds_full_prompt_only(self) -> None:
        off = rg.render_local([self.structural], include_fix_prompt=False)
        on = rg.render_local([self.structural], include_fix_prompt=True)
        self.assertIn("Implementation prompt:", on.rendered)
        self.assertEqual(on.findings, off.findings)
        self.assertEqual(on.decision, off.decision)

    def test_one_root_cause_finding_gets_one_prompt(self) -> None:
        review = rg.render_local([self.structural], include_fix_prompt=True)
        self.assertEqual(review.rendered.count("Implementation prompt:"), 1)

    def test_clean_review_never_manufactures_prompt(self) -> None:
        review = rg.render_local([], include_fix_prompt=True)
        self.assertEqual(review.findings, ())
        self.assertEqual(review.decision, "REVIEW CLEAN")
        self.assertNotIn("Implementation prompt:", review.rendered)

    def test_github_uses_concise_direction_without_full_prompt(self) -> None:
        review = rg.render_github([self.structural])
        self.assertIn("Fix:", review.rendered)
        self.assertNotIn("Implementation prompt:", review.rendered)
        self.assertEqual(review.decision, "REQUEST CHANGES")
        self.assertEqual(review.findings, (self.structural,))

    def test_remediation_does_not_change_approve_behavior(self) -> None:
        p2 = rg.Finding("F2", "P2", "Style", "Use the repository convention.")
        self.assertEqual(rg.render_github([p2]).decision, "APPROVE")

    def test_reference_model_has_no_mutation_capability(self) -> None:
        public_names = {name.lower() for name in dir(rg) if not name.startswith("_")}
        for capability in ("edit", "patch", "commit", "push", "branch", "merge"):
            self.assertNotIn(capability, public_names)
