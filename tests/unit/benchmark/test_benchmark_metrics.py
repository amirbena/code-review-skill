#!/usr/bin/env python3
"""Behavioural coverage for the benchmark missed/incorrect finding metrics (Issue #55).

Contract: docs/benchmark/missed-and-incorrect-findings.md. Driven through
the single reference counter (tests/reference/benchmark/benchmark_metrics.py), which
delegates every pairwise decision to the single reference matcher
(tests/reference/benchmark/benchmark_match.py, #54) — this module never defines a
second match relation. Expected findings use the bf.ExpectedFinding shape
(#50); produced findings and per-case results use br.ProducedFinding /
br.CaseResult (#52).

What is proven here:

1. every §8 worked example produces the documented
   false_negatives / false_positives / near_misses (data-driven), and two
   runs agree;
2. the pairing (§2) is greedy in fixture document order and one-to-one;
3. `match: optional`, `any_of`, `alternatives`, and `findings_completeness`
   change the accounting exactly as §3–§4 state;
4. the aggregate (§5) is a plain sum, and the report section (§6) renders
   metrics alongside per-case deltas without a score.

Severity accuracy (#56), duplicate noise (#57), and any blended
score / precision / recall are out of scope.
"""

from __future__ import annotations

import unittest

from tests.reference.benchmark import benchmark_fixture as bf
from tests.reference.benchmark import benchmark_match as bm
from tests.reference.benchmark import benchmark_metrics as bmet
from tests.reference.benchmark import benchmark_runner as br
from tests.support.paths import REPO_ROOT


# ── builders ────────────────────────────────────────────────────────────


def _exp(
    *,
    key: str,
    path: str = "auth/login.py",
    intent: str = "line",
    symbol: str | None = None,
    lines: tuple[int, int] | None = None,
    claim: str = "a cause leads to a faulty behavior",
    defect_kind: str | None = None,
    required: bool = True,
    severity: str = "P1",
    alternatives: tuple[dict, ...] = (),
) -> bf.ExpectedFinding:
    location: dict = {"location_intent": intent, "path": path}
    if symbol is not None:
        location["symbol"] = symbol
    if lines is not None:
        location["lines"] = {"start": lines[0], "end": lines[1]}
    return bf.ExpectedFinding(
        key=key,
        severities=(severity,),
        required=required,
        location=location,
        claim=claim,
        defect_kind=defect_kind,
        alternatives=alternatives,
    )


def _any_of(key: str, *members: bf.ExpectedFinding, required: bool = True) -> bf.ExpectedFinding:
    return bf.ExpectedFinding(key=key, severities=(), required=required, members=tuple(members))


def _prod(
    *,
    severity: str = "P1",
    path: str = "auth/login.py",
    symbol: str | None = None,
    line: int | None = None,
    claim: str | None = None,
    defect_kind: str | None = None,
) -> br.ProducedFinding:
    location: dict = {"path": path}
    if symbol is not None:
        location["symbol"] = symbol
    if line is not None:
        location["line"] = line
    extra = {"defect_kind": defect_kind} if defect_kind else {}
    return br.ProducedFinding(severity=severity, location=location, claim=claim, extra=extra)


def _case(
    *findings: bf.ExpectedFinding,
    completeness: str = "exhaustive",
    case_id: str = "c1",
) -> bf.BenchmarkCase:
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


_CMD = "unsanitized name reaches a shell true command injection"
_CMD_SUBSET = "unsanitized name reaches a shell true command"
_REL = "off by one in pagination page bounds"  # RELATED to the pagination claim below
_PAG = "slice end off by one page repeats one row from the next page"


# ── §8 worked examples, verbatim ────────────────────────────────────────

