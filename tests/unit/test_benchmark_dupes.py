#!/usr/bin/env python3
"""Behavioural coverage for the benchmark duplicate-noise metric (Issue #57).

Contract: docs/benchmark/duplicate-noise.md. Driven through the reference
clusterer (tests/reference/benchmark_dupes.py), whose same-root-cause edge
is the single reference matcher (tests/reference/benchmark_match.py, #54)
applied to a pair of produced findings — this module never defines a
second match relation or pairing.

What is proven here:

1. every §7 worked example produces the documented
   clusters / duplicate_clusters / redundant_findings (data-driven), and
   two runs agree;
2. `redundant_findings == produced - clusters` for every case (§1);
3. only a #54 `MATCH` pair is an edge — a `NEAR_MISS` (near location, or
   related-only claim) never clusters — and connectivity is transitive
   (§2, §3);
4. the aggregate (§4) is a plain sum with one exact-rational rate, and the
   report section (§5) renders deltas plus the highest-noise list without a
   score.

Severity accuracy (#56), the #55 pairing, and any blended
score / precision / recall are out of scope.
"""

from __future__ import annotations

import unittest
from fractions import Fraction

from tests.reference import benchmark_dupes as bdup
from tests.reference import benchmark_fixture as bf
from tests.reference import benchmark_runner as br
from tests.support.paths import REPO_ROOT


# ── builders ────────────────────────────────────────────────────────────


def _pf(
    path: str,
    line: int,
    *,
    defect_kind: str | None = None,
    claim: str | None = None,
) -> br.ProducedFinding:
    extra = {"defect_kind": defect_kind} if defect_kind is not None else {}
    return br.ProducedFinding(
        severity="P1",
        location={"path": path, "line": line},
        claim=claim,
        extra=extra,
    )


def _case(*, case_id: str = "c1") -> bf.BenchmarkCase:
    return bf.BenchmarkCase(
        format="benchmark-case/v1",
        id=case_id,
        title="t",
        input={"patch": "--- a\n+++ b\n"},
        decision=None,
        findings_completeness="exhaustive",
        findings=(),
    )


def _executed(case: bf.BenchmarkCase, *produced: br.ProducedFinding) -> br.CaseResult:
    return br.CaseResult(case.id, "patch", "executed", produced_findings=tuple(produced))


def _errored(case: bf.BenchmarkCase) -> br.CaseResult:
    return br.CaseResult(case.id, "patch", "error", error="reviewer-adapter-raised")


# ── §7 worked examples, verbatim ───────────────────────────────────────

# Each row: (name, result_fn, clusters, duplicate_clusters, redundant, rate),
# where result_fn(case) builds the runner CaseResult for that row — an
# executed case with its produced findings, or the errored row 9.
def _exec_row(*produced: br.ProducedFinding):
    return lambda case: _executed(case, *produced)


def _worked_examples():
    # 1 — two unrelated findings, no duplication
    yield (
        "1 no duplication",
        _exec_row(_pf("a.py", 40, defect_kind="command-injection"),
                  _pf("b.py", 88, defect_kind="path-traversal")),
        2, 0, 0, Fraction(0),
    )

    # 2 — one root cause reported twice
    yield (
        "2 reported twice",
        _exec_row(_pf("a.py", 40, defect_kind="command-injection"),
                  _pf("a.py", 40, defect_kind="command-injection")),
        1, 1, 1, Fraction(1, 2),
    )

    # 3 — triple report of one root cause
    yield (
        "3 triple report",
        _exec_row(*([_pf("a.py", 40, defect_kind="sql-injection")] * 3)),
        1, 1, 2, Fraction(2, 3),
    )

    # 4 — same line, genuinely different defects (EXACT + UNRELATED -> NO_MATCH)
    yield (
        "4 different defects same line",
        _exec_row(_pf("a.py", 40, defect_kind="command-injection"),
                  _pf("a.py", 40, defect_kind="resource-leak")),
        2, 0, 0, Fraction(0),
    )

    # 5 — same kind, different file (NONE location -> NO_MATCH)
    yield (
        "5 same kind different file",
        _exec_row(_pf("a.py", 40, defect_kind="sql-injection"),
                  _pf("b.py", 40, defect_kind="sql-injection")),
        2, 0, 0, Fraction(0),
    )

    # 6 — claim-overlap CORRESPONDS with no defect_kind, within the +/-3 window
    yield (
        "6 claim overlap correspond",
        _exec_row(_pf("a.py", 40, claim="SQL injection in the user query builder"),
                  _pf("a.py", 41, claim="SQL injection in user query builder")),
        1, 1, 1, Fraction(1, 2),
    )

    # 7 — same location, only related claims (EXACT + RELATED -> NEAR_MISS)
    yield (
        "7 related claim near miss",
        _exec_row(_pf("a.py", 40, claim="cache invalidation race timing"),
                  _pf("a.py", 40, claim="cache invalidation missing lock")),
        2, 0, 0, Fraction(0),
    )

    # 8 — transitive chain: 40-43 and 43-46 are edges, 40-46 is not
    yield (
        "8 transitive chain",
        _exec_row(_pf("a.py", 40, defect_kind="resource-leak"),
                  _pf("a.py", 43, defect_kind="resource-leak"),
                  _pf("a.py", 46, defect_kind="resource-leak")),
        1, 1, 2, Fraction(2, 3),
    )

    # 9 — errored case: produced nothing, contributes nothing (rate null)
    yield ("9 errored empty", _errored, 0, 0, 0, None)


