"""Campaign configuration of the temporary concurrency measurement (Issue #682).

Covers the committed subset, schedule, pin and thresholds, and the decision evaluator. Execution is stubbed;
no live model call is made.
"""

from __future__ import annotations

import copy
import inspect
import math
import unittest
from pathlib import Path
from unittest import mock

import yaml

from runtime_platform.benchmark.scripts import benchmark_concurrency_decision as decision
from runtime_platform.benchmark.scripts import benchmark_lane_run as lane_run
from runtime_platform.benchmark.scripts import benchmark_termination as termination
from runtime_platform.benchmark.scripts import run_concurrency_experiment as exp
from runtime_platform.benchmark.scripts.benchmark_corpus_membership import discover_comprehensive_fixtures
from tests.support.evidence_destination import offline_destination
from runtime_platform.benchmark.scripts.benchmark_evidence_destination import StoreUnavailable
from runtime_platform.benchmark.scripts.benchmark_evidence_destination import StoreUnavailable

_RESOLUTION = mock.patch.object(exp, "resolve_destination", side_effect=lambda *_a, **_k: offline_destination())


def setUpModule() -> None:
    _RESOLUTION.start()  # no test here contacts a real evidence store


def tearDownModule() -> None:
    _RESOLUTION.stop()


SHA = "a" * 40
DATES = ("2026-10-13", "2026-10-15", "2026-10-20", "2026-10-22")
ARMS = ([1, 2], [2, 4], [2, 1], [4, 2])
WIDE_KEYS = {"workspace_siblings", "repositories", "external_contexts", "unadmitted_repositories"}


def committed() -> dict:
    return exp.load_spec()


def fixtures_by_id() -> dict[str, dict]:
    found = discover_comprehensive_fixtures(Path(exp.rb.DEFAULT_CORPUS_DIR))
    return {fx.case_id: yaml.safe_load(fx.fixture_path.read_text(encoding="utf-8")) for fx in found}


