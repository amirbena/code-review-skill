#!/usr/bin/env python3
"""Contract coverage for the passive/semi/active publication-mode benchmark
corpus (Issue #316, depends on #314).

The corpus is `runtime_platform/benchmark/reference/publication_mode_fixtures.py`: a
focused, data-driven set of `PublicationModeCase` fixtures pinning every
outcome shape #316's scope requires, executed against the *single*
reference model `tests/reference/review/review_action_authorization.py`
(never a second implementation of the gate) plus
`emit_publication_artifact`, which constructs the actual GitHub-bound
publication artifact (or proves none is constructed) for each case.

This is deliberately **not** a duplicate of
`tests/unit/review/test_review_action_authorization.py`, which already
proves the resolver mechanically, including its own PR #297-style
regression test. That suite is *why* the boundary holds; this corpus is
the declarative, metadata-bearing **benchmark** layer #316 asks for, and
it is the only place that inspects the constructed GitHub-bound
publication artifact itself rather than only the `MutationOutcome` the
resolver returns -- satisfying #316's "Publication-artifact verification
is mandatory" requirement (a caller-facing sentence that nothing was
posted is not sufficient evidence).

Run this module alone to exercise the whole publication-mode corpus
independently of the rest of the benchmark suite:

    python3 -m unittest tests.unit.benchmark.test_publication_mode_corpus
"""

from __future__ import annotations

import inspect
import unittest

from runtime_platform.benchmark.reference import publication_mode_fixtures as pmf
from tests.reference.review import review_action_authorization as raa

MIN_CASES = 15
MAX_CASES = 40


