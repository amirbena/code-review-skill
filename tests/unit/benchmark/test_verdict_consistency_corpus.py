#!/usr/bin/env python3
"""Contract coverage for the verdict-consistency benchmark corpus (Issue
#378, depends on #377).

The corpus is `runtime_platform/benchmark/reference/verdict_consistency_fixtures.py`:
a focused, data-driven set of `VerdictConsistencyCase` fixtures that
deliberately drift the about-to-be-rendered/submitted decision signal away
from an already-finalized mechanical decision
(`tests/reference/review/decision_semantics.py`) and exercise the real
comparator (`tests/reference/review/verdict_consistency.py`) through the
runbook-shaped `render_or_withhold`/`publish_or_withhold` wrappers, at all
four reconciliation points `shared/policies/verdict-consistency.md` names.

This is deliberately **not** a duplicate of
`tests/unit/review/test_verdict_consistency.py`, which already proves the
raw comparator functions in isolation. That suite is *why* the boundary
holds; this corpus is the declarative, metadata-bearing **benchmark**
layer #378 asks for, and it is the only place that inspects the actual
withheld-or-emitted *artifact* a reconciliation point would construct,
proving withhold-and-report rather than silent skip or self-correction.
It is also distinct from #350's normal-path proof: every case here starts
from a finalized decision and then deliberately disagrees with it,
proving enforcement, not correct derivation.

Run this module alone to exercise the whole verdict-consistency corpus
independently of the rest of the benchmark suite:

    python3 -m unittest tests.unit.benchmark.test_verdict_consistency_corpus
"""

from __future__ import annotations

import inspect
import unittest

from runtime_platform.benchmark.reference import verdict_consistency_fixtures as vcf
from tests.reference.review import verdict_consistency as vc

MIN_CASES = 10
MAX_CASES = 30


class CorpusPresenceTests(unittest.TestCase):
    def test_corpus_is_non_trivial_and_bounded(self) -> None:
        n = len(vcf.ALL_CASES)
        self.assertGreaterEqual(n, MIN_CASES, "a required case went missing")
        self.assertLessEqual(n, MAX_CASES, "corpus is growing into a bulk library")

    def test_every_case_id_is_unique(self) -> None:
        ids = [c.case_id for c in vcf.ALL_CASES]
        self.assertEqual(len(ids), len(set(ids)))

    def test_corpus_validates_as_a_whole(self) -> None:
        vcf.validate_corpus(vcf.ALL_CASES)  # must not raise

    def test_every_category_has_at_least_one_case(self) -> None:
        for category in vcf.VALID_CATEGORIES:
            with self.subTest(category=category):
                self.assertTrue(vcf.cases_in_category(category), f"no case in category {category!r}")


class MalformedFixtureRejectionTests(unittest.TestCase):
    """validate_case/validate_corpus must fail closed on malformed data."""

    def _valid_kwargs(self) -> dict:
        case = vcf.ALL_CASES[0]
        return dict(
            case_id=case.case_id,
            category=case.category,
            covers=case.covers,
            description=case.description,
            run=case.run,
            expect_withheld=case.expect_withheld,
        )

    def test_empty_case_id_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["case_id"] = "   "
        with self.assertRaises(vcf.VerdictConsistencyFixtureError):
            vcf.validate_case(vcf.VerdictConsistencyCase(**kwargs))

    def test_unknown_category_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["category"] = "not-a-real-category"
        with self.assertRaises(vcf.VerdictConsistencyFixtureError):
            vcf.validate_case(vcf.VerdictConsistencyCase(**kwargs))

    def test_non_callable_run_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["run"] = "not callable"
        with self.assertRaises(vcf.VerdictConsistencyFixtureError):
            vcf.validate_case(vcf.VerdictConsistencyCase(**kwargs))

    def test_empty_description_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["description"] = "   "
        with self.assertRaises(vcf.VerdictConsistencyFixtureError):
            vcf.validate_case(vcf.VerdictConsistencyCase(**kwargs))

    def test_non_bool_expect_withheld_rejected(self) -> None:
        kwargs = self._valid_kwargs()
        kwargs["expect_withheld"] = "yes"
        with self.assertRaises(vcf.VerdictConsistencyFixtureError):
            vcf.validate_case(vcf.VerdictConsistencyCase(**kwargs))

    def test_duplicate_case_id_rejected_by_validate_corpus(self) -> None:
        dup = vcf.ALL_CASES[0]
        with self.assertRaises(vcf.VerdictConsistencyFixtureError):
            vcf.validate_corpus((dup, dup))

    def test_empty_corpus_rejected(self) -> None:
        with self.assertRaises(vcf.VerdictConsistencyFixtureError):
            vcf.validate_corpus(())