# Each row: (name, case, case_result, want_fn, want_fp, want_near,
#            want_absorbed, want_tolerated)
def _worked_examples():
    # 1 — perfect review
    c1 = _case(
        _exp(key="r1", symbol="authenticate", lines=(40, 40), claim=_CMD, defect_kind="command-injection"),
        _exp(key="r2", path="report/export.py", lines=(88, 88), claim="x escapes y path traversal", defect_kind="path-traversal"),
    )
    r1 = _executed(
        c1,
        _prod(symbol="authenticate", line=41, defect_kind="command-injection"),
        _prod(path="report/export.py", line=88, defect_kind="path-traversal"),
    )
    yield ("1 perfect", c1, r1, 0, 0, 0, 0, 0)

    # 2 — one required entry missed
    yield (
        "2 one missed",
        c1,
        _executed(c1, _prod(symbol="authenticate", line=41, defect_kind="command-injection")),
        1, 0, 0, 0, 0,
    )

    # 3 — an unexpected finding is a false positive (exhaustive)
    c3 = _case(_exp(key="r1", symbol="authenticate", lines=(40, 40), claim=_CMD, defect_kind="command-injection"))
    yield (
        "3 unexpected finding",
        c3,
        _executed(
            c3,
            _prod(symbol="authenticate", line=41, defect_kind="command-injection"),
            _prod(path="db/pool.py", line=7, claim="connection pool is never closed", defect_kind="resource-leak"),
        ),
        0, 1, 0, 0, 0,
    )

    # 4 — NEAR_MISS: one FN, zero FP, one near-miss (anti-double-count)
    c4 = _case(_exp(key="r1", lines=(15, 15), claim=_PAG))
    yield (
        "4 near miss",
        c4,
        _executed(c4, _prod(line=15, claim=_REL)),
        1, 0, 1, 0, 0,
    )

    # 5 — unsatisfied optional entry is not a miss
    c5 = _case(_exp(key="opt", lines=(3, 3), claim="a minor smell", required=False))
    yield ("5 optional unmet", c5, _executed(c5), 0, 0, 0, 0, 0)

    # 6 — matched optional entry is consumed, not a false positive
    yield (
        "6 optional matched",
        c5,
        _executed(c5, _prod(line=3, claim="a minor smell")),
        0, 0, 0, 0, 0,
    )

    # 7 — any_of satisfied once; the second corresponding finding is absorbed
    c7 = _case(
        _any_of(
            "grp",
            _exp(key="m1", path="report/export.py", lines=(88, 88), claim="path escapes the export dir path traversal", defect_kind="path-traversal"),
            _exp(key="m2", path="report/export.py", lines=(88, 88), claim="export path arg is not validated", defect_kind="missing-input-validation"),
        )
    )
    yield (
        "7 any_of absorbed extra",
        c7,
        _executed(
            c7,
            _prod(path="report/export.py", line=88, defect_kind="missing-input-validation"),
            _prod(path="report/export.py", line=88, defect_kind="path-traversal"),
        ),
        0, 0, 0, 1, 0,
    )

    # 8 — at-least tolerates the unexpected finding; required entry still missed
    c8 = _case(
        _exp(key="r1", symbol="authenticate", lines=(40, 40), claim=_CMD, defect_kind="command-injection"),
        completeness="at-least",
    )
    yield (
        "8 at-least tolerates",
        c8,
        _executed(c8, _prod(path="db/pool.py", line=7, claim="pool never closed", defect_kind="resource-leak")),
        1, 0, 0, 0, 1,
    )

    # 9 — errored case: every required entry missed, no false positives
    yield ("9 errored", c1, _errored(c1), 2, 0, 0, 0, 0)


WORKED = list(_worked_examples())


class WorkedExampleTests(unittest.TestCase):
    def test_every_worked_example_counts_as_documented(self) -> None:
        for name, case, result, fn, fp, near, absorbed, tolerated in WORKED:
            with self.subTest(row=name):
                m = bmet.compute_case_metrics(case, result)
                self.assertEqual(
                    (m.false_negatives, m.false_positives, m.near_misses,
                     m.absorbed_extra_match, m.tolerated_unexpected),
                    (fn, fp, near, absorbed, tolerated),
                    m.as_dict(),
                )

    def test_worked_examples_are_deterministic(self) -> None:
        first = [bmet.compute_case_metrics(c, r).as_dict() for _, c, r, *_ in WORKED]
        second = [bmet.compute_case_metrics(c, r).as_dict() for _, c, r, *_ in WORKED]
        self.assertEqual(first, second)

    def test_near_miss_is_a_subset_of_false_negatives(self) -> None:
        for name, case, result, *_ in WORKED:
            with self.subTest(row=name):
                m = bmet.compute_case_metrics(case, result)
                self.assertLessEqual(m.near_misses, m.false_negatives)

    def test_errored_case_is_flagged_and_produces_no_false_positives(self) -> None:
        _, case, _, *_ = WORKED[0]
        m = bmet.compute_case_metrics(case, _errored(case))
        self.assertEqual(m.status, "errored")
        self.assertEqual(m.false_positives, 0)
        self.assertEqual(m.false_negatives, 2)
        self.assertEqual(m.missed_keys, ("r1", "r2"))


