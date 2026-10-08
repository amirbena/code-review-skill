#!/usr/bin/env python3
"""Shared code hygiene review policy (Issue #676).

Contract: shared/policies/code-hygiene.md is the sole owner; review-scope.md
keeps a thin routing section. Prose checks only.
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import REVIEW_SCOPE, GITHUB_REASONING, LOCAL_RUNBOOK
from tests.support.policy_docs import extract_section as _section
from tests.support.policy_docs import load_normalized_text as _text
from tests.support.shared_policy_wiring import SectionForwarding, SectionForwardingMixin

CODE_HYGIENE = REPO_ROOT / "shared/policies/code-hygiene.md"
SEVERITY = REPO_ROOT / "shared/policies/severity.md"


class CodeHygienePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(CODE_HYGIENE)

    def test_scope_is_exactly_two_categories_on_the_changed_delta(self) -> None:
        for phrase in (
            "Exactly two categories",
            "only on the changed delta",
            "issue-tracker reference",
            "variable name",
        ):
            self.assertIn(phrase, self.text)

    def test_candidate_not_proof(self) -> None:
        self.assertIn("only makes a candidate", self.text)
        self.assertIn("never itself a finding", self.text)

    def test_meaningful_references_are_kept(self) -> None:
        for phrase in (
            "active workaround",
            "known limitation",
            "architectural decision",
            "external contract",
            "compatibility constraint",
            "project-required traceability",
        ):
            self.assertIn(phrase, self.text)

    def test_no_tracker_lookup_and_unknown_state_is_not_staleness(self) -> None:
        self.assertIn("local evidence only", self.text)
        self.assertIn("never call an issue-tracker API", self.text)
        self.assertIn("unknown tracker state", self.text)

    def test_naming_exclusions(self) -> None:
        for phrase in (
            "loop indices",
            "short names with clear local meaning",
            "standard domain abbreviations",
            "existing project convention",
            "cannot be improved confidently",
        ):
            self.assertIn(phrase, self.text)

    def test_severity_bounds(self) -> None:
        for phrase in (
            "severity-less",
            "no literal P3 value exists",
            "P2 is the only finding severity",
            "Never P0/P1",
            "never an input to the Decision tally",
            "causal evidence",
            "At most 3 per review",
        ):
            self.assertIn(phrase, self.text)

    def test_severity_definitions_are_unchanged(self) -> None:
        sev = _text(SEVERITY)
        self.assertNotIn("P3", sev)
        self.assertNotIn("hygiene", sev.lower())
        self.assertIn("P2 must not be used for cosmetic noise", sev)

    def test_review_scope_routes_without_restating(self) -> None:
        section = _section(_text(REVIEW_SCOPE), "## Code hygiene review")
        self.assertIn("code-hygiene.md", section)
        self.assertIn("are not restated here", section)
        self.assertNotIn("loop indices", section)
        self.assertNotIn("project-required traceability", section)

    def test_github_reasoning_does_not_restate(self) -> None:
        text = _text(GITHUB_REASONING)
        self.assertNotIn("loop indices", text)

    def test_local_runbook_names_section(self) -> None:
        self.assertIn("Code hygiene review", _text(LOCAL_RUNBOOK))


class CodeHygieneWiredIntoBothSkills(SectionForwardingMixin, unittest.TestCase):
    forwarding = SectionForwarding(
        name="code-hygiene",
        reasoning_heading="## Code Hygiene Review",
        shared_phrase="Code hygiene review",
        index_phrase="code hygiene",
        runbook_heading="Code Hygiene Review",
        local_window_start="Code hygiene review",
    )

    def test_local_report_template_renders_observations(self) -> None:
        text = _text(
            REPO_ROOT / "skills/local-code-review/templates/local-review-report.md"
        )
        self.assertIn("Code hygiene observations", text)
        self.assertIn("code-hygiene.md", text)

    def test_evidence_cross_reference_resolves_to_a_real_heading(self) -> None:
        self.assertIn("## Scope and trigger", CODE_HYGIENE.read_text(encoding="utf-8"))
        self.assertIn(
            'code-hygiene.md), "Scope and trigger"',
            _text(REPO_ROOT / "shared/policies/evidence.md"),
        )

    def test_both_skills_list_the_one_policy(self) -> None:
        for sk in ("local-code-review", "github-pr-review"):
            yaml = (REPO_ROOT / f"skills/{sk}/metadata/skill.yaml").read_text(
                encoding="utf-8"
            )
            self.assertIn("shared/policies/code-hygiene.md", yaml)


if __name__ == "__main__":
    unittest.main()
