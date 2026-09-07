#!/usr/bin/env python3
"""Behavioural coverage for the benchmark regression report (Issue #53).

Contract: docs/benchmark/regression-report.md. Driven through the single
test-only reference report (tests/reference/benchmark_report.py); this
module never defines a second one. It consumes runner results built with
the reference runner (tests/reference/benchmark_runner.py, Issue #52).

What is proven here:

1. two equal run results produce a well-formed, stable report with every
   count zero and ``has_regressions`` false;
2. the issue's Validation section: a seeded regression (a case that stops
   producing a finding the baseline produced, and a case whose execution
   flips ``executed`` -> ``error``) is classified ``regression`` and is
   reported distinctly from an ``improvement``;
3. ``mixed`` / ambiguous cases fail closed and are grouped with the
   regressions;
4. the identity guard: a ``corpus_id`` mismatch is a report error, not a
   silent cross-corpus comparison;
5. output is deterministic and byte-identical for identical inputs;
6. the report never writes the baseline (no promotion path on it).

Scoring a run against the fixtures' ``expected`` blocks — precision,
recall, pass rates — is out of scope (Issue #41).
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.reference import benchmark_report as brp
from tests.reference import benchmark_runner as br
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus"


def _pf(severity: str, path: str, *, claim: str = "c", defect: str | None = None) -> br.ProducedFinding:
    extra = {"defect_kind": defect} if defect else {}
    return br.ProducedFinding(severity=severity, location={"path": path}, claim=claim, extra=extra)


def _case(cid: str, *findings: br.ProducedFinding, status: str = "executed", error: str | None = None) -> br.CaseResult:
    if status == "executed":
        return br.CaseResult(cid, "patch", "executed", produced_findings=tuple(findings))
    return br.CaseResult(cid, "patch", "error", error=error)


def _baseline(*cases: br.CaseResult, corpus_id: str = "corpus-1", adapter_id: str = "base-adapter") -> brp.BaselineArtifact:
    return brp.BaselineArtifact(results=tuple(cases), corpus_id=corpus_id, adapter_id=adapter_id)


def _compare(baseline: brp.BaselineArtifact, candidate: list[br.CaseResult], *, corpus_id: str = "corpus-1", adapter_id: str = "cand-adapter"):
    return brp.compare(
        baseline, candidate, candidate_corpus_id=corpus_id, candidate_adapter_id=adapter_id
    )


class EqualRunsTests(unittest.TestCase):
    def test_equal_runs_produce_an_empty_stable_report(self) -> None:
        cases = [_case("a", _pf("P1", "x.py")), _case("b")]
        report = _compare(_baseline(*cases), [c for c in cases])
        self.assertFalse(report.has_regressions)
        self.assertEqual(
            report.counts,
            {"regression": 0, "improvement": 0, "mixed": 0, "unchanged": 2, "added": 0, "removed": 0},
        )
        self.assertEqual(report.aggregate_severity_delta, {"P0": 0, "P1": 0, "P2": 0})
        self.assertEqual(report.as_dict()["cases"]["regression"], [])


class SeededRegressionTests(unittest.TestCase):
    def test_dropped_finding_is_a_regression_distinct_from_improvement(self) -> None:
        baseline = _baseline(
            _case("keeps", _pf("P0", "auth.py", defect="cmd-injection")),
            _case("gains"),
        )
        candidate = [
            _case("keeps"),  # regression: the P0 finding is gone
            _case("gains", _pf("P2", "util.py")),  # improvement: a new finding
        ]
        report = _compare(baseline, candidate)

        self.assertTrue(report.has_regressions)
        self.assertEqual(report.counts["regression"], 1)
        self.assertEqual(report.counts["improvement"], 1)

        as_dict = report.as_dict()
        self.assertEqual([c["id"] for c in as_dict["cases"]["regression"]], ["keeps"])
        self.assertEqual([c["id"] for c in as_dict["cases"]["improvement"]], ["gains"])
        # the two classes are rendered as separate groups
        self.assertNotIn("gains", [c["id"] for c in as_dict["cases"]["regression"]])
        self.assertEqual(as_dict["cases"]["regression"][0]["dropped"][0]["severity"], "P0")
        self.assertEqual(report.total_dropped, 1)
        self.assertEqual(report.total_gained, 1)

    def test_execution_status_flip_to_error_is_a_regression(self) -> None:
        report = _compare(
            _baseline(_case("c", _pf("P1", "x.py"))),
            [_case("c", status="error", error="reviewer-adapter-raised")],
        )
        self.assertTrue(report.has_regressions)
        self.assertEqual(report.counts["regression"], 1)
        self.assertEqual(report.as_dict()["cases"]["regression"][0]["status"]["candidate_error"], "reviewer-adapter-raised")

    def test_execution_status_recovery_is_an_improvement(self) -> None:
        report = _compare(
            _baseline(_case("c", status="error", error="patch-did-not-apply")),
            [_case("c", _pf("P1", "x.py"))],
        )
        self.assertFalse(report.has_regressions)
        self.assertEqual(report.counts["improvement"], 1)

    def test_retained_finding_severity_rise_is_a_regression_fall_is_improvement(self) -> None:
        rose = _compare(
            _baseline(_case("c", _pf("P2", "x.py", defect="dup"))),
            [_case("c", _pf("P0", "x.py", defect="dup"))],
        )
        self.assertEqual(rose.counts["regression"], 1)
        self.assertEqual(rose.as_dict()["cases"]["regression"][0]["retained"][0]["candidate_severity"], "P0")

        fell = _compare(
            _baseline(_case("c", _pf("P0", "x.py", defect="dup"))),
            [_case("c", _pf("P2", "x.py", defect="dup"))],
        )
        self.assertEqual(fell.counts["improvement"], 1)


class MixedAndFailClosedTests(unittest.TestCase):
    def test_drop_and_gain_in_one_case_is_mixed_and_grouped_with_regressions(self) -> None:
        report = _compare(
            _baseline(_case("c", _pf("P1", "old.py", defect="a"))),
            [_case("c", _pf("P1", "new.py", defect="b"))],
        )
        self.assertEqual(report.counts["mixed"], 1)
        self.assertEqual(report.counts["regression"], 0)
        self.assertTrue(report.has_regressions, "mixed fails closed")

    def test_ambiguous_stability_key_is_mixed(self) -> None:
        # two findings collapse to the same coarse key within a run
        dup = _pf("P1", "x.py", claim="same")
        report = _compare(
            _baseline(_case("c", dup, dup)),
            [_case("c", dup)],
        )
        self.assertEqual(report.counts["mixed"], 1)
        self.assertTrue(report.has_regressions)


class IdentityGuardTests(unittest.TestCase):
    def test_corpus_id_mismatch_is_a_report_error(self) -> None:
        with self.assertRaises(brp.ReportError):
            brp.compare(
                _baseline(_case("c"), corpus_id="corpus-1"),
                [_case("c")],
                candidate_corpus_id="corpus-2",
                candidate_adapter_id="x",
            )

    def test_added_and_removed_cases_are_reported_not_dropped(self) -> None:
        report = _compare(
            _baseline(_case("stays"), _case("goes")),
            [_case("stays"), _case("arrives")],
        )
        self.assertEqual(report.added_case_ids, ("arrives",))
        self.assertEqual(report.removed_case_ids, ("goes",))
        # a removed case surfaces with the regressions; an added case does not
        self.assertTrue(report.has_regressions)
        self.assertEqual(report.counts["regression"], 0)

    def test_adapter_id_difference_is_recorded_not_gated(self) -> None:
        report = _compare(_baseline(_case("c")), [_case("c")], adapter_id="new-adapter")
        ident = report.as_dict()["identity"]
        self.assertEqual(ident["baseline_adapter_id"], "base-adapter")
        self.assertEqual(ident["candidate_adapter_id"], "new-adapter")


class DeterministicOutputTests(unittest.TestCase):
    def test_report_is_byte_identical_for_identical_inputs(self) -> None:
        baseline = _baseline(_case("b", _pf("P1", "b.py")), _case("a", _pf("P0", "a.py")), _case("c"))
        candidate = [_case("a"), _case("b", _pf("P1", "b.py")), _case("c", _pf("P2", "c.py"))]
        one = json.dumps(_compare(baseline, candidate).as_dict(), sort_keys=True)
        two = json.dumps(_compare(baseline, candidate).as_dict(), sort_keys=True)
        self.assertEqual(one, two)

    def test_cases_are_ordered_by_id_within_a_class(self) -> None:
        baseline = _baseline(
            _case("zeta", _pf("P1", "z.py")),
            _case("alpha", _pf("P1", "a.py")),
        )
        candidate = [_case("zeta"), _case("alpha")]  # both regress
        ids = [c["id"] for c in _compare(baseline, candidate).as_dict()["cases"]["regression"]]
        self.assertEqual(ids, ["alpha", "zeta"])

    def test_created_at_is_not_an_input_to_any_delta(self) -> None:
        a = brp.BaselineArtifact(results=(_case("c"),), corpus_id="k", adapter_id="x", created_at="2026-01-01")
        b = brp.BaselineArtifact(results=(_case("c"),), corpus_id="k", adapter_id="x", created_at="2026-09-09")
        self.assertEqual(
            brp.compare(a, [_case("c")], candidate_corpus_id="k", candidate_adapter_id="y").as_dict(),
            brp.compare(b, [_case("c")], candidate_corpus_id="k", candidate_adapter_id="y").as_dict(),
        )


class BaselineIsNeverWrittenTests(unittest.TestCase):
    def test_report_has_no_baseline_promotion_path(self) -> None:
        report = _compare(_baseline(_case("c")), [_case("c")])
        for attr in ("write", "promote", "save", "update_baseline"):
            self.assertFalse(hasattr(report, attr), f"report exposes {attr!r}")

    def test_promoting_requires_a_completed_run(self) -> None:
        failed = br.RunResult((), ok=False, error="corpus-parse-failed")
        with self.assertRaises(brp.ReportError):
            brp.BaselineArtifact.from_run(failed, corpus_id="k", adapter_id="x")

    def test_compare_does_not_mutate_the_baseline_artifact(self) -> None:
        baseline = _baseline(_case("c", _pf("P1", "x.py")))
        before = baseline.results
        _compare(baseline, [_case("c")])
        self.assertIs(baseline.results, before)


class EndToEndWithReferenceRunnerTests(unittest.TestCase):
    """The report consumes real runner output (Issue #52) unchanged."""

    def _run(self, reviewer) -> br.RunResult:
        with tempfile.TemporaryDirectory() as tmp:
            return br.run_corpus(CORPUS_DIR, reviewer, workspace_parent=Path(tmp))

    def test_seeded_regression_against_a_real_corpus_run(self) -> None:
        corpus_id = brp.corpus_digest(CORPUS_DIR)

        def baseline_reviewer(_ws: Path):
            return [br.ProducedFinding(severity="P0", location={"path": "app/x.py"}, claim="found", extra={"defect_kind": "bug"})]

        def regressed_reviewer(_ws: Path):
            return []  # the reviewer stopped finding anything

        base_run = self._run(baseline_reviewer)
        cand_run = self._run(regressed_reviewer)
        baseline = brp.BaselineArtifact.from_run(base_run, corpus_id=corpus_id, adapter_id="v1")

        report = brp.compare(
            baseline, cand_run, candidate_corpus_id=corpus_id, candidate_adapter_id="v2"
        )
        self.assertTrue(report.has_regressions)
        self.assertEqual(report.counts["regression"], len(base_run.case_results))
        self.assertEqual(report.counts["improvement"], 0)

    def test_no_change_against_a_real_corpus_run_has_no_regressions(self) -> None:
        corpus_id = brp.corpus_digest(CORPUS_DIR)

        def steady(_ws: Path):
            return []

        base_run = self._run(steady)
        cand_run = self._run(steady)
        baseline = brp.BaselineArtifact.from_run(base_run, corpus_id=corpus_id, adapter_id="v1")
        report = brp.compare(
            baseline, cand_run, candidate_corpus_id=corpus_id, candidate_adapter_id="v1"
        )
        self.assertFalse(report.has_regressions)
        self.assertEqual(report.counts["unchanged"], len(base_run.case_results))


class ReferenceModuleTests(unittest.TestCase):
    def test_module_is_declared_test_only(self) -> None:
        head = (REPO_ROOT / "tests" / "reference" / "benchmark_report.py").read_text(
            encoding="utf-8"
        )[:600]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_report_consumes_the_single_reference_runner(self) -> None:
        raw = (REPO_ROOT / "tests" / "reference" / "benchmark_report.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("from tests.reference import benchmark_runner as br", raw)


if __name__ == "__main__":
    unittest.main()