class PairingTests(unittest.TestCase):
    def test_pairing_is_one_to_one(self) -> None:
        case = _case(
            _exp(key="r1", symbol="authenticate", lines=(40, 40), claim=_CMD, defect_kind="command-injection"),
            _exp(key="r2", path="report/export.py", lines=(88, 88), claim="path traversal here", defect_kind="path-traversal"),
        )
        produced = [
            _prod(symbol="authenticate", line=40, defect_kind="command-injection"),
            _prod(path="report/export.py", line=88, defect_kind="path-traversal"),
        ]
        pairing = bmet.resolve_pairing(case, produced)
        self.assertEqual(pairing.paired, {"r1": 0, "r2": 1})
        self.assertEqual(pairing.unconsumed_indices, ())
        self.assertEqual(pairing.unpaired_entry_keys, ())

    def test_document_order_priority_when_two_entries_contest_one_finding(self) -> None:
        # Both entries can only be satisfied by the single produced finding;
        # the earlier entry (r1) wins it, r2 is a miss.
        case = _case(
            _exp(key="r1", symbol="authenticate", lines=(40, 40), claim=_CMD, defect_kind="command-injection"),
            _exp(key="r2", symbol="authenticate", lines=(40, 40), claim=_CMD, defect_kind="command-injection"),
        )
        result = _executed(case, _prod(symbol="authenticate", line=40, defect_kind="command-injection"))
        m = bmet.compute_case_metrics(case, result)
        self.assertEqual(m.false_negatives, 1)
        self.assertEqual(m.missed_keys, ("r2",))
        self.assertEqual(m.false_positives, 0)

    def test_a_stolen_finding_leaves_a_plain_miss_not_a_near_miss(self) -> None:
        case = _case(
            _exp(key="r1", symbol="authenticate", lines=(40, 40), claim=_CMD, defect_kind="command-injection"),
            _exp(key="r2", symbol="authenticate", lines=(40, 40), claim=_CMD, defect_kind="command-injection"),
        )
        result = _executed(case, _prod(symbol="authenticate", line=40, defect_kind="command-injection"))
        m = bmet.compute_case_metrics(case, result)
        self.assertEqual(m.near_misses, 0)


class VarianceConstructTests(unittest.TestCase):
    def test_alternative_location_pairs_the_entry(self) -> None:
        case = _case(
            _exp(
                key="dup",
                path="a/primary.py",
                lines=(3, 3),
                claim="duplicated branch logic",
                defect_kind="duplication",
                alternatives=({"location": {"location_intent": "line", "path": "a/other.py"}},),
            )
        )
        result = _executed(case, _prod(path="a/other.py", line=3, defect_kind="duplication"))
        m = bmet.compute_case_metrics(case, result)
        self.assertEqual((m.false_negatives, m.false_positives), (0, 0))

    def test_optional_any_of_unsatisfied_is_not_a_miss(self) -> None:
        case = _case(
            _any_of(
                "grp",
                _exp(key="m1", lines=(1, 1), claim="one read", defect_kind="a-kind"),
                _exp(key="m2", lines=(1, 1), claim="other read", defect_kind="b-kind"),
                required=False,
            )
        )
        m = bmet.compute_case_metrics(case, _executed(case))
        self.assertEqual(m.false_negatives, 0)

    def test_required_any_of_unsatisfied_is_one_miss_not_per_member(self) -> None:
        case = _case(
            _any_of(
                "grp",
                _exp(key="m1", lines=(1, 1), claim="one read", defect_kind="a-kind"),
                _exp(key="m2", lines=(1, 1), claim="other read", defect_kind="b-kind"),
            )
        )
        m = bmet.compute_case_metrics(case, _executed(case, _prod(path="z/z.py", line=9, defect_kind="unrelated")))
        self.assertEqual(m.false_negatives, 1)
        self.assertEqual(m.missed_keys, ("grp",))
        self.assertEqual(m.false_positives, 1)

    def test_at_least_zeroes_false_positives_and_records_tolerated(self) -> None:
        case = _case(
            _exp(key="r1", lines=(1, 1), claim="the real bug", defect_kind="bug"),
            completeness="at-least",
        )
        result = _executed(
            case,
            _prod(line=1, claim="the real bug", defect_kind="bug"),
            _prod(path="noise/a.py", line=2, claim="unrelated nit", defect_kind="nit"),
            _prod(path="noise/b.py", line=3, claim="another unrelated nit", defect_kind="style"),
        )
        m = bmet.compute_case_metrics(case, result)
        self.assertEqual(m.false_positives, 0)
        self.assertEqual(m.tolerated_unexpected, 2)
        self.assertEqual(m.incorrect_indices, ())


