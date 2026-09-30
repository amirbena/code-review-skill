#!/usr/bin/env python3
"""Deterministic benchmark for the human reasoning checkpoint (Issue #567,
Epic #564; proves the implementation delivered by #566).

Every test loads the single reference fixture module
`runtime_platform/benchmark/reference/reasoning_checkpoint_fixtures.py` and is
independent of the `benchmark-case/v2` runner/matcher/metrics stack. The
corpus and its mechanism choice are documented in
docs/benchmark/corpus/reasoning-checkpoint/README.md.
"""

from __future__ import annotations

import unittest

from runtime_platform.benchmark.reference import reasoning_checkpoint_fixtures as fx
from runtime_platform.benchmark.reference.reasoning_checkpoint_fixtures import (
    ALL_CASES,
    REQUIRED_COVERAGE_TAGS,
    SURFACES,
    cases_covering,
    cases_in_category,
)
from tests.reference.review import decision_semantics as ds


def _active() -> tuple[fx.ReasoningCheckpointCase, ...]:
    return tuple(c for c in ALL_CASES if c.expected_active)


def _inactive() -> tuple[fx.ReasoningCheckpointCase, ...]:
    return tuple(c for c in ALL_CASES if not c.expected_active)


class CoverageCompletenessTests(unittest.TestCase):
    def test_every_required_tag_is_covered(self) -> None:
        covered = frozenset().union(*(c.covers for c in ALL_CASES))
        self.assertEqual(REQUIRED_COVERAGE_TAGS - covered, frozenset())

    def test_no_unknown_tags(self) -> None:
        declared = frozenset().union(*(c.covers for c in ALL_CASES))
        self.assertEqual(declared - REQUIRED_COVERAGE_TAGS, frozenset())

    def test_corpus_validates_and_ids_are_unique(self) -> None:
        fx.validate_corpus(ALL_CASES)
        ids = [c.case_id for c in ALL_CASES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_category_is_populated(self) -> None:
        for category in fx.VALID_CATEGORIES:
            with self.subTest(category=category):
                self.assertTrue(cases_in_category(category))

    def test_malformed_fixture_is_rejected(self) -> None:
        bad = fx.ReasoningCheckpointCase(
            case_id="x", category="nope", covers=frozenset(), description="d", change_kind="ordinary"
        )
        with self.assertRaises(fx.ReasoningCheckpointFixtureError):
            fx.validate_case(bad)
        inconsistent_r = fx.ReasoningCheckpointCase(
            case_id="y", category=fx.CATEGORY_INERT, covers=frozenset(), description="d",
            change_kind="ordinary", runtime_dependent=True,
        )
        with self.assertRaises(fx.ReasoningCheckpointFixtureError):
            fx.validate_case(inconsistent_r)


class ActivationTests(unittest.TestCase):
    def test_reference_activation_matches_every_expectation(self) -> None:
        for case in ALL_CASES:
            with self.subTest(case=case.case_id):
                self.assertEqual(fx.evaluate_activation(case), case.expected_active)

    def test_bug_fix_activates_investigation_questions_first(self) -> None:
        for case in cases_covering("bug-fix-investigation-activates"):
            with self.subTest(case=case.case_id):
                self.assertTrue(fx.investigation_facet_active(case))
                questions = fx.emitted_questions(case)
                self.assertTrue(questions)
                self.assertEqual(questions[0].facet, fx.FACET_INVESTIGATION)

    def test_architecture_change_activates_design_question_with_placement_evidence(self) -> None:
        for case in cases_covering("architecture-lifecycle-activates"):
            with self.subTest(case=case.case_id):
                self.assertTrue(fx.design_facet_active(case))
                design = [q for q in fx.emitted_questions(case) if q.facet == fx.FACET_DESIGN]
                self.assertTrue(design)
                for q in design:
                    self.assertIn(q.anchor_kind, {fx.ANCHOR_PLACEMENT_RING, fx.ANCHOR_INSPECTED_PEER})

    def test_runtime_dependent_implies_active_investigation_facet(self) -> None:
        for case in ALL_CASES:
            if case.runtime_dependent:
                with self.subTest(case=case.case_id):
                    self.assertTrue(fx.investigation_facet_active(case))


class InertTests(unittest.TestCase):
    def test_trivial_change_renders_no_section_on_every_surface(self) -> None:
        for case in cases_covering("trivial-change-absent"):
            for surface in SURFACES:
                with self.subTest(case=case.case_id, surface=surface):
                    body = fx.render_review(case, surface).body
                    self.assertNotIn("Reasoning check", body)
                    self.assertNotIn(fx.SECTION_LEAD_IN, body)

    def test_inert_review_is_byte_identical_to_one_without_the_capability(self) -> None:
        for case in _inactive():
            for surface in SURFACES:
                with self.subTest(case=case.case_id, surface=surface):
                    self.assertEqual(
                        fx.render_review(case, surface).body,
                        fx.render_review(case, surface, checkpoint=False).body,
                    )

    def test_weak_signals_never_activate_alone(self) -> None:
        for case in _inactive():
            if case.signals and case.signals <= fx.NON_SIGNALS:
                with self.subTest(case=case.case_id):
                    self.assertFalse(fx.evaluate_activation(case))

    def test_inert_under_incomplete_coverage_and_unresolved_jira(self) -> None:
        cases = cases_covering("inert-under-incomplete-or-unresolved")
        self.assertTrue(any(c.coverage_incomplete for c in cases))
        self.assertTrue(any(c.jira_unresolved for c in cases))
        for case in cases:
            with self.subTest(case=case.case_id):
                # Full activation evidence is present; only the gate is inert.
                self.assertTrue(fx.investigation_facet_active(case))
                self.assertFalse(fx.evaluate_activation(case))


class InsufficientEvidenceTests(unittest.TestCase):
    def test_no_anchorable_question_fails_closed_without_placeholder(self) -> None:
        for case in cases_covering("insufficient-evidence-no-invention"):
            if not case.expected_active:
                with self.subTest(case=case.case_id):
                    body = fx.render_review(case, "local").body
                    self.assertNotIn(fx.SECTION_HEADING, body)
                    lowered = body.lower()
                    for phrase in fx.PLACEHOLDER_PHRASES:
                        self.assertNotIn(phrase, lowered)

    def test_restated_finding_question_is_dropped(self) -> None:
        case = next(c for c in ALL_CASES if c.case_id == "candidate-restating-a-finding-is-dropped")
        self.assertEqual(fx.select_questions(case.candidates), ())
        self.assertNotIn(fx.SECTION_HEADING, fx.render_review(case, "local").body)

    def test_unverifiable_hypothesis_yields_one_question_asking_for_evidence(self) -> None:
        case = next(c for c in ALL_CASES if c.case_id == "unverifiable-hypothesis-single-question")
        questions = fx.emitted_questions(case)
        self.assertEqual(len(questions), 1)
        self.assertIn("cannot be validated from the available evidence", questions[0].text)

    def test_insufficient_placement_question_names_no_invented_owner(self) -> None:
        case = next(c for c in ALL_CASES if c.case_id.startswith("insufficient-evidence-boundary-move"))
        (question,) = fx.emitted_questions(case)
        self.assertIn("no owning abstraction could be established", question.text)

    def test_candidate_without_anchor_is_not_selected(self) -> None:
        unanchored = fx.Question("Is this right?", fx.FACET_INVESTIGATION, fx.ANCHOR_CHAIN_LINK, " ")
        self.assertEqual(fx.select_questions((unanchored,)), ())


class QuestionContractTests(unittest.TestCase):
    def test_every_emitted_question_is_sound(self) -> None:
        for case in _active():
            for q in fx.emitted_questions(case):
                with self.subTest(case=case.case_id, question=q.text[:40]):
                    self.assertEqual(fx.question_violations(q, case), [])

    def test_violation_detector_catches_each_forbidden_shape(self) -> None:
        case = _active()[0]
        bad = {
            "P1 label": "Is this the P1 cause?",
            "decision token": "Does CHANGES REQUIRED apply here?",
            "finding id": "Does F1 cover this path?",
            "generic": "Did you test this?",
            "access claim": "The logs show the retry storm, is that right?",
            "not a question": "Explain the root cause.",
            "two sentences": "Is it a? Is it b?",
        }
        for name, text in bad.items():
            with self.subTest(shape=name):
                q = fx.Question(text, fx.FACET_INVESTIGATION, fx.ANCHOR_CHAIN_LINK, "ref")
                self.assertTrue(fx.question_violations(q, case), name)

    def test_provenance_tag_must_appear_when_declared(self) -> None:
        case = _active()[0]
        q = fx.Question("Was it seen?", fx.FACET_INVESTIGATION, fx.ANCHOR_CHAIN_LINK, "r", fx.PROV_REPORTED)
        self.assertIn("provenance tag not present in the question text", fx.question_violations(q, case))

    def test_count_is_within_bounds_and_ordered(self) -> None:
        for case in _active():
            with self.subTest(case=case.case_id):
                questions = fx.emitted_questions(case)
                self.assertGreaterEqual(len(questions), fx.MIN_QUESTIONS)
                self.assertLessEqual(len(questions), fx.MAX_QUESTIONS)
                facets = [q.facet for q in questions]
                self.assertEqual(facets, sorted(facets, key=lambda f: 0 if f == fx.FACET_INVESTIGATION else 1))


class RuntimeBoundaryTests(unittest.TestCase):
    def test_provenance_classes_stay_distinct(self) -> None:
        case = next(c for c in ALL_CASES if c.case_id == "bug-fix-three-provenance-classes-distinct")
        self.assertEqual({i.status for i in case.evidence_items}, fx.VALID_PROVENANCE)
        questions = fx.emitted_questions(case)
        self.assertEqual({q.provenance for q in questions}, fx.VALID_PROVENANCE)
        for q in questions:
            other = fx.VALID_PROVENANCE - {q.provenance}
            for label in other:
                with self.subTest(question=q.text[:30], other=label):
                    self.assertNotIn(label, q.text.lower())

    def test_unavailable_evidence_is_asked_about_never_described(self) -> None:
        for case in cases_covering("runtime-boundary-asks-not-assumes"):
            unavailable = {i.name for i in case.evidence_items if i.status == fx.PROV_UNAVAILABLE}
            for q in fx.emitted_questions(case):
                if q.provenance == fx.PROV_UNAVAILABLE:
                    with self.subTest(case=case.case_id):
                        self.assertTrue(q.text.endswith("?"))
                        self.assertTrue(unavailable)
                        self.assertEqual(fx.question_violations(q, case), [])

    def test_no_case_claims_runtime_access_or_contents(self) -> None:
        for case in _active():
            for surface in SURFACES:
                body = fx.render_review(case, surface).body.lower()
                for pattern in fx.ACCESS_CLAIM_PATTERNS:
                    with self.subTest(case=case.case_id, surface=surface, pattern=pattern):
                        self.assertIsNone(__import__("re").search(pattern, body))

    def test_readiness_language_under_condition_r(self) -> None:
        r_cases = [c for c in _active() if c.runtime_dependent]
        self.assertTrue(r_cases)
        for case in r_cases:
            for surface in SURFACES:
                body = fx.render_review(case, surface).body
                lowered = body.lower()
                with self.subTest(case=case.case_id, surface=surface):
                    for phrase in fx.FORBIDDEN_READINESS_PHRASES:
                        self.assertNotIn(phrase, lowered)
                    self.assertIn(fx.SCOPED_OPENING_ASSESSMENT, body)
                    self.assertIn(fx.SECTION_HEADING, body)

    def test_opening_assessment_unscoped_when_r_does_not_hold(self) -> None:
        for case in _active():
            if not case.runtime_dependent:
                with self.subTest(case=case.case_id):
                    body = fx.render_review(case, "local").body
                    self.assertNotIn(fx.SCOPED_OPENING_ASSESSMENT, body)
                    for phrase in fx.FORBIDDEN_READINESS_PHRASES:
                        self.assertNotIn(phrase, body.lower())


class QuestionsAreNotFindingsTests(unittest.TestCase):
    def test_section_carries_no_severity_id_or_decision_token(self) -> None:
        for case in _active():
            for surface in SURFACES:
                questions = fx.extract_section(fx.render_review(case, surface).body)
                with self.subTest(case=case.case_id, surface=surface):
                    self.assertIsNotNone(questions)
                    for text in questions:
                        self.assertIsNone(fx._SEVERITY_LABEL.search(text))
                        self.assertIsNone(fx._DECISION_TOKEN.search(text))
                        self.assertIsNone(fx._FINDING_ID.search(text))

    def test_questions_never_appear_inline_or_in_structured_result(self) -> None:
        for case in _active():
            questions = fx.emitted_questions(case)
            structured = repr(fx.render_structured_result(case))
            for surface in SURFACES:
                rendered = fx.render_review(case, surface)
                for q in questions:
                    with self.subTest(case=case.case_id, surface=surface):
                        for comment in rendered.inline_comments:
                            self.assertNotIn(q.text, comment)
                        self.assertNotIn(q.text, structured)
            self.assertNotIn("reasoning", structured.lower())

    def test_clean_p2_and_blocking_reviews_all_carry_the_section(self) -> None:
        clean = cases_covering("clean-review-checkpoint-appears")
        p2 = cases_covering("p2-only-non-blocking-checkpoint")
        blocking = cases_covering("findings-present-questions-not-findings")
        self.assertTrue(any(c.decision is ds.Decision.CLEAN and not c.findings for c in clean))
        self.assertTrue(any(c.decision is ds.Decision.CLEAN and c.findings for c in p2))
        self.assertTrue(any(c.decision is ds.Decision.CHANGES_REQUIRED for c in blocking))
        for case in (*clean, *p2, *blocking):
            if case.expected_active:
                with self.subTest(case=case.case_id):
                    self.assertIn(fx.SECTION_HEADING, fx.render_review(case, "local").body)

    def test_p2_only_review_stays_clean_with_section_present(self) -> None:
        case = next(c for c in ALL_CASES if c.case_id == "analogue-deviation-concrete-consequence")
        body = fx.render_review(case, "local").body
        self.assertIn("REVIEW CLEAN", body)
        self.assertNotIn("CHANGES REQUIRED", body)
        self.assertIn(fx.SECTION_HEADING, body)


class InvarianceTests(unittest.TestCase):
    def test_decision_and_findings_identical_with_checkpoint_on_or_off(self) -> None:
        for case in cases_covering("decision-severity-invariance"):
            for surface in SURFACES:
                for human in (False, True):
                    on = fx.render_review(case, surface, human_review_output=human)
                    off = fx.render_review(case, surface, human_review_output=human, checkpoint=False)
                    with self.subTest(case=case.case_id, surface=surface, human=human):
                        self.assertEqual(self._decision_lines(on.body), self._decision_lines(off.body))
                        self.assertEqual(self._finding_lines(on.body), self._finding_lines(off.body))
                        self.assertEqual(on.inline_comments, off.inline_comments)
                        self.assertEqual(
                            ds.derive_decision(case.findings).value, case.decision.value
                        )

    def test_structured_result_is_independent_of_the_checkpoint(self) -> None:
        for case in _active():
            with self.subTest(case=case.case_id):
                result = fx.render_structured_result(case)
                self.assertEqual(set(result), {"findings", "coverage", "decision", "summary"})
                self.assertEqual(result["decision"], case.decision.value)

    def test_removing_the_section_restores_the_suppressed_render(self) -> None:
        for case in _active():
            if case.runtime_dependent:
                continue  # the scoped opening sentence is the one sanctioned difference
            for surface in SURFACES:
                on = fx.render_review(case, surface).body
                off = fx.render_review(case, surface, checkpoint=False).body
                with self.subTest(case=case.case_id, surface=surface):
                    self.assertEqual(fx.strip_section(on), off)

    def test_runtime_dependent_difference_is_only_the_scoped_sentence_and_section(self) -> None:
        for case in _active():
            if not case.runtime_dependent:
                continue
            on = fx.render_review(case, "local").body
            off = fx.render_review(case, "local", checkpoint=False).body
            restored = fx.strip_section(on).replace(fx.SCOPED_OPENING_ASSESSMENT, fx._opening_assessment(case, False))
            with self.subTest(case=case.case_id):
                self.assertEqual(restored, off)

    @staticmethod
    def _decision_lines(body: str) -> list[str]:
        return [ln for ln in body.splitlines() if ln.startswith("**Result:") or ln in ("**REVIEW CLEAN**", "**CHANGES REQUIRED**")]

    @staticmethod
    def _finding_lines(body: str) -> list[str]:
        return [ln for ln in body.splitlines() if fx._SEVERITY_LABEL.search(ln)]


class RenderingParityTests(unittest.TestCase):
    def test_section_text_count_and_anchors_identical_across_surfaces_and_modes(self) -> None:
        for case in cases_covering("rendering-local-and-github"):
            if not case.expected_active:
                continue
            expected = tuple(q.text for q in fx.emitted_questions(case))
            for surface in SURFACES:
                for human in (False, True):
                    with self.subTest(case=case.case_id, surface=surface, human=human):
                        rendered = fx.render_review(case, surface, human_review_output=human)
                        self.assertEqual(fx.extract_section(rendered.body), expected)

    def test_placement_after_decision_and_before_metadata(self) -> None:
        for case in _active():
            for surface in SURFACES:
                body = fx.render_review(case, surface).body
                with self.subTest(case=case.case_id, surface=surface):
                    decision = body.index("### Decision")
                    section = body.index(fx.SECTION_HEADING)
                    metadata = body.index("### Review Metadata")
                    self.assertLess(decision, section)
                    self.assertLess(section, metadata)
                    if surface == "github-self-review":
                        self.assertLess(body.index("Self-review:"), section)

    def test_heading_override_is_the_only_surface_difference_in_the_section(self) -> None:
        case = next(c for c in ALL_CASES if c.case_id == "bug-fix-bug-description-runtime-dependent")
        local = fx.render_review(case, "local").body
        github = fx.render_review(case, "github-active").body
        self.assertTrue(local.startswith("## Code Review"))
        self.assertTrue(github.startswith("## Review Summary"))
        self.assertEqual(fx.extract_section(local), fx.extract_section(github))


class NoiseAndBoundTests(unittest.TestCase):
    def test_ceiling_holds_when_more_than_four_candidates_are_anchored(self) -> None:
        for case in cases_covering("question-count-ceiling"):
            with self.subTest(case=case.case_id):
                self.assertGreater(len(case.candidates), fx.MAX_QUESTIONS)
                emitted = fx.emitted_questions(case)
                self.assertEqual(len(emitted), fx.MAX_QUESTIONS)
                self.assertEqual(
                    [q.facet for q in emitted[:3]], [fx.FACET_INVESTIGATION] * 3
                )
                for surface in SURFACES:
                    self.assertEqual(len(fx.extract_section(fx.render_review(case, surface).body)), fx.MAX_QUESTIONS)

    def test_ordinary_reviews_never_carry_a_checkpoint(self) -> None:
        ordinary = cases_covering("ordinary-reviews-no-checkpoint")
        self.assertGreaterEqual(len(ordinary), 10)
        for case in ordinary:
            for surface in SURFACES:
                for human in (False, True):
                    with self.subTest(case=case.case_id, surface=surface, human=human):
                        body = fx.render_review(case, surface, human_review_output=human).body
                        self.assertIsNone(fx.extract_section(body))
                        self.assertNotIn(fx.SECTION_LEAD_IN, body)

    def test_activation_rate_is_a_minority_of_the_corpus(self) -> None:
        # Guards drift toward a generic questionnaire: most cases are inert.
        self.assertLess(len(_active()), len(_inactive()))


if __name__ == "__main__":
    unittest.main()