class CorpusPresenceTests(unittest.TestCase):
    def test_corpus_is_non_trivial_and_bounded(self) -> None:
        n = len(pmf.ALL_CASES)
        self.assertGreaterEqual(n, MIN_CASES, "a required case went missing")
        self.assertLessEqual(n, MAX_CASES, "corpus is growing into a bulk library")

    def test_every_case_id_is_unique(self) -> None:
        ids = [c.case_id for c in pmf.ALL_CASES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_corpus_validates_as_a_whole(self) -> None:
        pmf.validate_corpus(pmf.ALL_CASES)  # must not raise

    def test_every_category_has_at_least_one_case(self) -> None:
        for category in pmf.VALID_CATEGORIES:
            with self.subTest(category=category):
                self.assertTrue(pmf.cases_in_category(category), f"no case in category {category!r}")


class MalformedFixtureRejectionTests(unittest.TestCase):
    """validate_case/validate_corpus must fail closed on malformed data."""

    def _valid_kwargs(self) -> dict:
        case = pmf.ALL_CASES[0]
        return dict(
            case_id=case.case_id,
            category=case.category,
            covers=case.covers,
            description=case.description,
            run=case.run,
            expected_resolved_mode=case.expected_resolved_mode,
            expected_event=case.expected_event,
            expected_would_publish=case.expected_would_publish,
            expected_artifact_emitted=case.expected_artifact_emitted,
            expected_artifact_kind=case.expected_artifact_kind,
        )

    def test_empty_case_id_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["case_id"] = "   "
        with self.assertRaises(pmf.PublicationModeFixtureError):
            pmf.validate_case(pmf.PublicationModeCase(**kwargs))

    def test_unknown_category_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["category"] = "not-a-real-category"
        with self.assertRaises(pmf.PublicationModeFixtureError):
            pmf.validate_case(pmf.PublicationModeCase(**kwargs))

    def test_non_callable_run_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["run"] = "not callable"
        with self.assertRaises(pmf.PublicationModeFixtureError):
            pmf.validate_case(pmf.PublicationModeCase(**kwargs))

    def test_artifact_emitted_without_kind_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["expected_artifact_emitted"] = True
        kwargs["expected_artifact_kind"] = None
        with self.assertRaises(pmf.PublicationModeFixtureError):
            pmf.validate_case(pmf.PublicationModeCase(**kwargs))

    def test_artifact_kind_without_emission_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["expected_artifact_emitted"] = False
        kwargs["expected_artifact_kind"] = "formal_review"
        with self.assertRaises(pmf.PublicationModeFixtureError):
            pmf.validate_case(pmf.PublicationModeCase(**kwargs))

    def test_duplicate_case_id_rejected_by_validate_corpus(self) -> None:
        dup = pmf.ALL_CASES[0]
        with self.assertRaises(pmf.PublicationModeFixtureError):
            pmf.validate_corpus((dup, dup))

    def test_empty_corpus_rejected(self) -> None:
        with self.assertRaises(pmf.PublicationModeFixtureError):
            pmf.validate_corpus(())


class ExecuteEveryCaseTests(unittest.TestCase):
    """Runs every case's run() and compares the actual Observed outcome
    against its declared expectation, field by field."""

    def test_every_case_matches_its_declared_expectation(self) -> None:
        for case in pmf.ALL_CASES:
            with self.subTest(case_id=case.case_id):
                observed = case.run()
                self.assertEqual(observed.resolved_mode, case.expected_resolved_mode, case.case_id)
                self.assertEqual(observed.event, case.expected_event, case.case_id)
                self.assertEqual(observed.would_publish, case.expected_would_publish, case.case_id)
                if case.expected_artifact_emitted:
                    self.assertIsNotNone(observed.artifact, f"{case.case_id}: expected an artifact, got None")
                    self.assertEqual(observed.artifact.kind, case.expected_artifact_kind, case.case_id)
                else:
                    self.assertIsNone(
                        observed.artifact,
                        f"{case.case_id}: expected no GitHub-bound artifact, got {observed.artifact!r}",
                    )


# --------------------------------------------------------------------------
# Passive: never publishes
# --------------------------------------------------------------------------
class PassiveNeverPublishesTests(unittest.TestCase):
    def test_no_case_in_the_passive_category_emits_an_artifact(self) -> None:
        for case in pmf.cases_in_category(pmf.CATEGORY_PASSIVE):
            with self.subTest(case_id=case.case_id):
                observed = case.run()
                self.assertIsNone(observed.artifact)
                self.assertEqual(observed.event, raa.GitHubEvent.NONE)
                self.assertEqual(observed.would_publish, raa.GitHubEvent.NONE)


# --------------------------------------------------------------------------
# Semi: computes active-equivalent intent, never publishes
# --------------------------------------------------------------------------
class SemiComputesIntentWithoutMutatingTests(unittest.TestCase):
    def test_semi_cases_never_emit_an_artifact(self) -> None:
        for case in pmf.cases_in_category(pmf.CATEGORY_SEMI):
            with self.subTest(case_id=case.case_id):
                self.assertIsNone(case.run().artifact)

    def test_semi_cases_still_compute_a_nonzero_would_publish_event(self) -> None:
        # This is the specific "semi degrades into passive" regression
        # #316 calls out: a SEMI case that stops computing intent would
        # regress to would_publish == NONE, indistinguishable from PASSIVE.
        for case in pmf.cases_in_category(pmf.CATEGORY_SEMI):
            with self.subTest(case_id=case.case_id):
                self.assertNotEqual(case.run().would_publish, raa.GitHubEvent.NONE)


# --------------------------------------------------------------------------
# Active: publishes the reasoned event; the artifact reaches the boundary
# --------------------------------------------------------------------------
class ActivePublishesAndReachesBoundaryTests(unittest.TestCase):
    def test_active_clean_publishes_approve_artifact(self) -> None:
        cases = [c for c in pmf.cases_in_category(pmf.CATEGORY_ACTIVE) if c.expected_event is raa.GitHubEvent.APPROVE]
        self.assertTrue(cases)
        for case in cases:
            observed = case.run()
            self.assertEqual(observed.artifact.kind, "formal_review")
            self.assertEqual(observed.artifact.event, raa.GitHubEvent.APPROVE)

    def test_active_blocking_publishes_request_changes_artifact(self) -> None:
        cases = [
            c for c in pmf.cases_in_category(pmf.CATEGORY_ACTIVE) if c.expected_event is raa.GitHubEvent.REQUEST_CHANGES
        ]
        self.assertTrue(cases)
        for case in cases:
            observed = case.run()
            self.assertEqual(observed.artifact.kind, "formal_review")
            self.assertEqual(observed.artifact.event, raa.GitHubEvent.REQUEST_CHANGES)

    def test_active_does_not_require_a_second_activation_signal(self) -> None:
        # ActionAuthorizationInput structurally has no field representing a
        # second, independently-sourced authorization signal -- there is
        # nothing to set even if a caller wanted to. This is the same
        # by-construction argument review-action-authorization.md's
        # "Anti-regression guard" makes.
        field_names = {f for f in raa.ActionAuthorizationInput.__dataclass_fields__}
        for fragment in ("activation_phrase", "second_signal", "trusted_authorization", "mutation_authorization"):
            self.assertNotIn(fragment, field_names)


# --------------------------------------------------------------------------
# Canonical PR #297 regression fixture
# --------------------------------------------------------------------------
class Pr297RegressionFixtureTests(unittest.TestCase):
    def _the_fixture(self) -> pmf.PublicationModeCase:
        cases = pmf.cases_in_category(pmf.CATEGORY_REGRESSION_297)
        self.assertEqual(len(cases), 1, "exactly one canonical PR #297 regression fixture is expected")
        return cases[0]

    def test_publication_is_true_and_formal_action_is_approve(self) -> None:
        case = self._the_fixture()
        observed = case.run()
        self.assertEqual(observed.event, raa.GitHubEvent.APPROVE)
        self.assertIsNotNone(observed.artifact)
        self.assertEqual(observed.artifact.kind, "formal_review")
        self.assertEqual(observed.artifact.event, raa.GitHubEvent.APPROVE)

    def test_cannot_regress_to_withheld_for_missing_activation(self) -> None:
        case = self._the_fixture()
        observed = case.run()
        self.assertIsNone(observed.withheld_reason)
        if observed.withheld_reason:
            self.assertNotIn("activation", observed.withheld_reason.lower())


# --------------------------------------------------------------------------
# Mode invariants + semi/active equivalence before side-effect execution
# --------------------------------------------------------------------------
class ModeInvariantTests(unittest.TestCase):
    def test_passive_semi_active_publication_booleans(self) -> None:
        cases = {c.expected_resolved_mode: c for c in pmf.cases_in_category(pmf.CATEGORY_MODE_INVARIANT)}
        self.assertEqual(set(cases), {raa.PublicationMode.PASSIVE, raa.PublicationMode.SEMI, raa.PublicationMode.ACTIVE})

        passive_observed = cases[raa.PublicationMode.PASSIVE].run()
        semi_observed = cases[raa.PublicationMode.SEMI].run()
        active_observed = cases[raa.PublicationMode.ACTIVE].run()

        self.assertIsNone(passive_observed.artifact)
        self.assertIsNone(semi_observed.artifact)
        self.assertIsNotNone(active_observed.artifact)

    def test_semi_and_active_agree_on_the_intended_event_before_publication(self) -> None:
        # Semi/active must preserve equivalent findings/verdict/publication
        # intent before side-effect execution -- their only difference is
        # publication side effects, not review quality (#316 scope).
        cases = {c.expected_resolved_mode: c for c in pmf.cases_in_category(pmf.CATEGORY_MODE_INVARIANT)}
        semi_observed = cases[raa.PublicationMode.SEMI].run()
        active_observed = cases[raa.PublicationMode.ACTIVE].run()
        self.assertEqual(semi_observed.verdict, active_observed.verdict)
        self.assertEqual(semi_observed.would_publish, active_observed.event)


# --------------------------------------------------------------------------
# Self-review boundary, every mode
# --------------------------------------------------------------------------
class SelfReviewBoundaryTests(unittest.TestCase):
    def test_no_self_review_case_ever_produces_a_formal_event(self) -> None:
        for case in pmf.cases_in_category(pmf.CATEGORY_SELF_REVIEW):
            with self.subTest(case_id=case.case_id):
                observed = case.run()
                self.assertEqual(observed.event, raa.GitHubEvent.NONE)
                if observed.artifact is not None:
                    self.assertNotEqual(observed.artifact.kind, "formal_review")

    def test_only_active_self_review_publishes_an_informational_comment(self) -> None:
        for case in pmf.cases_in_category(pmf.CATEGORY_SELF_REVIEW):
            with self.subTest(case_id=case.case_id):
                observed = case.run()
                if case.expected_resolved_mode is raa.PublicationMode.ACTIVE:
                    self.assertIsNotNone(observed.artifact)
                    self.assertEqual(observed.artifact.kind, "informational_comment")
                else:
                    self.assertIsNone(observed.artifact)


# --------------------------------------------------------------------------
# Authority boundary: active mode never widens beyond publication
# --------------------------------------------------------------------------
class ArtifactAuthorityBoundaryTests(unittest.TestCase):
    def test_artifact_dataclass_exposes_only_publication_capabilities(self) -> None:
        for name in pmf.ARTIFACT_FIELD_NAMES:
            for fragment in pmf.PROHIBITED_UNRELATED_MUTATION_FRAGMENTS:
                self.assertNotIn(fragment, name.lower())

    def test_no_public_signature_in_the_fixtures_module_exposes_a_prohibited_capability(self) -> None:
        for name, obj in vars(pmf).items():
            if not callable(obj) or name.startswith("_"):
                continue
            try:
                params = " ".join(inspect.signature(obj).parameters).lower()
            except (TypeError, ValueError):
                continue
            for fragment in pmf.PROHIBITED_UNRELATED_MUTATION_FRAGMENTS:
                self.assertNotIn(fragment, params, f"{name} exposes a prohibited capability: {fragment}")

    def test_active_authority_boundary_cases_construct_only_publication_artifacts(self) -> None:
        for case in pmf.cases_in_category(pmf.CATEGORY_AUTHORITY_BOUNDARY):
            with self.subTest(case_id=case.case_id):
                observed = case.run()
                self.assertIsNotNone(observed.artifact)
                self.assertEqual(observed.artifact.kind, "formal_review")
                # The artifact's own fields are exactly the publication
                # surface -- nothing else was constructed alongside it.
                artifact_fields = {f for f in type(observed.artifact).__dataclass_fields__}
                self.assertEqual(artifact_fields, pmf.ARTIFACT_FIELD_NAMES)

    def test_github_event_enum_carries_no_merge_or_source_mutation_member(self) -> None:
        names = {e.name.lower() for e in raa.GitHubEvent}
        for fragment in pmf.PROHIBITED_UNRELATED_MUTATION_FRAGMENTS:
            self.assertFalse(any(fragment in n for n in names), fragment)


# --------------------------------------------------------------------------
# Invocation phrasing robustness (bounded set, canonical examples only)
# --------------------------------------------------------------------------
class InvocationPhrasingRobustnessTests(unittest.TestCase):
    def test_every_phrasing_case_resolves_to_its_declared_mode(self) -> None:
        cases = pmf.cases_in_category(pmf.CATEGORY_PHRASING)
        self.assertGreaterEqual(len(cases), 4, "should cover at least passive/semi/active phrasings")
        for case in cases:
            with self.subTest(case_id=case.case_id):
                self.assertEqual(case.run().resolved_mode, case.expected_resolved_mode)

    def test_phrasing_set_stays_small_and_bounded(self) -> None:
        # #316 explicitly says this is not a general NL-parser benchmark.
        self.assertLessEqual(len(pmf.cases_in_category(pmf.CATEGORY_PHRASING)), 10)

    def test_active_phrasing_never_depends_on_a_second_magic_phrase(self) -> None:
        active_cases = [
            c for c in pmf.cases_in_category(pmf.CATEGORY_PHRASING) if c.expected_resolved_mode is raa.PublicationMode.ACTIVE
        ]
        self.assertGreaterEqual(len(active_cases), 2)
        for case in active_cases:
            with self.subTest(case_id=case.case_id):
                self.assertEqual(case.run().resolved_mode, raa.PublicationMode.ACTIVE)


# --------------------------------------------------------------------------
# Separation from ordinary finding precision/recall metrics (#41-family)
# --------------------------------------------------------------------------
class SeparateFromFindingPrecisionMetricsTests(unittest.TestCase):
    def test_fixtures_module_touches_no_finding_matching_or_severity_machinery(self) -> None:
        source = inspect.getsource(pmf)
        for forbidden in ("benchmark_match", "benchmark_metrics", "benchmark_severity", "ProducedFinding"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
