#!/usr/bin/env python3
"""Behavioural coverage for the benchmark severity-accuracy metric (Issue #56).

Contract: docs/benchmark/severity-accuracy.md. Driven through the reference
classifier (tests/reference/benchmark_severity.py), which takes the #55
pairing verbatim (tests/reference/benchmark_metrics.py) and, through it,
the single reference matcher (tests/reference/benchmark_match.py, #54) —
this module never defines a second pairing or match relation.

What is proven here:

1. every §7 worked example produces the documented
   matched / severity_exact / over_severity / under_severity (data-driven),
   and two runs agree;
2. exact + over + under == matched for every case (§3 partition);
3. `severity` lists (permitted variance) and `any_of` member resolution
   change the reference set exactly as §1/§3 state;
4. the aggregate (§4) is a plain sum with one exact-rational rate, and the
   report section (§5) renders deltas alongside without a score.

Duplicate noise (#57) and any blended score / precision / recall are out of
scope.
"""

from __future__ import annotations

import unittest
from fractions import Fraction

from tests.reference import benchmark_fixture as bf
from tests.reference import benchmark_runner as br
from tests.reference import benchmark_severity as bsev
from tests.support.paths import REPO_ROOT


# ── builders ────────────────────────────────────────────────────────────


def _exp(
    *,
    key: str,
    path: str = "auth/login.py",
    lines: tuple[int, int] = (40, 40),
    claim: str = "a cause leads to a faulty behavior",
    defect_kind: str = "command-injection",
    required: bool = True,
    severity: str | tuple[str, ...] = "P1",
) -> bf.ExpectedFinding:
    severities = (severity,) if isinstance(severity, str) else tuple(severity)
    return bf.ExpectedFinding(
        key=key,
        severities=severities,
        required=required,
        location={"location_intent": "line", "path": path, "lines": {"start": lines[0], "end": lines[1]}},
        claim=claim,
        defect_kind=defect_kind,
    )


def _member(*, key: str, defect_kind: str, severity: str, path: str = "report/export.py") -> bf.ExpectedFinding:
    return bf.ExpectedFinding(
        key=key,
        severities=(severity,),
        required=True,
        location={"location_intent": "line", "path": path, "lines": {"start": 88, "end": 88}},
        claim=f"{defect_kind} at the export path",
        defect_kind=defect_kind,
    )


def _any_of(key: str, *members: bf.ExpectedFinding, required: bool = True) -> bf.ExpectedFinding:
    return bf.ExpectedFinding(key=key, severities=(), required=required, members=tuple(members))


def _prod(
    *,
    severity: str = "P1",
    path: str = "auth/login.py",
    line: int = 40,
    defect_kind: str = "command-injection",
    claim: str | None = None,
) -> br.ProducedFinding:
    return br.ProducedFinding(
        severity=severity,
        location={"path": path, "line": line},
        claim=claim,
        extra={"defect_kind": defect_kind},
    )


def _case(*findings: bf.ExpectedFinding, completeness: str = "exhaustive", case_id: str = "c1") -> bf.BenchmarkCase:
    return bf.BenchmarkCase(
        format="benchmark-case/v1",
        id=case_id,
        title="t",
        input={"patch": "--- a\n+++ b\n"},
        decision=None,
        findings_completeness=completeness,
        findings=tuple(findings),
    )


def _executed(case: bf.BenchmarkCase, *produced: br.ProducedFinding) -> br.CaseResult:
    return br.CaseResult(case.id, "patch", "executed", produced_findings=tuple(produced))


def _errored(case: bf.BenchmarkCase) -> br.CaseResult:
    return br.CaseResult(case.id, "patch", "error", error="reviewer-adapter-raised")


_R1 = dict(key="r1", path="auth/login.py", lines=(40, 40), defect_kind="command-injection")
_R2 = dict(key="r2", path="report/export.py", lines=(88, 88), defect_kind="path-traversal")


def _p_r1(severity: str) -> br.ProducedFinding:
    return _prod(severity=severity, path="auth/login.py", line=40, defect_kind="command-injection")


def _p_r2(severity: str) -> br.ProducedFinding:
    return _prod(severity=severity, path="report/export.py", line=88, defect_kind="path-traversal")


# ── §7 worked examples, verbatim ───────────────────────────────────────

