"""In-run confirmation and drift evaluation (#470; drift-issue-lifecycle-and-recovery.md §2)."""

from __future__ import annotations

import unittest
from typing import Any, Mapping

from runtime_platform.benchmark.reference import benchmark_result_reference as ref
from runtime_platform.benchmark.scripts import benchmark_result as res
from runtime_platform.benchmark.scripts.benchmark_baseline import BaselineLookup
from runtime_platform.benchmark.scripts.benchmark_drift_evaluation import (
    ConfirmationPolicy,
    evaluate_drift,
)
from runtime_platform.benchmark.scripts.benchmark_run_record import (
    metrics_from_case,
    noise_from_case,
    severity_from_case,
)
from tests.support.benchmark_records import make_case, sealed_record

POLICY = ConfirmationPolicy(reruns=2, threshold=2, max_cases=10)
RUNTIME = {"runtime_name": "cli", "runtime_version": "cli-1", "model_id": "model-a"}


def _baseline(*cases: Mapping[str, Any], **kwargs: str) -> BaselineLookup:
    return BaselineLookup("compared", record=sealed_record("sentinel", list(cases), **kwargs))


class Observer:
    """Fake `observe`: a per-case queue of rerun cases; records every call."""

    def __init__(self, queues: Mapping[str, list[Mapping[str, Any]]] | None = None) -> None:
        self.queues = {k: list(v) for k, v in (queues or {}).items()}
        self.calls: list[str] = []

    def __call__(self, case_id: str) -> Mapping[str, Any]:
        self.calls.append(case_id)
        return self.queues[case_id].pop(0)


def _evaluate(candidate, lookup, observer=None, policy=POLICY, **kwargs):
    return evaluate_drift(candidate, lookup, policy, RUNTIME, observer or Observer(), **kwargs)


class NotEvaluatedTests(unittest.TestCase):
    def test_bootstrap_is_not_evaluated_and_runs_nothing(self) -> None:
        observer = Observer()
        result = _evaluate([make_case("a")], BaselineLookup("bootstrap"), observer)
        self.assertEqual(result.baseline["state"], "bootstrap")
        self.assertEqual(result.drift["outcome"]["status"], "not-evaluated")
        self.assertEqual((result.reruns_performed, observer.calls), (0, []))

    def test_incomparable_baseline_carries_its_reason(self) -> None:
        result = _evaluate([make_case("a")], BaselineLookup("incomparable", reason="lane-identity mismatch"))
        self.assertEqual(result.baseline["state"], "incomparable")
        self.assertEqual(result.drift["outcome"], {"status": "not-evaluated", "reason": "lane-identity mismatch"})

    def test_no_comparable_case_is_not_evaluated(self) -> None:
        result = _evaluate([make_case("a", fixture="edited")], _baseline(make_case("a")))
        self.assertEqual(result.baseline["state"], "compared")
        self.assertEqual(result.drift["outcome"]["status"], "not-evaluated")
        self.assertEqual(result.drift["evaluated_scope"], [])


class ClassificationTests(unittest.TestCase):
    def test_no_drift_runs_no_confirmation(self) -> None:
        observer = Observer()
        result = _evaluate([make_case("a"), make_case("b")], _baseline(make_case("a"), make_case("b")), observer)
        self.assertEqual(result.drift["outcome"], {"status": "none", "reason": None})
        self.assertEqual(result.drift["evaluated_scope"], ["a", "b"])
        self.assertEqual((result.reruns_performed, observer.calls), (0, []))

    def test_fixture_edit_makes_only_that_case_incomparable(self) -> None:
        candidate = [make_case("a", missed=["k"], fixture="edited"), make_case("b")]
        result = _evaluate(candidate, _baseline(make_case("a"), make_case("b")))
        self.assertEqual(result.baseline["comparable_case_ids"], ["b"])
        self.assertEqual([c["id"] for c in result.baseline["incomparable_cases"]], ["a"])
        self.assertEqual(result.drift["observations"], [])

    def test_runtime_change_is_attributed_but_not_suppressed(self) -> None:
        drifting = [make_case("a", missed=["k"])]
        observer = Observer({"a": [make_case("a", missed=["k"])] * 2})
        result = _evaluate(drifting, _baseline(make_case("a"), model_id="model-old"), observer)
        self.assertEqual(result.drift["attribution"], "runtime-changed")
        self.assertEqual(len(result.drift["confirmed"]), 2)

    def test_same_runtime_has_no_attribution(self) -> None:
        self.assertEqual(_evaluate([make_case("a")], _baseline(make_case("a"))).drift["attribution"], "none")