class ObservedShapeInvariantTests(unittest.TestCase):
    """validate_observed_shape must reject a two-artifacts (self-correction)
    or zero-artifacts (silent skip) outcome."""

    def test_two_artifacts_at_once_is_rejected(self) -> None:
        observed = vcf.Observed(
            reconciliation_point="x",
            verdict=vc.Verdict.CONSISTENT,
            rendered=vcf.RenderedReportArtifact(signal=vc.RenderedSignal.REVIEW_CLEAN, body="b"),
            withheld=vcf.WithheldArtifact(
                reason=vcf.INTERNAL_CONSISTENCY_FAILURE_REASON, detail="d", reconciliation_point="x"
            ),
        )
        with self.assertRaises(vcf.VerdictConsistencyFixtureError):
            vcf.validate_observed_shape(observed)

    def test_zero_artifacts_is_rejected(self) -> None:
        observed = vcf.Observed(reconciliation_point="x", verdict=vc.Verdict.CONSISTENT)
        with self.assertRaises(vcf.VerdictConsistencyFixtureError):
            vcf.validate_observed_shape(observed)

    def test_withheld_with_wrong_reason_is_rejected(self) -> None:
        observed = vcf.Observed(
            reconciliation_point="x",
            verdict=vc.Verdict.INCONSISTENT,
            withheld=vcf.WithheldArtifact(reason="something_else", detail="d", reconciliation_point="x"),
        )
        with self.assertRaises(vcf.VerdictConsistencyFixtureError):
            vcf.validate_observed_shape(observed)

    def test_consistent_single_artifact_passes(self) -> None:
        observed = vcf.Observed(
            reconciliation_point="x",
            verdict=vc.Verdict.CONSISTENT,
            rendered=vcf.RenderedReportArtifact(signal=vc.RenderedSignal.REVIEW_CLEAN, body="b"),
        )
        vcf.validate_observed_shape(observed)  # must not raise


class ExecuteEveryCaseTests(unittest.TestCase):
    """Runs every case's run(), validates the Observed shape, and asserts
    the withhold-vs-emit outcome matches its declared expectation."""

    def test_every_case_matches_its_declared_expectation(self) -> None:
        for case in vcf.ALL_CASES:
            with self.subTest(case_id=case.case_id):
                observed = case.run()
                vcf.validate_observed_shape(observed)
                if case.expect_withheld:
                    self.assertIsNotNone(
                        observed.withheld, f"{case.case_id}: mismatch was allowed through unwithheld"
                    )
                    self.assertIsNone(observed.rendered, case.case_id)
                    self.assertIsNone(observed.published, case.case_id)
                else:
                    self.assertIsNone(
                        observed.withheld,
                        f"{case.case_id}: a genuinely consistent signal was withheld",
                    )


class BlockingToCleanMismatchIsAlwaysWithheldTests(unittest.TestCase):
    """The single required minimum from #378: a blocking-findings ->
    clean/approve mismatch must be caught at every reconciliation point
    that can express it."""

    def test_every_highest_risk_case_is_withheld(self) -> None:
        cases = vcf.cases_covering("highest-risk")
        self.assertGreaterEqual(len(cases), 4, "expected coverage across multiple reconciliation points")
        for case in cases:
            with self.subTest(case_id=case.case_id):
                self.assertTrue(case.expect_withheld)
                observed = case.run()
                self.assertIsNotNone(observed.withheld)

    def test_active_prepublish_blocking_to_approve_event_is_the_named_case(self) -> None:
        cases = [c for c in vcf.ALL_CASES if c.case_id == "vc-active-prepublish-blocking-to-approve-event-mismatch"]
        self.assertEqual(len(cases), 1)
        observed = cases[0].run()
        self.assertIsNotNone(observed.withheld)
        self.assertEqual(observed.withheld.reason, vcf.INTERNAL_CONSISTENCY_FAILURE_REASON)


class ReconciliationPointCoverageTests(unittest.TestCase):
    """All four reconciliation points named by verdict-consistency.md must
    each have at least one mismatch case that is withheld."""

    def test_local_pre_render_point_1_is_covered(self) -> None:
        cases = vcf.cases_in_category(vcf.CATEGORY_LOCAL_PRE_RENDER)
        self.assertTrue(any(c.expect_withheld for c in cases))

    def test_passive_semi_pre_render_point_2_is_covered(self) -> None:
        cases = vcf.cases_in_category(vcf.CATEGORY_PASSIVE_SEMI_PRE_RENDER)
        self.assertTrue(any(c.expect_withheld for c in cases))

    def test_active_pre_render_point_3_is_covered(self) -> None:
        cases = vcf.cases_in_category(vcf.CATEGORY_ACTIVE_PRE_RENDER)
        self.assertTrue(any(c.expect_withheld for c in cases))

    def test_active_pre_publish_point_4_is_covered(self) -> None:
        cases = vcf.cases_in_category(vcf.CATEGORY_ACTIVE_PRE_PUBLISH)
        self.assertTrue(any(c.expect_withheld for c in cases))