# Each row: (name, case, case_result, matched, exact, over, under, exact_rate)
def _worked_examples():
    c_two = _case(_exp(**_R1, severity="P1"), _exp(**_R2, severity="P0"))

    # 1 — every matched finding at the expected severity
    yield ("1 all exact", c_two, _executed(c_two, _p_r1("P1"), _p_r2("P0")), 2, 2, 0, 0, Fraction(1))

    # 2 — reviewer over-calls a P1 as P0
    c_one_p1 = _case(_exp(**_R1, severity="P1"))
    yield ("2 over", c_one_p1, _executed(c_one_p1, _p_r1("P0")), 1, 0, 1, 0, Fraction(0))

    # 3 — reviewer under-calls a P0 as P1
    c_one_p0 = _case(_exp(**_R1, severity="P0"))
    yield ("3 under", c_one_p0, _executed(c_one_p0, _p_r1("P1")), 1, 0, 0, 1, Fraction(0))

    # 4 — one exact, one under-severity (P0 reported P2)
    c_two_b = _case(_exp(**_R1, severity="P1"), _exp(**_R2, severity="P0"))
    yield ("4 mixed", c_two_b, _executed(c_two_b, _p_r1("P1"), _p_r2("P2")), 2, 1, 0, 1, Fraction(1, 2))

    # 5 — permitted severity variance: P2 is in the band -> exact
    c_var = _case(_exp(**_R1, severity=("P1", "P2")))
    yield ("5 variance exact", c_var, _executed(c_var, _p_r1("P2")), 1, 1, 0, 0, Fraction(1))

    # 6 — P0 above the whole permitted band -> over-severity
    yield ("6 variance over", c_var, _executed(c_var, _p_r1("P0")), 1, 0, 1, 0, Fraction(0))

    # 7 — empty matched set (errored)
    yield ("7 errored empty", c_two, _errored(c_two), 0, 0, 0, 0, None)

    # 8 — any_of satisfied via the P2 member; produced P1 -> over
    c_grp = _case(
        _any_of(
            "grp",
            _member(key="m1", defect_kind="path-traversal", severity="P1"),
            _member(key="m2", defect_kind="missing-input-validation", severity="P2"),
        )
    )
    grp_prod = _prod(severity="P1", path="report/export.py", line=88, defect_kind="missing-input-validation")
    yield ("8 any_of member ref", c_grp, _executed(c_grp, grp_prod), 1, 0, 1, 0, Fraction(0))

    # 9 — a paired optional entry is in the matched set
    c_opt = _case(_exp(**_R1, severity="P2", required=False))
    yield ("9 optional matched", c_opt, _executed(c_opt, _p_r1("P2")), 1, 1, 0, 0, Fraction(1))


WORKED = list(_worked_examples())


class WorkedExampleTests(unittest.TestCase):
    def test_every_worked_example_counts_as_documented(self) -> None:
        for name, case, result, matched, exact, over, under, rate in WORKED:
            with self.subTest(row=name):
                m = bsev.compute_case_severity_accuracy(case, result)
                self.assertEqual(
                    (m.matched, m.severity_exact, m.over_severity, m.under_severity, m.exact_rate),
                    (matched, exact, over, under, rate),
                    m.as_dict(),
                )

    def test_exact_over_under_partition_the_matched_set(self) -> None:
        for name, case, result, *_ in WORKED:
            with self.subTest(row=name):
                m = bsev.compute_case_severity_accuracy(case, result)
                self.assertEqual(m.severity_exact + m.over_severity + m.under_severity, m.matched)

    def test_worked_examples_are_deterministic(self) -> None:
        first = [bsev.compute_case_severity_accuracy(c, r).as_dict() for _, c, r, *_ in WORKED]
        second = [bsev.compute_case_severity_accuracy(c, r).as_dict() for _, c, r, *_ in WORKED]
        self.assertEqual(first, second)

    def test_mismatches_carry_direction_and_are_fixture_ordered(self) -> None:
        _, case, result, *_ = WORKED[3]  # row 4: r1 exact, r2 under
        m = bsev.compute_case_severity_accuracy(case, result)
        self.assertEqual([mm["key"] for mm in m.mismatches], ["r2"])
        self.assertEqual(m.mismatches[0]["direction"], "under")
        self.assertEqual(m.mismatches[0]["expected"], ["P0"])
        self.assertEqual(m.mismatches[0]["produced"], "P2")


class EmptyAndErroredTests(unittest.TestCase):
    def test_errored_case_has_empty_matched_set_and_null_rate(self) -> None:
        case = _case(_exp(**_R1, severity="P1"))
        m = bsev.compute_case_severity_accuracy(case, _errored(case))
        self.assertEqual(m.status, "errored")
        self.assertEqual((m.matched, m.severity_exact, m.over_severity, m.under_severity), (0, 0, 0, 0))
        self.assertIsNone(m.exact_rate)

    def test_unmatched_findings_do_not_enter_the_metric(self) -> None:
        # A required entry the reviewer never matched: no severity to score.
        case = _case(_exp(**_R1, severity="P0"))
        unrelated = _prod(severity="P0", path="z/z.py", line=9, defect_kind="resource-leak")
        m = bsev.compute_case_severity_accuracy(case, _executed(case, unrelated))
        self.assertEqual(m.matched, 0)
        self.assertIsNone(m.exact_rate)

    def test_missing_result_for_a_case_is_treated_as_errored(self) -> None:
        case = _case(_exp(**_R1, severity="P1"), case_id="only")
        run = bsev.compute_run_severity_accuracy([case], [])
        self.assertEqual(run.per_case[0].status, "errored")
        self.assertEqual(run.per_case[0].matched, 0)


