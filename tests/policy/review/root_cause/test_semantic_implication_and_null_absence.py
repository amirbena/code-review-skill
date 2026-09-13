#!/usr/bin/env python3
"""Semantic change-implication reasoning and null-like absence-risk review.

Contract: shared/policies/review-scope.md ("Semantic change-implication
reasoning") and shared/policies/null-absence-risk.md, extracted from
review-scope.md (Issue #264); review-scope.md keeps a thin routing
paragraph under its own "Null-like absence-risk review" heading (see
test_review_scope_core_wiring.py for the reachability/routing checks that
span every extracted pass).
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

NULL_ABSENCE_RISK = REPO_ROOT / "shared/policies/null-absence-risk.md"


class SemanticImplicationSectionTests(unittest.TestCase):
    """(shared semantics) the base semantic change-implication pass detects
    materially implicated system dimensions and performs the minimum
    bounded reasoning itself, never a mandatory eight-dimension checklist,
    and is unconditional with respect to any domain-specific deepening
    capability — such a capability may add depth but can never gate
    whether a dimension is considered at all. This is Tier-3-neutral: it
    does not say how a deeper capability is selected, activated, or
    composed (that is #82's scope)."""

    def setUp(self) -> None:
        self.section = _section(
            _text(REVIEW_SCOPE),
            "## Semantic change-implication reasoning",
            "## Existing behavior ownership",
        )

    def test_it_performs_base_reasoning_itself_not_only_routing(self) -> None:
        self.assertIn(
            "it performs the minimum bounded reasoning itself — it", self.section
        )
        self.assertIn("is not solely a router", self.section)
        self.assertIn(
            "none of them may gate, weaken, narrow, or replace this base obligation",
            self.section,
        )

    def test_base_reasoning_is_unconditional_on_deeper_capabilities(self) -> None:
        self.assertIn(
            "Base semantic reasoning is unconditional with respect to "
            "additional domain-specific depth",
            self.section,
        )
        self.assertIn(
            "it never determines whether that dimension is considered at all",
            self.section,
        )
        self.assertIn(
            "How a deeper capability is selected, activated, or composed with "
            "the base review is owned by \"Domain-specific deepening pass\" "
            "below, not by this section",
            self.section,
        )
        for stale in ("opt-in specialist profile", "profile is selected"):
            self.assertNotIn(stale, self.section)

    def test_taxonomy_is_not_mutually_exclusive(self) -> None:
        self.assertIn("not a mutually-exclusive classification", self.section)
        self.assertIn(
            "may materially implicate several dimensions at once", self.section
        )

    def test_no_signal_dimension_is_not_analysed_and_emits_no_output(self) -> None:
        self.assertIn(
            "is not analysed and produces no output, including no not-applicable "
            "record",
            self.section,
        )
        self.assertIn("deliberately not an eight-dimension checklist", self.section)

    def test_all_eight_canonical_dimensions_are_present_with_depth_owner(self) -> None:
        for dimension in (
            "User-facing / client behavior",
            "Concurrency / distributed-system semantics",
            "Data / persistence",
            "API / integration contracts",
            "Infrastructure / deployment",
            "Security / trust boundaries",
            "Operability / production-readiness",
            "Performance / scale",
        ):
            self.assertIn(dimension, self.section)
        self.assertEqual(self.section.count("Depth owner:"), 8)

    def test_one_dimension_has_no_dedicated_owner_yet(self) -> None:
        self.assertEqual(
            self.section.count(
                "no dedicated owner contract exists yet in this repository"
            ),
            1,
        )

    def test_infrastructure_dimension_depth_owner_names_dependency_supply_chain(
        self,
    ) -> None:
        self.assertIn(
            'Depth owner: "Dependency / supply-chain deepening review" below',
            self.section,
        )

    def test_worked_multi_dimension_example_names_four_implicated_dimensions(self) -> None:
        self.assertIn("Worked example", self.section)
        self.assertIn("webhook", self.section)
        self.assertIn(
            "does not implicate concurrency, infrastructure, or performance/scale "
            "unless",
            self.section,
        )

    def test_evidence_is_semantic_not_structural(self) -> None:
        self.assertIn(
            "File type, framework, path, and language are evidence that a dimension",
            self.section,
        )
        self.assertIn("never solely authoritative", self.section)
        for example in (
            "Shared-state read→decide→write",
            "User-controlled value reaching rendered output",
            "Schema or persisted-state change",
            "Deployment or configuration change",
        ):
            self.assertIn(example, self.section)

    def test_bounded_expansion_reuses_architectural_placement_model(self) -> None:
        self.assertIn(
            "the same minimum-context-first, one-ring-at-a-time model and stop "
            'conditions already defined under "Architectural placement and '
            'execution-lifecycle fidelity"',
            self.section,
        )
        self.assertIn("insufficient evidence", self.section.lower())
        self.assertIn("introduces no second scope or evidence model", self.section)


class SemanticImplicationWiredIntoBothSkillsTests(unittest.TestCase):
    def test_github_review_reasoning_forwards_to_the_shared_section(self) -> None:
        text = _text(GITHUB_REASONING)
        self.assertIn("## Semantic Implication Review", text)
        self.assertIn("Semantic change-implication reasoning", text)
        self.assertIn("does not restate them", text)

    def test_github_review_index_lists_semantic_implication_reasoning(self) -> None:
        text = _text(GITHUB_REVIEW_INDEX)
        self.assertIn("semantic implication", text)

    def test_semantic_implication_runs_before_other_reasoning_passes_in_github_reasoning(
        self,
    ) -> None:
        text = _text(GITHUB_REASONING)
        semantic_idx = text.index("## Semantic Implication Review")
        cohort_idx = text.index("## Logical Cohort Review")
        self.assertLess(semantic_idx, cohort_idx)

    def test_both_github_runbooks_apply_semantic_implication_first(self) -> None:
        for runbook in (GITHUB_ACTIVE_RUNBOOK, GITHUB_PASSIVE_RUNBOOK):
            text = _text(runbook)
            self.assertIn("Semantic Implication Review", text)
            semantic_idx = text.index("Semantic Implication Review")
            cohort_idx = text.index("Logical Cohort Review")
            self.assertLess(semantic_idx, cohort_idx)

    def test_local_runbook_marks_the_section_signal_triggered(self) -> None:
        text = _text(LOCAL_RUNBOOK)
        window = _section(
            text,
            "Semantic change-implication reasoning",
            "Classify findings per",
        )
        self.assertIn(
            "signal-triggered per that policy's own gating conditions", window
        )
        self.assertIn("not applied", window)
        self.assertIn("unconditionally to every diff", window)


class NullLikeAbsenceRiskSectionTests(unittest.TestCase):
    """(shared semantics) the null-like absence-risk pass is a
    cross-language semantic rule — never a regex or keyword match — that
    surfaces only credible, evidence-backed absence risk and suppresses
    theoretical nullability already made safe by a guard, the type
    system, a framework/contract guarantee, or upstream validation. It
    introduces no new severity or finding category (Issue #121)."""

    def setUp(self) -> None:
        self.section = _section(
            _text(NULL_ABSENCE_RISK),
            "## Null-like absence-risk review",
        )

    def test_it_is_a_semantic_rule_not_a_keyword_or_regex_match(self) -> None:
        self.assertIn(
            "a semantic rule keyed to the reviewed language's nullability "
            "model, never a regex or keyword match",
            self.section,
        )
        self.assertIn(
            "not whether a variable is named value or a method is named get",
            self.section,
        )

    def test_it_applies_identically_across_representative_languages(self) -> None:
        for language in ("Java/Kotlin", "JavaScript/TypeScript", "C#", "Python", "Go"):
            self.assertIn(language, self.section)

    def test_theoretical_nullability_is_not_reported(self) -> None:
        self.assertIn("purely theoretical nullability", self.section)
        self.assertIn("is not reported", self.section)

    def test_introduces_no_new_severity_or_finding_category(self) -> None:
        self.assertIn("adds no new finding category", self.section)
        self.assertIn("classified under", self.section)
        self.assertIn("severity.md", self.section)
        self.assertIn("evidence.md", self.section)
        self.assertIn(
            "carries no dedicated severity merely because a nullable "
            "value is present",
            self.section,
        )

    def test_credible_absence_paths_are_illustrative_not_a_keyword_list(self) -> None:
        self.assertIn("Credible absence paths", self.section)
        self.assertIn("not an exhaustive keyword list", self.section)
        for pattern in (
            "optional or lookup result",
            "nullable return value",
            "destructuring",
            "nullable collection element",
        ):
            self.assertIn(pattern, self.section)

    def test_interoperability_and_escape_hatch_boundaries_are_named(self) -> None:
        self.assertIn("Interoperability and escape-hatch boundaries", self.section)
        for boundary in (
            "Kotlin platform type",
            "non-null assertion",
            "null-forgiving",
            "unsafe/cgo/reflection",
            "Deserialization".lower(),
        ):
            self.assertIn(boundary.lower(), self.section.lower())

    def test_suppression_rule_requires_a_reachable_failure_path(self) -> None:
        self.assertIn("Suppression", self.section)
        self.assertIn(
            "whether *this* code path can", self.section
        )
        self.assertIn(
            "not whether the value's declared type permits absence in "
            "the abstract",
            self.section,
        )
        for safe_source in (
            "a guard, early return, assertion",
            "framework or contract guarantee",
            "demonstrable upstream validation",
        ):
            self.assertIn(safe_source, self.section)


class NullLikeAbsenceRiskWiredIntoBothSkillsTests(unittest.TestCase):
    def test_github_review_reasoning_forwards_to_the_shared_section(self) -> None:
        text = _text(GITHUB_REASONING)
        self.assertIn("## Null-Like Absence-Risk Review", text)
        self.assertIn("Null-like absence-risk review", text)
        self.assertIn("does not restate them", text)

    def test_github_review_index_lists_null_like_absence_risk(self) -> None:
        text = _text(GITHUB_REVIEW_INDEX)
        self.assertIn("null-like absence risk", text)

    def test_both_github_runbooks_apply_null_like_absence_risk_review(self) -> None:
        for runbook in (GITHUB_ACTIVE_RUNBOOK, GITHUB_PASSIVE_RUNBOOK):
            text = _text(runbook)
            self.assertIn("Null-Like Absence-Risk Review", text)

    def test_local_runbook_marks_the_section_signal_triggered(self) -> None:
        text = _text(LOCAL_RUNBOOK)
        window = _section(
            text,
            "Null-like absence-risk review",
            "Classify findings per",
        )
        self.assertIn(
            "signal-triggered per that policy's own gating conditions", window
        )
        self.assertIn("not applied", window)
        self.assertIn("unconditionally to every diff", window)

    def test_parallel_review_cites_the_shared_section(self) -> None:
        text = _text(PARALLEL_REVIEW)
        self.assertIn("Null-like absence-risk review", text)


if __name__ == "__main__":
    unittest.main()