class ConfirmationProtocolTests(unittest.TestCase):
    """A newly missed finding is two fingerprints: `missed-required-finding` and `decision-flip`."""

    def setUp(self) -> None:
        self.baseline = _baseline(make_case("a"))
        self.drifting = [make_case("a", missed=["k"])]

    def test_only_the_drifting_case_is_rerun_the_configured_number_of_times(self) -> None:
        observer = Observer({"a": [make_case("a", missed=["k"])] * 2})
        result = _evaluate([make_case("a", missed=["k"]), make_case("b")], _baseline(make_case("a"), make_case("b")), observer)
        self.assertEqual(observer.calls, ["a", "a"])
        self.assertEqual(result.reruns_performed, 2)

    def test_confirmed_when_seen_in_threshold_of_the_observations(self) -> None:
        observer = Observer({"a": [make_case("a"), make_case("a", missed=["k"])]})
        result = _evaluate(self.drifting, self.baseline, observer)
        self.assertEqual([r["case_id"] for r in result.drift["confirmed"]], ["a", "a"])
        self.assertEqual(result.drift["unconfirmed"], [])
        self.assertEqual(result.drift["outcome"]["status"], "drift")

    def test_not_reproduced_is_unconfirmed_and_never_issue_worthy(self) -> None:
        observer = Observer({"a": [make_case("a"), make_case("a")]})
        result = _evaluate(self.drifting, self.baseline, observer)
        self.assertEqual(result.drift["confirmed"], [])
        self.assertEqual({u["reason"] for u in result.drift["unconfirmed"]}, {"not-reproduced"})
        self.assertEqual(result.drift["outcome"]["status"], "none")

    def test_threshold_counts_the_initial_observation(self) -> None:
        strict = ConfirmationPolicy(reruns=2, threshold=3, max_cases=10)
        one_of_two = Observer({"a": [make_case("a", missed=["k"]), make_case("a")]})
        self.assertEqual(_evaluate(self.drifting, self.baseline, one_of_two, strict).drift["confirmed"], [])
        two_of_two = Observer({"a": [make_case("a", missed=["k"])] * 2})
        self.assertEqual(len(_evaluate(self.drifting, self.baseline, two_of_two, strict).drift["confirmed"]), 2)

    def test_confirmation_is_per_fingerprint_and_ignores_rerun_only_ones(self) -> None:
        observer = Observer({"a": [make_case("a", missed=["other"])] * 2})
        result = _evaluate(self.drifting, self.baseline, observer)
        self.assertEqual([r["drift_type"] for r in result.drift["confirmed"]], ["decision-flip"])
        self.assertEqual([u["expected_finding_key"] for u in result.drift["unconfirmed"]], ["k"])
        self.assertNotIn("other", [o["expected_finding_key"] for o in result.drift["observations"]])

    def test_observations_partition_into_confirmed_and_unconfirmed(self) -> None:
        observer = Observer({"a": [make_case("a", missed=["k"])] * 2})
        result = _evaluate(self.drifting, self.baseline, observer)
        observed = {o["fingerprint"] for o in result.drift["observations"]}
        parts = {c["fingerprint"] for c in result.drift["confirmed"]} | {u["fingerprint"] for u in result.drift["unconfirmed"]}
        self.assertEqual(observed, parts)

    def test_cap_flags_systemic_and_skips_the_remainder(self) -> None:
        ids = [f"c{i:02d}" for i in range(12)]
        baseline = _baseline(*[make_case(i) for i in ids])
        candidate = [make_case(i, missed=["k"]) for i in ids]
        observer = Observer({i: [make_case(i, missed=["k"])] * 2 for i in ids})
        result = _evaluate(candidate, baseline, observer)
        self.assertTrue(result.drift["systemic"])
        self.assertEqual(result.reruns_performed, 20)
        self.assertEqual(sorted(set(observer.calls)), ids[:10])
        capped = [u for u in result.drift["unconfirmed"] if u["reason"] == "systemic-cap"]
        self.assertEqual(sorted({u["case_id"] for u in capped}), ids[10:])
        self.assertEqual({r["case_id"] for r in result.drift["confirmed"]}, set(ids[:10]))

    def test_at_the_cap_is_not_systemic(self) -> None:
        ids = [f"c{i:02d}" for i in range(10)]
        baseline = _baseline(*[make_case(i) for i in ids])
        observer = Observer({i: [make_case(i, missed=["k"])] * 2 for i in ids})
        result = _evaluate([make_case(i, missed=["k"]) for i in ids], baseline, observer)
        self.assertFalse(result.drift["systemic"])

    def test_exhausted_budget_records_unconfirmed_timeout(self) -> None:
        observer = Observer({"a": [make_case("a", missed=["k"])] * 2})
        result = _evaluate(self.drifting, self.baseline, observer, deadline=10.0, clock=lambda: 11.0)
        self.assertEqual(observer.calls, [])
        self.assertEqual({u["reason"] for u in result.drift["unconfirmed"]}, {"unconfirmed-timeout"})

    def test_budget_expiring_mid_case_keeps_a_fingerprint_already_at_threshold(self) -> None:
        ticks = iter([0.0, 5.0])
        observer = Observer({"a": [make_case("a", missed=["k"])]})
        result = _evaluate(self.drifting, self.baseline, observer, deadline=1.0, clock=lambda: next(ticks))
        self.assertEqual(observer.calls, ["a"])
        self.assertEqual(len(result.drift["confirmed"]), 2)

    def test_an_unverifiable_rerun_propagates(self) -> None:
        def failing(_: str) -> Mapping[str, Any]:
            raise RuntimeError("fail-closed")

        with self.assertRaises(RuntimeError):
            _evaluate(self.drifting, self.baseline, failing)


class ConformanceTests(unittest.TestCase):
    def test_blocks_build_a_record_the_validator_accepts(self) -> None:
        baseline_record = sealed_record("sentinel", [make_case("a"), make_case("b")])
        candidate = [make_case("a", missed=["k"]), make_case("b", fixture="edited")]
        observer = Observer({"a": [make_case("a", missed=["k"]), make_case("a")]})
        result = _evaluate(candidate, BaselineLookup("compared", record=baseline_record), observer)
        drift = {**result.drift, "evidence": {"a": "excerpt"}}
        projections = [
            ref.CaseProjection(
                c["id"],
                c["fixture_digest"],
                metrics_from_case(c),
                severity_from_case(c),
                noise_from_case(c),
                1.0,
            )
            for c in candidate
        ]
        record = ref.build_record(
            lane="sentinel",
            projections=projections,
            corpus_id="0" * 64,
            repo_sha="b" * 40,
            started_at="2026-09-04T01:00:00Z",
            baseline=result.baseline,
            drift=drift,
        )
        self.assertEqual(res.validate_record(record), [])


if __name__ == "__main__":
    unittest.main()