class AggregateAndSectionTests(unittest.TestCase):
    def test_aggregate_is_a_plain_sum(self) -> None:
        miss_case = _case(
            _exp(key="a1", lines=(1, 1), claim="bug one", defect_kind="k1"),
            _exp(key="a2", lines=(2, 2), claim="bug two", defect_kind="k2"),
            case_id="miss",
        )
        fp_case = _case(_exp(key="b1", lines=(1, 1), claim="bug", defect_kind="k"), case_id="fp")
        err_case = _case(
            _exp(key="c1", lines=(1, 1), claim="x", defect_kind="k"),
            _exp(key="c2", lines=(2, 2), claim="y", defect_kind="k2"),
            case_id="err",
        )
        cases = [miss_case, fp_case, err_case]
        results = [
            _executed(miss_case, _prod(line=1, claim="bug one", defect_kind="k1")),  # a2 missed
            _executed(
                fp_case,
                _prod(line=1, claim="bug", defect_kind="k"),
                _prod(path="z/z.py", line=9, claim="unrelated", defect_kind="other"),
            ),
            _errored(err_case),  # c1, c2 both missed
        ]
        run = bmet.compute_run_metrics(cases, results)
        agg = run.aggregate
        self.assertEqual(agg.total_false_negatives, 1 + 0 + 2)
        self.assertEqual(agg.total_false_positives, 0 + 1 + 0)
        self.assertEqual(agg.cases_with_false_negatives, 2)
        self.assertEqual(agg.cases_with_false_positives, 1)
        self.assertEqual(agg.errored_cases, 1)

    def test_missing_result_for_a_case_is_treated_as_errored(self) -> None:
        _, case, _r, *_ = WORKED[0]
        run = bmet.compute_run_metrics([case], [])
        self.assertEqual(run.per_case[0].status, "errored")
        self.assertEqual(run.per_case[0].false_negatives, 2)

    def test_section_without_baseline_is_just_the_candidate(self) -> None:
        _, case, result, *_ = WORKED[1]
        run = bmet.compute_run_metrics([case], [result])
        section = bmet.metrics_section(run)
        self.assertEqual(set(section), {"candidate"})
        self.assertEqual(section["candidate"]["aggregate"]["total_false_negatives"], 1)

    def test_section_with_baseline_renders_deltas_alongside(self) -> None:
        _, case, bad, *_ = WORKED[1]          # r2 missed
        _, _case2, good, *_ = WORKED[0]       # both found
        baseline = bmet.compute_run_metrics([case], [bad])
        candidate = bmet.compute_run_metrics([case], [good])
        section = bmet.metrics_section(candidate, baseline=baseline)
        row = section["cases"][0]
        self.assertEqual(row["id"], "c1")
        self.assertEqual(row["false_negatives"], {"baseline": 1, "candidate": 0, "delta": -1})
        self.assertEqual(
            section["aggregate"]["total_false_negatives"],
            {"baseline": 1, "candidate": 0, "delta": -1},
        )

    def test_section_is_deterministic(self) -> None:
        _, case, result, *_ = WORKED[2]
        run = bmet.compute_run_metrics([case], [result])
        self.assertEqual(bmet.metrics_section(run), bmet.metrics_section(run))


class ReferenceModuleTests(unittest.TestCase):
    def test_module_is_declared_test_only(self) -> None:
        head = (REPO_ROOT / "tests" / "reference" / "benchmark" / "benchmark_metrics.py").read_text(encoding="utf-8")[:700]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_counter_consumes_the_single_reference_matcher(self) -> None:
        raw = (REPO_ROOT / "tests" / "reference" / "benchmark" / "benchmark_metrics.py").read_text(encoding="utf-8")
        self.assertIn("from tests.reference.benchmark import benchmark_match as bm", raw)
        self.assertIn("never defines a second", raw)

    def test_only_match_edges_pair(self) -> None:
        # A NEAR_MISS never satisfies an entry: the entry stays a miss.
        case = _case(_exp(key="r1", lines=(15, 15), claim=_PAG))
        m = bmet.compute_case_metrics(case, _executed(case, _prod(line=15, claim=_REL)))
        self.assertEqual(m.false_negatives, 1)


if __name__ == "__main__":
    unittest.main()
