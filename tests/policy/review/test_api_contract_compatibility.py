#!/usr/bin/env python3
"""API / contract compatibility review.

Contract: shared/policies/api-contract-compatibility.md, extracted from
review-scope.md (Issue #264, itself the #175/#251 depth owner);
review-scope.md keeps a thin routing paragraph under its own "API /
contract compatibility review" heading (see test_review_scope_core_wiring.py
for the reachability/routing checks that span every extracted pass).
Prose checks only — there is deliberately no second implementation of the
rules (see policies/skill-development-policy.md, "Runbook Design").
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import (
    GITHUB_ACTIVE_RUNBOOK,
    GITHUB_PASSIVE_RUNBOOK,
    GITHUB_REASONING,
    GITHUB_REVIEW_INDEX,
    LOCAL_RUNBOOK,
    PARALLEL_REVIEW,
    REVIEW_SCOPE,
)
from tests.support.policy_docs import extract_section as _section
from tests.support.policy_docs import load_normalized_text as _text

API_CONTRACT_COMPATIBILITY = REPO_ROOT / "shared/policies/api-contract-compatibility.md"


class ApiContractCompatibilitySectionTests(unittest.TestCase):
    """(shared semantics) the API/contract compatibility pass classifies a
    changed repository contract's change shape as compatible / breaking /
    context-dependent, ties the outcome to the existing severity/evidence
    model, and fails closed rather than inventing a breakage claim when the
    consumer surface cannot be established (Issue #175)."""

    def setUp(self) -> None:
        self.section = _section(
            _text(API_CONTRACT_COMPATIBILITY),
            "## API / contract compatibility review",
        )

    def test_recognized_contract_types_are_named(self) -> None:
        for contract_type in (
            "OpenAPI",
            "JSON Schema",
            "protobuf",
            "public API request/response model",
            "event/message schema",
            "configuration contract",
        ):
            self.assertIn(contract_type, self.section)

    def test_recognition_signal_is_never_itself_the_finding(self) -> None:
        self.assertIn("it is never itself the finding", self.section)

    def test_all_change_shapes_are_classified(self) -> None:
        for shape in (
            "Additive, optional",
            "Field or property removed",
            "Optional narrowed to required",
            "Property or field renamed",
            "Enum member removed",
            "Enum member added",
            "Incompatible type change",
        ):
            self.assertIn(shape, self.section)
        self.assertIn("context-dependent", self.section)

    def test_context_dependent_shape_explains_the_ambiguity(self) -> None:
        self.assertIn("ignores unknown members", self.section)
        self.assertIn(
            "exhaustive switch/case or closed-set validation", self.section
        )
        self.assertIn(
            "The diff alone cannot establish which kind of consumer exists",
            self.section,
        )

    def test_fail_closed_rule_never_invents_a_breaking_finding(self) -> None:
        self.assertIn(
            "this pass does not invent a required breaking finding for it",
            self.section,
        )
        self.assertIn(
            "inventing a breakage claim the diff cannot support is worse "
            "than reporting nothing",
            self.section,
        )
        self.assertIn("optional, non-blocking note", self.section)
        self.assertIn("never raises severity or forces", self.section)

    def test_reuses_existing_fail_closed_discipline_not_a_new_standard(self) -> None:
        self.assertIn(
            "Architectural placement and execution-lifecycle fidelity", self.section
        )
        self.assertIn("Semantic change-implication reasoning", self.section)
        self.assertIn(
            "not a new evidence standard invented for this section alone",
            self.section,
        )

    def test_no_new_severity_or_score_and_ties_to_existing_model(self) -> None:
        self.assertIn(
            "adds no new severity, finding category, or probability", self.section
        )
        self.assertIn("evidence.md", self.section)
        self.assertIn("severity.md", self.section)
        self.assertIn("typically P1", self.section)

    def test_design_record_named_not_linked(self) -> None:
        self.assertIn(
            "API/contract compatibility model design record", self.section
        )
        self.assertIn("not linked because", self.section)

    def test_it_is_a_depth_owner_alongside_not_replacing_existing_owners(self) -> None:
        self.assertIn("alongside, not replacing", self.section)
        self.assertIn("Affected-test / test-impact analysis", self.section)
        self.assertIn(
            "Architectural placement and execution-lifecycle fidelity", self.section
        )
        self.assertIn("not a second scope model", self.section)

    def test_never_retrieves_another_repositorys_consumer_code(self) -> None:
        self.assertIn(
            "It never fetches or retrieves another repository's consumer "
            "code to resolve that ambiguity",
            self.section,
        )

    def test_dimension_depth_owner_line_names_this_section(self) -> None:
        text = _text(REVIEW_SCOPE)
        dimension_section = _section(
            text,
            "API / integration contracts",
            "Infrastructure / deployment",
        )
        self.assertIn(
            "API / contract compatibility review", dimension_section
        )


class ApiContractCompatibilityWiredIntoBothSkillsTests(unittest.TestCase):
    def test_github_review_reasoning_forwards_to_the_shared_section(self) -> None:
        text = _text(GITHUB_REASONING)
        self.assertIn("## API / Contract Compatibility Review", text)
        self.assertIn("API / contract compatibility review", text)
        self.assertIn("this PR-specific policy does not restate them", text)

    def test_github_review_index_lists_api_contract_compatibility(self) -> None:
        text = _text(GITHUB_REVIEW_INDEX)
        self.assertIn("api / contract compatibility", text)

    def test_both_github_runbooks_name_the_forwarding_subsection(self) -> None:
        for runbook in (GITHUB_ACTIVE_RUNBOOK, GITHUB_PASSIVE_RUNBOOK):
            text = _text(runbook)
            self.assertIn("API / Contract Compatibility Review", text)

    def test_local_runbook_marks_the_section_signal_triggered(self) -> None:
        text = _text(LOCAL_RUNBOOK)
        window = _section(
            text,
            "API / contract compatibility review",
            "Classify findings per",
        )
        self.assertIn(
            "signal-triggered per that policy's own gating conditions", window
        )
        self.assertIn("not applied", window)
        self.assertIn("unconditionally to every diff", window)

    def test_parallel_review_cites_the_shared_section(self) -> None:
        text = _text(PARALLEL_REVIEW)
        self.assertIn("API / contract compatibility review", text)


if __name__ == "__main__":
    unittest.main()