class AggregateAndSectionTests(unittest.TestCase):
    def _run(self):
        exact_case = _case(_exp(**_R1, severity="P1"), case_id="exact")
        over_case = _case(_exp(**_R1, severity="P1"), case_id="over")
        under_case = _case(_exp(**_R1, severity="P0"), case_id="under")
        cases = [exact_case, over_case, under_case]
        results = [
            _executed(exact_case, _p_r1("P1")),
            _executed(over_case, _p_r1("P0")),
            _executed(under_case, _p_r1("P1")),
        ]
        return bsev.compute_run_severity_accuracy(cases, results)

    def test_aggregate_is_a_plain_sum_with_one_rational_rate(self) -> None:
        agg = self._run().aggregate
        self.assertEqual(agg.total_matched, 3)
        self.assertEqual(agg.total_severity_exact, 1)
        self.assertEqual(agg.total_over_severity, 1)
        self.assertEqual(agg.total_under_severity, 1)
        self.assertEqual(agg.exact_rate, Fraction(1, 3))
        self.assertEqual(agg.cases_with_severity_mismatch, 2)

    def test_as_dict_renders_rate_as_canonical_string_or_null(self) -> None:
        d = self._run().as_dict()
        self.assertEqual(d["aggregate"]["exact_rate"], "1/3")
        errored = bsev.compute_run_severity_accuracy(
            [_case(_exp(**_R1), case_id="e")], []
        )
        self.assertIsNone(errored.as_dict()["aggregate"]["exact_rate"])

    def test_section_without_baseline_is_just_the_candidate(self) -> None:
        section = bsev.severity_section(self._run())
        self.assertEqual(set(section), {"candidate"})

    def test_section_with_baseline_renders_deltas_alongside(self) -> None:
        good_case = _case(_exp(**_R1, severity="P1"), case_id="c1")
        baseline = bsev.compute_run_severity_accuracy([good_case], [_executed(good_case, _p_r1("P0"))])  # over
        candidate = bsev.compute_run_severity_accuracy([good_case], [_executed(good_case, _p_r1("P1"))])  # exact
        section = bsev.severity_section(candidate, baseline=baseline)
        row = section["cases"][0]
        self.assertEqual(row["id"], "c1")
        self.assertEqual(row["over_severity"], {"baseline": 1, "candidate": 0, "delta": -1})
        self.assertEqual(row["severity_exact"], {"baseline": 0, "candidate": 1, "delta": 1})
        self.assertEqual(
            section["aggregate"]["total_over_severity"], {"baseline": 1, "candidate": 0, "delta": -1}
        )
        self.assertEqual(section["aggregate"]["exact_rate"], {"baseline": "0", "candidate": "1"})

    def test_section_added_and_removed_case_ids(self) -> None:
        a = _case(_exp(**_R1, severity="P1"), case_id="a")
        b = _case(_exp(**_R1, severity="P1"), case_id="b")
        baseline = bsev.compute_run_severity_accuracy([a], [_executed(a, _p_r1("P1"))])
        candidate = bsev.compute_run_severity_accuracy([b], [_executed(b, _p_r1("P1"))])
        section = bsev.severity_section(candidate, baseline=baseline)
        self.assertEqual(section["added_case_ids"], ["b"])
        self.assertEqual(section["removed_case_ids"], ["a"])
        self.assertEqual(section["cases"], [])

    def test_section_is_deterministic(self) -> None:
        run = self._run()
        self.assertEqual(bsev.severity_section(run), bsev.severity_section(run))


class ReferenceModuleTests(unittest.TestCase):
    def test_module_is_declared_test_only(self) -> None:
        head = (REPO_ROOT / "tests" / "reference" / "benchmark_severity.py").read_text(encoding="utf-8")[:700]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_classifier_consumes_the_single_pairing_and_matcher(self) -> None:
        raw = (REPO_ROOT / "tests" / "reference" / "benchmark_severity.py").read_text(encoding="utf-8")
        self.assertIn("from tests.reference import benchmark_metrics as bmet", raw)
        self.assertIn("from tests.reference import benchmark_match as bm", raw)
        self.assertIn("defines no second pairing or match relation", raw)

    def test_pairing_is_taken_verbatim_not_recomputed(self) -> None:
        # A NEAR_MISS never pairs, so it is never severity-scored even when
        # its severity would be "wrong". Same path/line (EXACT location) but
        # unrelated claims and no shared defect_kind -> NEAR_MISS, not MATCH.
        near = _case(
            _exp(key="r1", severity="P0", claim="off by one in pagination page bounds", defect_kind="off-by-one")
        )
        pf = br.ProducedFinding(
            severity="P2",
            location={"path": "auth/login.py", "line": 40},
            claim="pagination page boundary calculation is wrong",
        )
        m = bsev.compute_case_severity_accuracy(near, _executed(near, pf))
        self.assertEqual(m.matched, 0)


if __name__ == "__main__":
    unittest.main()