WORKED = list(_worked_examples())


class WorkedExampleTests(unittest.TestCase):
    def test_every_worked_example_counts_as_documented(self) -> None:
        case = _case()
        for name, result_fn, clusters, dup_clusters, redundant, rate in WORKED:
            with self.subTest(row=name):
                m = bdup.compute_case_duplicate_noise(case, result_fn(case))
                self.assertEqual(
                    (m.clusters, m.duplicate_clusters, m.redundant_findings, m.duplicate_rate),
                    (clusters, dup_clusters, redundant, rate),
                    m.as_dict(),
                )

    def test_errored_row_9_reports_errored_status(self) -> None:
        case = _case()
        name, result_fn, *_ = WORKED[-1]
        m = bdup.compute_case_duplicate_noise(case, result_fn(case))
        self.assertEqual(m.status, "errored")
        self.assertEqual(m.produced, 0)
        self.assertIsNone(m.duplicate_rate)

    def test_redundant_equals_produced_minus_clusters(self) -> None:
        case = _case()
        for name, result_fn, *_ in WORKED:
            with self.subTest(row=name):
                m = bdup.compute_case_duplicate_noise(case, result_fn(case))
                self.assertEqual(m.redundant_findings, m.produced - m.clusters)

    def test_worked_examples_are_deterministic(self) -> None:
        case = _case()
        first = [
            bdup.compute_case_duplicate_noise(case, result_fn(case)).as_dict()
            for _, result_fn, *_ in WORKED
        ]
        second = [
            bdup.compute_case_duplicate_noise(case, result_fn(case)).as_dict()
            for _, result_fn, *_ in WORKED
        ]
        self.assertEqual(first, second)

    def test_cluster_members_are_recorded_for_duplicate_clusters_only(self) -> None:
        case = _case()
        _, result_fn, *_ = WORKED[7]  # row 8: transitive chain {0,1,2}
        m = bdup.compute_case_duplicate_noise(case, result_fn(case))
        self.assertEqual(len(m.cluster_members), 1)
        self.assertEqual(m.cluster_members[0]["representative_index"], 0)
        self.assertEqual(m.cluster_members[0]["member_indices"], [0, 1, 2])
        self.assertEqual(m.cluster_members[0]["size"], 3)


class EdgeSemanticsTests(unittest.TestCase):
    def test_near_location_same_defect_is_not_an_edge(self) -> None:
        # lines 40 and 50 — outside the +/-3 window -> NEAR location ->
        # NEAR_MISS, never a same-root-cause edge.
        case = _case()
        produced = [
            _pf("a.py", 40, defect_kind="resource-leak"),
            _pf("a.py", 50, defect_kind="resource-leak"),
        ]
        m = bdup.compute_case_duplicate_noise(case, _executed(case, *produced))
        self.assertEqual((m.clusters, m.redundant_findings), (2, 0))

    def test_a_finding_with_no_location_never_forces_a_spurious_cluster(self) -> None:
        case = _case()
        produced = [
            br.ProducedFinding(severity="P1", location={}, claim="something vague"),
            br.ProducedFinding(severity="P1", location={}, claim="another vague note"),
        ]
        m = bdup.compute_case_duplicate_noise(case, _executed(case, *produced))
        self.assertEqual(m.redundant_findings, 0)

    def test_single_finding_is_one_cluster_zero_redundant(self) -> None:
        case = _case()
        m = bdup.compute_case_duplicate_noise(
            case, _executed(case, _pf("a.py", 1, defect_kind="x-y"))
        )
        self.assertEqual((m.produced, m.clusters, m.redundant_findings), (1, 1, 0))
        self.assertEqual(m.duplicate_rate, Fraction(0))


