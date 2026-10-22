"""Tests for the per-test timing report."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.validation import suite_timing_report as timing


def sample(runs=2):
    return {
        "schema": timing.SCHEMA,
        "environment": {"python": "3.x", "platform": "test", "cpu_count": 1},
        "runs": runs,
        "discovery_seconds": [0.5, 0.7],
        "wall_seconds": [12.0, 14.0],
        "tests": {
            "tests.unit.a.test_x.C.test_slow": {"seconds": [4.0, 6.0], "outcome": "ok"},
            "tests.unit.a.test_x.C.test_fast": {"seconds": [0.1, 0.1], "outcome": "ok"},
            "tests.integration.p.test_y.D.test_build": {"seconds": [5.0, 5.0], "outcome": "ok"},
            "tests.policy.q.test_z.E.test_skip": {"seconds": [0.0, 0.0], "outcome": "skip"},
        },
    }


class RenderTests(unittest.TestCase):
    def test_per_test_figure_is_the_median_over_runs(self):
        self.assertEqual(timing.median_seconds(sample()["tests"]["tests.unit.a.test_x.C.test_slow"]), 5.0)

    def test_ranking_is_by_descending_seconds_with_name_as_tiebreak(self):
        totals = {tid: timing.median_seconds(e) for tid, e in sample()["tests"].items()}
        ranked = [name for name, _ in timing.top(totals, 3)]
        self.assertEqual(
            ranked,
            [
                "tests.integration.p.test_y.D.test_build",
                "tests.unit.a.test_x.C.test_slow",
                "tests.unit.a.test_x.C.test_fast",
            ],
        )

    def test_top_n_limits_the_slowest_tables(self):
        text = timing.render_markdown(sample(), top_n=1)
        self.assertNotIn("test_fast", text)

    def test_unattributed_wall_time_is_wall_minus_test_sum(self):
        # median wall 13.0, tests sum 5.0 + 0.1 + 5.0 + 0.0 = 10.1
        self.assertIn("| Wall time not attributed to any test (fixtures, imports) | 2.9 |", timing.render_markdown(sample()))

    def test_outcomes_are_counted(self):
        self.assertIn("ok 3, skip 1", timing.render_markdown(sample()))

    def test_integration_time_is_excluded_from_the_fast_total(self):
        text = timing.render_markdown(sample())
        self.assertIn("Sum of per-test durations | 10.1 |", text)
        self.assertIn("the FAST tier still runs | 5.1 |", text)

    def test_tier_and_module_grouping(self):
        tid = "tests.unit.a.test_x.C.test_slow"
        self.assertEqual(timing.group_key(tid, 2), "tests.unit")
        self.assertEqual(timing.module_of(tid), "tests.unit.a.test_x")

    def test_from_json_renders_without_running_the_suite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.json"
            path.write_text(json.dumps(sample()), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(timing.main(["--from-json", str(path)]), 0)
        self.assertIn("Tests discovered | 4 |", out.getvalue())


def run_sample(seconds, outcome=None, detail=None):
    return {"seconds": seconds, "outcome": outcome or {}, "detail": detail or {}}


class MergeTests(unittest.TestCase):
    def test_a_failure_in_a_later_run_is_not_hidden_by_a_passing_first_run(self):
        first = run_sample({"t.A.test_x": 1.0}, {"t.A.test_x": "ok"})
        second = run_sample({"t.A.test_x": 2.0}, {"t.A.test_x": "error"}, {"t.A.test_x": "TimeoutExpired: 60"})
        entry = timing.merge_samples([first, second])["t.A.test_x"]
        self.assertEqual((entry["outcome"], entry["detail"]), ("error", "TimeoutExpired: 60"))
        self.assertEqual(entry["seconds"], [1.0, 2.0])

    def test_worst_outcome_wins_in_either_run_order(self):
        for order in ((("fail", "error")), (("error", "fail"))):
            runs = [run_sample({"t": 1.0}, {"t": o}) for o in order]
            self.assertEqual(timing.merge_samples(runs)["t"]["outcome"], "error")

    def test_fixture_outcomes_merge_worst_first_across_runs(self):
        name = "setUpClass (t.Broken)"
        runs = [
            {"fixtures": {name: {"outcome": "skip"}}},
            {"fixtures": {name: {"outcome": "error", "detail": "RuntimeError: boom"}}},
            {"fixtures": {}},
        ]
        self.assertEqual(timing.merge_fixtures(runs), {name: {"outcome": "error", "detail": "RuntimeError: boom"}})

    def test_collect_keeps_a_fixture_error_that_only_a_later_run_produced(self):
        def one_run(fixtures):
            return {
                "discovery_seconds": 0.1,
                "wall_seconds": 1.0,
                "seconds": {"t.ok": 0.5},
                "outcome": {"t.ok": "ok"},
                "detail": {},
                "fixtures": fixtures,
            }

        runs = iter([one_run({}), one_run({"setUpClass (t.B)": {"outcome": "error", "detail": "RuntimeError: boom"}})])
        with mock.patch.object(timing, "run_once", side_effect=lambda *_: next(runs)):
            data = timing.collect(timing.REPO_ROOT, 2)
        self.assertEqual(data["fixtures"], {"setUpClass (t.B)": {"outcome": "error", "detail": "RuntimeError: boom"}})
        self.assertFalse(timing.passed(data))

    def test_a_class_fixture_error_is_kept_apart_from_tests(self):
        class Broken(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError("boom")

            def test_never_runs(self):
                pass

        result = timing.TimingResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(Broken).run(result)
        self.assertEqual(result.outcome, {})
        ((name, entry),) = result.fixtures.items()
        self.assertIn("setUpClass", name)
        self.assertEqual(entry, {"outcome": "error", "detail": "RuntimeError: boom"})

    def test_a_class_fixture_skip_is_recorded_and_does_not_fail_the_run(self):
        class Skipped(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise unittest.SkipTest("not here")

            def test_x(self):
                pass

        result = timing.TimingResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(Skipped).run(result)
        self.assertEqual(result.outcome, {})
        self.assertEqual([f["outcome"] for f in result.fixtures.values()], ["skip"])
        data = {"tests": timing.merge_samples([run_sample(result.seconds, result.outcome)]), "fixtures": result.fixtures}
        self.assertTrue(timing.passed(data))

    def test_passed_is_false_when_only_a_fixture_errored(self):
        data = {"tests": timing.merge_samples([run_sample({"t.ok": 1.0}, {"t.ok": "ok"})]), "fixtures": {"setUpClass (t.B)": {"outcome": "error"}}}
        self.assertFalse(timing.passed(data))

    def test_exit_status_is_failure_when_only_a_fixture_errored(self):
        data = {
            "schema": timing.SCHEMA,
            "environment": {"python": "3", "platform": "p", "cpu_count": 1},
            "runs": 1,
            "discovery_seconds": [0.1],
            "wall_seconds": [1.0],
            "tests": timing.merge_samples([run_sample({"t.ok": 1.0}, {"t.ok": "ok"})]),
            "fixtures": {"setUpClass (tests.unit.x.Broken)": {"outcome": "error", "detail": "RuntimeError: boom"}},
        }
        with mock.patch.object(timing, "collect", return_value=data), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(timing.main([]), 1)

    def test_fixture_errors_do_not_enter_the_test_count_or_the_group_tables(self):
        data = {
            "schema": timing.SCHEMA,
            "environment": {"python": "3", "platform": "p", "cpu_count": 1},
            "runs": 1,
            "discovery_seconds": [0.1],
            "wall_seconds": [1.0],
            "tests": timing.merge_samples([run_sample({"tests.unit.a.test_x.C.test_ok": 1.0}, {"tests.unit.a.test_x.C.test_ok": "ok"})]),
            "fixtures": {"setUpClass (tests.unit.x.Broken)": {"outcome": "error", "detail": "RuntimeError: boom"}},
        }
        text = timing.render_markdown(data)
        self.assertIn("Tests discovered | 1 |", text)
        self.assertNotIn("| `setUpClass (tests.unit` |", text)
        self.assertIn("| Fixture outcomes (not tests) | error 1 |", text)
        self.assertIn("| `setUpClass (tests.unit.x.Broken)` | error | RuntimeError: boom |", text)

    def test_a_report_without_fixtures_renders_no_fixture_section(self):
        self.assertNotIn("Fixture outcomes", timing.render_markdown(sample()))


class OutcomeRecordingTests(unittest.TestCase):
    def run_case(self, case):
        result = timing.TimingResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(case).run(result)
        return result

    def test_a_failing_subtest_marks_the_parent_test_failed(self):
        class Case(unittest.TestCase):
            def test_parts(self):
                for n in (1, 2):
                    with self.subTest(n=n):
                        self.assertEqual(n, 1)

        result = self.run_case(Case)
        ((test_id, outcome),) = result.outcome.items()
        self.assertTrue(test_id.endswith("test_parts"))
        self.assertEqual(outcome, "fail")
        self.assertIn("AssertionError", result.detail[test_id])

    def test_an_erroring_subtest_marks_the_parent_test_errored(self):
        class Case(unittest.TestCase):
            def test_parts(self):
                with self.subTest(n=1):
                    raise ValueError("bad part")

        result = self.run_case(Case)
        ((_, outcome),) = result.outcome.items()
        self.assertEqual(outcome, "error")
        self.assertEqual(list(result.detail.values()), ["ValueError: bad part"])

    def test_a_later_failure_never_downgrades_an_earlier_error(self):
        class Case(unittest.TestCase):
            def test_parts(self):
                with self.subTest(n=1):
                    raise ValueError("first")
                self.fail("later")

        result = self.run_case(Case)
        self.assertEqual(list(result.outcome.values()), ["error"])
        self.assertEqual(list(result.detail.values()), ["ValueError: first"])

    def test_passing_subtests_leave_the_test_ok(self):
        class Case(unittest.TestCase):
            def test_parts(self):
                for n in (1, 2):
                    with self.subTest(n=n):
                        self.assertTrue(n)

        self.assertEqual(list(self.run_case(Case).outcome.values()), ["ok"])

    def test_an_unexpected_success_is_a_failure(self):
        class Case(unittest.TestCase):
            @unittest.expectedFailure
            def test_surprise(self):
                pass

        result = self.run_case(Case)
        self.assertEqual(list(result.outcome.values()), ["fail"])
        self.assertEqual(list(result.detail.values()), ["unexpected success"])

    def test_subtest_failures_reach_the_merged_entry_and_the_run_status(self):
        class Case(unittest.TestCase):
            def test_parts(self):
                with self.subTest(n=1):
                    self.fail("part")

        result = self.run_case(Case)
        tests = timing.merge_samples([run_sample(result.seconds, result.outcome, result.detail)])
        self.assertFalse(timing.passed({"tests": tests, "fixtures": result.fixtures}))


class OutputPathTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cwd = Path(self._tmp.name).resolve()
        self._origin = Path.cwd()
        self.addCleanup(os.chdir, self._origin)

    def data(self):
        return {
            "schema": timing.SCHEMA,
            "environment": {"python": "3", "platform": "p", "cpu_count": 1},
            "runs": 1,
            "discovery_seconds": [0.1],
            "wall_seconds": [1.0],
            "tests": timing.merge_samples([run_sample({"t.ok": 1.0}, {"t.ok": "ok"})]),
        }

    def test_relative_out_is_written_where_the_caller_ran_not_the_repo_root(self):
        def chdir_like_run_once(*_args):
            os.chdir(timing.REPO_ROOT)
            return self.data()

        os.chdir(self.cwd)
        with mock.patch.object(timing, "collect", side_effect=chdir_like_run_once), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(timing.main(["--out", "timing.json"]), 0)
        self.assertTrue((self.cwd / "timing.json").is_file())
        self.assertFalse((timing.REPO_ROOT / "timing.json").exists())

    def test_collect_restores_the_callers_working_directory(self):
        def chdir_like_run_once(repo, start_dir):
            os.chdir(repo)
            return run_sample({"t.ok": 0.1}, {"t.ok": "ok"}) | {"discovery_seconds": 0.0, "wall_seconds": 0.1}

        os.chdir(self.cwd)
        with mock.patch.object(timing, "run_once", side_effect=chdir_like_run_once):
            timing.collect(timing.REPO_ROOT, 1)
        self.assertEqual(Path.cwd().resolve(), self.cwd)


class ResultTests(unittest.TestCase):
    def test_outcomes_and_durations_are_recorded_per_test(self):
        class Case(unittest.TestCase):
            def test_ok(self):
                pass

            def test_fail(self):
                self.fail("x")

            @unittest.skip("s")
            def test_skip(self):
                pass

        result = timing.TimingResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(Case).run(result)
        outcomes = {tid.rsplit(".", 1)[1]: o for tid, o in result.outcome.items()}
        self.assertEqual(outcomes, {"test_ok": "ok", "test_fail": "fail", "test_skip": "skip"})
        self.assertTrue(all(s >= 0 for s in result.seconds.values()))

    def test_failure_detail_keeps_only_the_last_traceback_line(self):
        class Case(unittest.TestCase):
            def test_boom(self):
                raise ValueError("boom detail")

        result = timing.TimingResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(Case).run(result)
        (detail,) = result.detail.values()
        self.assertEqual(detail, "ValueError: boom detail")


if __name__ == "__main__":
    unittest.main()
