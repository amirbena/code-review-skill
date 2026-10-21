"""Tests for the per-test timing report."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

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