class AggregateAndSectionTests(unittest.TestCase):
    def _run(self):
        clean = _case(case_id="clean")
        noisy = _case(case_id="noisy")
        noisier = _case(case_id="noisier")
        cases = [clean, noisy, noisier]
        results = [
            _executed(clean, _pf("a.py", 1, defect_kind="a-b")),
            _executed(
                noisy,
                _pf("a.py", 40, defect_kind="sql-injection"),
                _pf("a.py", 40, defect_kind="sql-injection"),
            ),
            _executed(noisier, *([_pf("a.py", 9, defect_kind="path-traversal")] * 3)),
        ]
        return bdup.compute_run_duplicate_noise(cases, results)

    def test_aggregate_is_a_plain_sum_with_one_rational_rate(self) -> None:
        agg = self._run().aggregate
        self.assertEqual(agg.total_produced, 6)
        self.assertEqual(agg.total_redundant_findings, 3)  # 0 + 1 + 2
        self.assertEqual(agg.total_duplicate_clusters, 2)
        self.assertEqual(agg.duplicate_rate, Fraction(1, 2))
        self.assertEqual(agg.cases_with_duplication, 2)

    def test_as_dict_renders_rate_as_canonical_string_or_null(self) -> None:
        d = self._run().as_dict()
        self.assertEqual(d["aggregate"]["duplicate_rate"], "1/2")
        empty = bdup.compute_run_duplicate_noise([_case(case_id="e")], [])
        self.assertIsNone(empty.as_dict()["aggregate"]["duplicate_rate"])

    def test_highest_noise_cases_are_ranked_and_need_no_baseline(self) -> None:
        d = self._run().as_dict()
        self.assertEqual(
            [c["id"] for c in d["highest_noise_cases"]], ["noisier", "noisy"]
        )
        self.assertEqual(d["highest_noise_cases"][0]["redundant_findings"], 2)
        # the clean case is not listed
        self.assertNotIn("clean", [c["id"] for c in d["highest_noise_cases"]])

    def test_missing_result_for_a_case_is_treated_as_errored(self) -> None:
        case = _case(case_id="only")
        run = bdup.compute_run_duplicate_noise([case], [])
        self.assertEqual(run.per_case[0].status, "errored")
        self.assertEqual(run.per_case[0].produced, 0)

    def test_section_without_baseline_is_candidate_plus_highest_noise(self) -> None:
        section = bdup.duplicate_noise_section(self._run())
        self.assertEqual(set(section), {"candidate"})
        self.assertIn("highest_noise_cases", section["candidate"])

    def test_section_with_baseline_renders_deltas_alongside(self) -> None:
        c = _case(case_id="c1")
        twice = _executed(
            c,
            _pf("a.py", 40, defect_kind="sql-injection"),
            _pf("a.py", 40, defect_kind="sql-injection"),
        )
        once = _executed(c, _pf("a.py", 40, defect_kind="sql-injection"))
        baseline = bdup.compute_run_duplicate_noise([c], [twice])
        candidate = bdup.compute_run_duplicate_noise([c], [once])
        section = bdup.duplicate_noise_section(candidate, baseline=baseline)
        row = section["cases"][0]
        self.assertEqual(row["id"], "c1")
        self.assertEqual(
            row["redundant_findings"], {"baseline": 1, "candidate": 0, "delta": -1}
        )
        self.assertEqual(
            row["duplicate_clusters"], {"baseline": 1, "candidate": 0, "delta": -1}
        )
        self.assertEqual(
            section["aggregate"]["total_redundant_findings"],
            {"baseline": 1, "candidate": 0, "delta": -1},
        )
        self.assertEqual(
            section["aggregate"]["duplicate_rate"],
            {"baseline": "1/2", "candidate": "0"},
        )
        self.assertEqual(section["highest_noise_cases"], [])

    def test_section_added_and_removed_case_ids(self) -> None:
        a = _case(case_id="a")
        b = _case(case_id="b")
        baseline = bdup.compute_run_duplicate_noise([a], [_executed(a, _pf("a.py", 1, defect_kind="a-b"))])
        candidate = bdup.compute_run_duplicate_noise([b], [_executed(b, _pf("a.py", 1, defect_kind="a-b"))])
        section = bdup.duplicate_noise_section(candidate, baseline=baseline)
        self.assertEqual(section["added_case_ids"], ["b"])
        self.assertEqual(section["removed_case_ids"], ["a"])
        self.assertEqual(section["cases"], [])

    def test_section_is_deterministic(self) -> None:
        run = self._run()
        self.assertEqual(
            bdup.duplicate_noise_section(run), bdup.duplicate_noise_section(run)
        )


class ReferenceModuleTests(unittest.TestCase):
    def test_module_is_declared_test_only(self) -> None:
        head = (REPO_ROOT / "tests" / "reference" / "benchmark_dupes.py").read_text(encoding="utf-8")[:700]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_clusterer_consumes_the_single_matcher(self) -> None:
        raw = (REPO_ROOT / "tests" / "reference" / "benchmark_dupes.py").read_text(encoding="utf-8")
        self.assertIn("from tests.reference import benchmark_match as bm", raw)
        self.assertIn("defines no second match relation", raw)


if __name__ == "__main__":
    unittest.main()