class CommittedSubsetTest(unittest.TestCase):
    def test_identity_matches_the_corpus_and_is_deterministic(self):
        spec = committed()
        first, manifest = exp.select_subset(spec, str(exp.rb.DEFAULT_CORPUS_DIR))
        second, again = exp.select_subset(spec, str(exp.rb.DEFAULT_CORPUS_DIR))
        self.assertEqual(manifest, again)
        self.assertEqual(manifest["subset_id"], spec["subset"]["subset_id"])
        self.assertEqual([f.case_id for f in first], spec["subset"]["case_ids"])
        self.assertEqual(len(first), spec["subset"]["size"])

    def test_a_changed_fixture_digest_fails_closed(self):
        spec = committed()
        spec["subset"]["subset_id"] = "0" * 64
        with self.assertRaisesRegex(exp.RoutineExecutionError, "subset_id"):
            exp.select_subset(spec, str(exp.rb.DEFAULT_CORPUS_DIR))

    def test_strata_partition_the_case_ids(self):
        subset = committed()["subset"]
        listed = [c for ids in subset["strata"].values() for c in ids]
        self.assertEqual(sorted(listed), subset["case_ids"])
        self.assertEqual(len(listed), len(set(listed)))
        self.assertGreaterEqual(len(subset["case_ids"]) // 4, 6, "each of 4 workers needs several fixtures")

    def test_every_stratum_matches_the_fixtures_it_claims_to_represent(self):
        subset, corpus = committed()["subset"], fixtures_by_id()
        strata = subset["strata"]
        tags = lambda c: set(corpus[c]["metadata"]["tags"])  # noqa: E731
        patch_files = lambda c: (corpus[c]["input"].get("patch") or "").count("diff --git")  # noqa: E731
        self.assertTrue(all(c in corpus for c in subset["case_ids"]))
        self.assertTrue(all(patch_files(c) >= 10 for c in strata["large-patch"]))
        self.assertTrue(all(WIDE_KEYS & set(corpus[c]["input"]) for c in strata["wide-context"]))
        for name in ("security", "concurrency", "performance"):
            self.assertTrue(any(name in tags(c) for c in strata[name]), name)
        self.assertTrue(all(patch_files(c) >= 2 for c in strata["multi-file"]))
        self.assertTrue(all(corpus[c]["expected"]["decision"] == "clean" and not corpus[c]["expected"]["findings"] for c in strata["no-finding"]))
        self.assertTrue(all(patch_files(c) == 1 for c in strata["fast-single-file"]))

    def test_decision_mix_covers_findings_and_clean_expectations(self):
        corpus = fixtures_by_id()
        decisions = {corpus[c]["expected"]["decision"] for c in committed()["subset"]["case_ids"]}
        self.assertEqual(decisions, {"clean", "changes-required"})

    def test_a_subset_that_is_not_the_strata_union_is_rejected(self):
        spec = committed()
        spec["subset"]["case_ids"] = spec["subset"]["case_ids"][:-1]
        with self.assertRaisesRegex(decision.SpecError, "sorted union"):
            decision.validate_spec(spec)
        spec = committed()
        spec["subset"]["strata"]["security"].append(spec["subset"]["strata"]["performance"][0])
        with self.assertRaisesRegex(decision.SpecError, "only one stratum"):
            decision.validate_spec(spec)


class ScheduleAuthorizationTest(unittest.TestCase):
    def test_committed_campaign_is_the_approved_one(self):
        spec = committed()
        stop = spec["stop_condition"]
        self.assertEqual([(e["date"], e["arms"]) for e in stop["experiments"]], list(zip(DATES, ARMS)))
        self.assertEqual(stop["window_end"], DATES[-1])
        self.assertEqual(stop["max_experiments"], 4)
        self.assertEqual(spec["intended_start"]["timezone"], "Asia/Jerusalem")
        self.assertEqual(spec["intended_start"]["local_time"], "12:00")
        decision.validate_spec(spec)

    def test_each_listed_day_runs_its_own_arms_and_no_other_day_runs(self):
        spec = committed()
        for date, arms in zip(DATES, ARMS):
            self.assertIsNone(exp.skip_reason(spec, [], date, date))
            self.assertEqual(exp.scheduled_arms(spec, date), arms)
        for other in ("2026-10-12", "2026-10-14", "2026-10-16", "2026-10-21"):
            self.assertEqual(exp.skip_reason(spec, [], other, other), "not-an-experiment-day")

    def test_nothing_starts_after_the_window(self):
        for late in ("2026-10-23", "2026-10-27", "2027-01-01"):
            self.assertEqual(exp.skip_reason(committed(), [], late, late), "window-ended")

    def test_noon_in_jerusalem_is_the_listed_local_date(self):
        from datetime import datetime, timezone

        noon_utc = datetime(2026, 10, 13, 9, 0, tzinfo=timezone.utc)
        self.assertEqual(exp.local_today(committed(), noon_utc), "2026-10-13")

    def test_inconsistent_schedules_are_rejected(self):
        cases = {
            "weekday": lambda s: s["stop_condition"]["experiments"][0].update(date="2026-10-14"),
            "window_end": lambda s: s["stop_condition"].update(window_end="2026-10-23"),
            "count": lambda s: s["stop_condition"]["experiments"].pop(),
            "order": lambda s: s["stop_condition"]["experiments"].reverse(),
            "duplicate": lambda s: s["stop_condition"]["experiments"][1].update(date=DATES[0]),
            "counterbalance": lambda s: s["stop_condition"]["experiments"][2].update(arms=[1, 2]),
            "unsupported": lambda s: s["stop_condition"]["experiments"][0].update(arms=[1, 3]),
            "single arm": lambda s: s["stop_condition"]["experiments"][0].update(arms=[2]),
            "bad date": lambda s: s["stop_condition"]["experiments"][0].update(date="soon"),
        }
        for name, mutate in cases.items():
            spec = committed()
            mutate(spec)
            with self.assertRaises(decision.SpecError, msg=name):
                decision.validate_campaign(spec)

    def test_a_window_without_dates_is_rejected(self):
        spec = committed()
        spec["stop_condition"]["experiments"] = []
        with self.assertRaises(decision.SpecError):
            decision.validate_campaign(spec)


class WorkerValidationTest(unittest.TestCase):
    def test_scheduled_arms_outside_the_allowed_counts_are_rejected(self):
        spec = committed()
        spec["stop_condition"]["experiments"][0]["arms"] = [1, 3]
        with self.assertRaises(exp.RoutineExecutionError):
            exp.scheduled_arms(spec, DATES[0])

    def test_an_unsupported_scheduled_arm_runs_no_fixture(self):
        spec = committed()
        spec["stop_condition"]["experiments"][0]["arms"] = [1, 8]
        with mock.patch.object(exp, "load_spec", return_value=spec), mock.patch.object(exp.workers_mod, "run_arm") as arm:
            self.assertEqual(exp.main(["--cli", "fake", "--trigger", "scheduled", "--pinned-sha", SHA]), 1)
        arm.assert_not_called()


def run_scheduled(date: str, *, head: str, pinned: str | None, clean: bool = True, refs=()):
    argv = ["--cli", "fake", "--trigger", "scheduled", "--runtime-version", "v1"] + (["--pinned-sha", pinned] if pinned else [])
    with mock.patch.object(exp, "prior_experiment_refs", return_value=list(refs)), mock.patch.object(exp, "local_today", return_value=date), mock.patch.object(
        exp, "utc_now", return_value=f"{date}T09:00:00Z"
    ), mock.patch.object(exp, "git_sha", return_value=head), mock.patch.object(exp, "checkout_is_clean", return_value=clean), mock.patch.object(
        exp.workers_mod, "run_arm"
    ) as arm, mock.patch.object(exp.seal, "seal_to_ref", return_value="c" * 40) as push:
        code = exp.main(argv)
    return code, arm, push


class PinnedShaTest(unittest.TestCase):
    def test_accepts_only_the_exact_clean_checkout(self):
        decision.check_pinned_sha(SHA, SHA, True)
        for expected, actual, clean, why in (
            (None, SHA, True, "missing"),
            ("abc123", "abc123", True, "short"),
            (SHA.upper(), SHA.upper(), True, "uppercase"),
            (SHA, "b" * 40, True, "mismatch"),
            (SHA, SHA, False, "dirty"),
        ):
            with self.assertRaises(decision.SpecError, msg=why):
                decision.check_pinned_sha(expected, actual, clean)

    def test_a_mismatching_checkout_fails_before_any_fixture_runs(self):
        for head, pinned, clean in (("b" * 40, SHA, True), (SHA, None, True), (SHA, SHA, False)):
            code, arm, push = run_scheduled(DATES[0], head=head, pinned=pinned, clean=clean)
            self.assertEqual(code, 1)
            arm.assert_not_called()
            push.assert_not_called()

    def test_the_pinned_checkout_runs_each_day_with_its_own_arms(self):
        for date, arms in zip(DATES, ARMS):
            _, arm, push = run_scheduled(date, head=SHA, pinned=SHA)
            self.assertEqual([call.args[0] for call in arm.call_args_list], arms)
            self.assertTrue(push.call_args.args[2].startswith(exp.EXPERIMENT_REF_PREFIX))
            self.assertEqual(push.call_args.args[3]["concurrency-experiment.json"].count(SHA.encode()) > 0, True)

    def test_a_skipped_day_does_not_need_the_pin(self):
        code, arm, _ = run_scheduled("2026-10-14", head="b" * 40, pinned=None)
        self.assertEqual(code, 0)
        arm.assert_not_called()


class DuplicateAndStopTest(unittest.TestCase):
    def _run(self, date: str, refs: list[str]):
        return run_scheduled(date, head=SHA, pinned=SHA, refs=refs)

    def test_a_second_run_on_the_same_day_does_nothing(self):
        refs = [f"{exp.EXPERIMENT_REF_PREFIX}{DATES[1].replace('-', '')}T090000Z-aaaaaaaaaaaa"]
        code, arm, push = self._run(DATES[1], refs)
        self.assertEqual(code, 0)
        arm.assert_not_called()
        push.assert_not_called()

    def test_a_missed_day_is_not_made_up_on_a_later_day(self):
        refs = [f"{exp.EXPERIMENT_REF_PREFIX}{d.replace('-', '')}T090000Z-aaaaaaaaaaaa" for d in (DATES[0], DATES[2])]
        for later in ("2026-10-16", "2026-10-21"):
            code, arm, _ = self._run(later, refs)
            self.assertEqual(code, 0)
            arm.assert_not_called()

    def test_four_experiment_refs_stop_the_campaign_even_on_a_listed_day(self):
        refs = [f"{exp.EXPERIMENT_REF_PREFIX}2026100{i}T090000Z-aaaaaaaaaaaa" for i in range(1, 5)]
        code, arm, _ = self._run(DATES[3], refs)
        self.assertEqual(code, 0)
        arm.assert_not_called()

    def test_the_window_end_stops_the_campaign_with_runs_left(self):
        code, arm, _ = self._run("2026-10-23", [])
        self.assertEqual(code, 0)
        arm.assert_not_called()

    def test_an_unlistable_ref_set_refuses_to_run(self):
        with mock.patch.object(exp, "prior_experiment_refs", side_effect=StoreUnavailable("offline")), mock.patch.object(
            exp, "local_today", return_value=DATES[0]
        ), mock.patch.object(exp.workers_mod, "run_arm") as arm:
            self.assertEqual(exp.main(["--cli", "fake", "--trigger", "scheduled", "--pinned-sha", SHA]), 3)
        arm.assert_not_called()


class ThresholdConfigurationTest(unittest.TestCase):
    def test_the_committed_thresholds_are_valid(self):
        decision.validate_thresholds(committed()["decision"], committed()["allowed_workers"])

    def test_invalid_thresholds_are_rejected(self):
        cases = {
            "isolation relaxed": lambda d: d["hard_safety_gates"].update(max_isolation_violations=1),
            "valid rate relaxed": lambda d: d["hard_safety_gates"].update(min_valid_result_rate=0.95),
            "unknown provenance key": lambda d: d["hard_safety_gates"].update(provenance_must_match_across_experiments=["mood"]),
            "empty provenance": lambda d: d["hard_safety_gates"].update(provenance_must_match_across_experiments=[]),
            "efficiency missing key": lambda d: d["performance_thresholds"]["min_scaling_efficiency"].pop("4"),
            "efficiency above 1": lambda d: d["performance_thresholds"]["min_scaling_efficiency"].update({"2": 1.5}),
            "efficiency string": lambda d: d["performance_thresholds"]["min_scaling_efficiency"].update({"2": "0.6"}),
            "speedup floor": lambda d: d["performance_thresholds"].update(no_meaningful_speedup_below=1.0),
            "cv zero": lambda d: d["performance_thresholds"].update(max_same_config_wall_cv=0),
            "disagreement negative": lambda d: d["performance_thresholds"].update(max_outcome_disagreement_excess=-0.1),
            "rate limit fraction": lambda d: d["performance_thresholds"].update(max_rate_limited_fixture_fraction=2),
            "window fraction loosened": lambda d: d["window"].update(max_fraction_of_window=0.9),
            "window fraction bool": lambda d: d["window"].update(max_fraction_of_window=True),
            "window negative": lambda d: d["window"].update(evidenced_window_s=-5),
            "confirmations": lambda d: d["window"].update(worst_case_confirmation_invocations=-1),
            "diagnostics": lambda d: d.update(diagnostic_indicators="all"),
            "missing section": lambda d: d.pop("window"),
        }
        for name, mutate in cases.items():
            spec = committed()
            mutate(spec["decision"])
            with self.assertRaises(decision.SpecError, msg=name):
                decision.validate_thresholds(spec["decision"], spec["allowed_workers"])

    def test_the_recorded_window_is_a_conservative_bound_not_a_provider_sla(self):
        window = committed()["decision"]["window"]
        evidence = window["evidence"]
        self.assertEqual(evidence["reported_phase_duration_s"], 2399.4)
        self.assertEqual(evidence["kind"], "conservative-lower-bound")
        self.assertIs(evidence["provider_sla"], False)
        self.assertEqual(evidence["issue"], 696)
        self.assertIn("fixtures phase only", evidence["measures"])
        derived = math.floor((evidence["reported_phase_duration_s"] - evidence["reported_precision_s"] - evidence["max_cleanup_after_signal_s"]) * 10 + 1e-6) / 10
        self.assertEqual(window["evidenced_window_s"], derived)
        self.assertEqual(window["evidenced_window_s"], 2379.3)
        self.assertLess(window["evidenced_window_s"], evidence["reported_phase_duration_s"])
        self.assertEqual(window["max_fraction_of_window"], 0.6)
        self.assertAlmostEqual(window["evidenced_window_s"] * window["max_fraction_of_window"], 1427.58)

    def test_the_cleanup_allowance_covers_the_verified_unwinding_path(self):
        cleanup = committed()["decision"]["window"]["evidence"]["max_cleanup_after_signal_s"]
        source = inspect.getsource(lane_run.invoke)
        self.assertIn("stop_process_tree(proc, PARENT_GRACE_S)", source)
        self.assertIn("forwarder.join(timeout=2.0)", source)
        self.assertGreaterEqual(cleanup, termination.PARENT_GRACE_S + termination.KILL_WAIT_S + 2.0)

    def test_recording_the_window_leaves_the_other_thresholds_unchanged(self):
        decision_spec = committed()["decision"]
        self.assertEqual(decision_spec["hard_safety_gates"]["max_isolation_violations"], 0)
        self.assertEqual(decision_spec["hard_safety_gates"]["min_valid_result_rate"], 1.0)
        self.assertEqual(decision_spec["performance_thresholds"], {
            "min_scaling_efficiency": {"2": 0.6, "4": 0.45},
            "no_meaningful_speedup_below": 1.15,
            "max_same_config_wall_cv": 0.25,
            "max_outcome_disagreement_excess": 0.0,
            "max_rate_limited_fixture_fraction": 0.05,
        })
        self.assertEqual(decision_spec["window"]["worst_case_confirmation_invocations"], 20)

    def test_a_run_with_invalid_thresholds_starts_nothing(self):
        spec = committed()
        spec["decision"]["window"]["max_fraction_of_window"] = 0.95
        with mock.patch.object(exp, "load_spec", return_value=spec), mock.patch.object(exp.workers_mod, "run_arm") as arm:
            self.assertEqual(exp.main(["--arms", "1,2", "--cli", "fake", "--seal-dir", "/nonexistent"]), 1)
        arm.assert_not_called()

    def test_a_wrong_pin_mechanism_is_rejected(self):
        spec = committed()
        spec["pin"]["mechanism"] = "self-reference"
        with self.assertRaises(decision.SpecError):
            decision.validate_spec(spec)


def fixture(case_id: str, findings: int = 1, hits: int = 0) -> dict:
    return {"case_id": case_id, "produced_finding_count": findings, "rate_limit_hits": hits}


def arm(workers: int, wall: float, *, planned: int = 4, completed: int | None = None, findings: int = 1, hits: int = 0) -> dict:
    ids = [f"c{i}" for i in range(planned)]
    return {
        "workers": workers, "planned": planned, "attempted": planned, "completed": planned if completed is None else completed,
        "wall_s": wall, "fixtures": [fixture(c, findings, hits if i == 0 else 0) for i, c in enumerate(ids)],
    }


def experiment(arms: list[dict], *, sha: str = SHA, violations: int = 0, model: str = "m", status: str = "complete") -> dict:
    return {
        "status": status,
        "planned_arms": [a["workers"] for a in arms],
        "isolation": {"violations": [{}] * violations},
        "provenance": {"repo_sha": sha},
        "runtime": {"model_id": model, "runtime_version": "v1"},
        "manifest": {"subset_id": "s", "corpus_id": "c"},
        "arms": arms,
    }


def good_campaign() -> list[dict]:
    return [
        experiment([arm(1, 200.0), arm(2, 110.0)]),
        experiment([arm(2, 105.0), arm(4, 60.0)]),
        experiment([arm(2, 112.0), arm(1, 205.0)]),
        experiment([arm(4, 58.0), arm(2, 108.0)]),
    ]


def evaluate(experiments: list[dict], *, window: float | None = 10000.0, pinned: str | None = SHA) -> dict:
    thresholds = copy.deepcopy(committed()["decision"])
    thresholds["window"]["evidenced_window_s"] = window
    return decision.evaluate_campaign(experiments, thresholds, corpus_size=144, pinned_sha=pinned)


def outcome(result: dict, check_id: str) -> dict:
    return next(c for c in result["checks"] if c["id"] == check_id)


class DecisionEvaluationTest(unittest.TestCase):
    def test_go_needs_every_threshold_and_an_evidenced_window(self):
        result = evaluate(good_campaign())
        self.assertEqual(result["decision"], "GO", [c for c in result["checks"] if c["passed"] is not True])
        self.assertIn(2, result["eligible_worker_counts"])

    def test_an_unevidenced_window_can_never_be_go(self):
        result = evaluate(good_campaign(), window=None)
        self.assertEqual(result["decision"], "INCONCLUSIVE")
        self.assertIsNone(outcome(result, "projected-full-corpus-2-workers")["passed"])

    def test_a_projection_over_sixty_percent_of_the_window_is_not_go(self):
        result = evaluate(good_campaign(), window=600.0)
        self.assertEqual(result["decision"], "INCONCLUSIVE")
        self.assertFalse(outcome(result, "projected-full-corpus-2-workers")["passed"])

    def test_an_isolation_violation_is_no_go(self):
        campaign = good_campaign()
        campaign[1] = experiment(campaign[1]["arms"], violations=1)
        self.assertEqual(evaluate(campaign)["decision"], "NO-GO")

    def test_an_incomplete_result_is_no_go(self):
        campaign = good_campaign()
        campaign[0] = experiment([arm(1, 200.0), arm(2, 110.0, completed=3)])
        self.assertEqual(evaluate(campaign)["decision"], "NO-GO")

    def test_provenance_drift_or_a_foreign_sha_is_no_go(self):
        campaign = good_campaign()
        campaign[2] = experiment(campaign[2]["arms"], model="other")
        self.assertEqual(evaluate(campaign)["decision"], "NO-GO")
        self.assertEqual(evaluate(good_campaign(), pinned="b" * 40)["decision"], "NO-GO")

    def test_no_meaningful_speedup_is_no_go(self):
        campaign = [experiment([arm(1, 100.0), arm(2, 95.0)]), experiment([arm(2, 96.0), arm(4, 94.0)]), experiment([arm(2, 97.0), arm(1, 99.0)]), experiment([arm(4, 95.0), arm(2, 96.0)])]
        self.assertEqual(evaluate(campaign)["decision"], "NO-GO")

    def test_too_few_experiments_is_inconclusive(self):
        result = evaluate(good_campaign()[:2])
        self.assertEqual(result["decision"], "INCONCLUSIVE")
        self.assertFalse(outcome(result, "coverage")["passed"])
        self.assertEqual(evaluate([])["decision"], "INCONCLUSIVE")

    def test_noisy_same_configuration_runs_are_inconclusive(self):
        campaign = good_campaign()
        campaign[2] = experiment([arm(2, 300.0), arm(1, 205.0)])
        result = evaluate(campaign)
        self.assertFalse(outcome(result, "same-config-wall-cv")["passed"])
        self.assertEqual(result["decision"], "INCONCLUSIVE")

    def test_disagreement_above_the_same_configuration_baseline_is_not_go(self):
        campaign = good_campaign()
        campaign[1] = experiment([arm(2, 105.0), arm(4, 60.0, findings=2)])
        result = evaluate(campaign)
        self.assertFalse(outcome(result, "outcome-disagreement-excess")["passed"])
        self.assertEqual(result["decision"], "INCONCLUSIVE")

    def test_unmeasured_outcomes_cannot_pass(self):
        campaign = good_campaign()
        for e in campaign:
            for a in e["arms"]:
                for f in a["fixtures"]:
                    f["produced_finding_count"] = None
        self.assertIsNone(outcome(evaluate(campaign), "outcome-disagreement-excess")["passed"])
        self.assertNotEqual(evaluate(campaign)["decision"], "GO")

    def test_rate_limiting_above_the_fraction_removes_that_worker_count(self):
        campaign = good_campaign()
        campaign[1] = experiment([arm(2, 105.0), arm(4, 60.0, hits=3)])
        result = evaluate(campaign)
        self.assertFalse(outcome(result, "rate-limited-fixtures-4-workers")["passed"])
        self.assertEqual(result["eligible_worker_counts"], [2])
        self.assertEqual(result["decision"], "GO", "a worker count that fails its own thresholds does not block another that passes")

    def test_an_incomplete_or_terminated_experiment_is_no_go(self):
        campaign = good_campaign()
        campaign[3] = experiment(campaign[3]["arms"], status="terminated")
        self.assertEqual(evaluate(campaign)["decision"], "NO-GO")
        campaign = good_campaign()
        campaign[0]["planned_arms"] = [1, 2, 4]
        self.assertEqual(evaluate(campaign)["decision"], "NO-GO")


if __name__ == "__main__":
    unittest.main()