class SilentDriftCaughtOnlyAtPrepublishTests(unittest.TestCase):
    """Proves point (4) is not redundant with point (3): a case whose
    pre-render check already passed must still be caught independently
    when the submitted event later drifts."""

    def _the_case(self) -> vcf.VerdictConsistencyCase:
        cases = vcf.cases_in_category(vcf.CATEGORY_SILENT_DRIFT_AFTER_PRERENDER)
        self.assertEqual(len(cases), 1)
        return cases[0]

    def test_drift_case_is_withheld_despite_prerender_having_passed(self) -> None:
        case = self._the_case()
        observed = case.run()
        self.assertIsNotNone(observed.withheld)
        self.assertEqual(observed.withheld.reconciliation_point, vcf.CATEGORY_ACTIVE_PRE_PUBLISH)


class ReviewIncompleteCarveOutUnderDriftTests(unittest.TestCase):
    """A mismatch that happens to involve REVIEW INCOMPLETE must still be
    caught -- the carve-out is for a *correctly* rendered incomplete
    outcome, never a license to skip checking it."""

    def test_incomplete_coverage_mismatches_are_withheld(self) -> None:
        cases = vcf.cases_in_category(vcf.CATEGORY_INCOMPLETE_COVERAGE_MISMATCH)
        self.assertTrue(cases)
        for case in cases:
            with self.subTest(case_id=case.case_id):
                self.assertTrue(case.expect_withheld)
                self.assertIsNotNone(case.run().withheld)

    def test_correctly_rendered_incomplete_outcome_is_not_withheld(self) -> None:
        cases = [
            c
            for c in vcf.cases_in_category(vcf.CATEGORY_CONTROL_CONSISTENT)
            if "coverage-incomplete" in c.covers
        ]
        self.assertTrue(cases)
        for case in cases:
            with self.subTest(case_id=case.case_id):
                self.assertIsNone(case.run().withheld)


class NeverSilentlySkippedOrSelfCorrectedTests(unittest.TestCase):
    """Every mismatch case's withheld artifact must classify the failure
    as an internal verdict-consistency failure -- never a bare pass-through
    (silent skip) and never a rendered/published artifact alongside it
    (self-correction)."""

    def test_every_mismatch_case_is_classified_as_internal_consistency_failure(self) -> None:
        for case in vcf.ALL_CASES:
            if not case.expect_withheld:
                continue
            with self.subTest(case_id=case.case_id):
                observed = case.run()
                self.assertEqual(observed.withheld.reason, vcf.INTERNAL_CONSISTENCY_FAILURE_REASON)
                self.assertTrue(observed.withheld.detail)

    def test_no_wrapper_function_accepts_an_override_or_correction_parameter(self) -> None:
        for name, obj in inspect.getmembers(vcf):
            if not inspect.isfunction(obj):
                continue
            for param_name in inspect.signature(obj).parameters:
                lowered = param_name.lower()
                for fragment in vc.PROHIBITED_OVERRIDE_PARAM_FRAGMENTS | vc.PROHIBITED_CORRECTION_FRAGMENTS:
                    self.assertNotIn(
                        fragment,
                        lowered,
                        f"{name}() must not accept an override/correction parameter, found: {param_name}",
                    )


class ControlCasesNeverWithheldTests(unittest.TestCase):
    """A genuinely consistent signal must never be flagged -- this corpus
    is adversarial, not trigger-happy."""

    def test_every_control_case_is_not_withheld(self) -> None:
        cases = vcf.cases_in_category(vcf.CATEGORY_CONTROL_CONSISTENT)
        self.assertGreaterEqual(len(cases), 3)
        for case in cases:
            with self.subTest(case_id=case.case_id):
                self.assertFalse(case.expect_withheld)
                self.assertIsNone(case.run().withheld)


class SeparateFromFindingPrecisionMetricsTests(unittest.TestCase):
    """Disjoint from #350's normal-path proof and from the finding
    precision/recall/severity metrics -- this corpus never touches a
    finding's content beyond the closed severity used to derive the
    mechanical decision it starts from."""

    def test_fixtures_module_touches_no_finding_matching_machinery(self) -> None:
        source = inspect.getsource(vcf)
        for forbidden in ("benchmark_match", "benchmark_metrics", "ProducedFinding"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
