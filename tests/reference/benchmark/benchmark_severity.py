#!/usr/bin/env python3
"""Test-only reference for the benchmark severity-accuracy metric (Issue #56).

Test-only: not runtime logic, not packaged — the packaged Skills are
Markdown/YAML only. This module mirrors
``docs/benchmark/severity-accuracy.md``: over the matched set produced by
the #55 pairing, it classifies each pair's produced severity as exact,
over-severity, or under-severity against the permitted expected severities
of the entry that pair satisfied, and reports the per-case and aggregate
counts plus the exact-match rate rendered alongside the regression report.

It is a *classifier over an existing pairing*, not a matcher or a pairer:
the pairing comes verbatim from the single reference metric
``tests/reference/benchmark/benchmark_metrics.py`` (#55), which itself delegates
every pairwise decision to the single reference matcher
``tests/reference/benchmark/benchmark_match.py`` (#54). This module therefore
defines no second pairing or match relation. Duplicate / same-root-cause
noise (#57) and any blended score / precision / recall (out of scope for
#41) are downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping, Sequence

from tests.reference.benchmark import benchmark_fixture as bf
from tests.reference.benchmark import benchmark_match as bm
from tests.reference.benchmark import benchmark_metrics as bmet
from tests.reference.benchmark import benchmark_runner as br

_EXECUTED = "executed"
_ERRORED = "errored"

# P0 more severe than P1 more severe than P2 (regression-report.md §5).
_SEVERITY_RANK = {"P2": 0, "P1": 1, "P0": 2}


def _classify(permitted: Sequence[str], produced: str) -> str:
    """severity-accuracy.md §3: exact / over / under for one matched pair."""
    if produced in permitted:
        return "exact"
    if _SEVERITY_RANK[produced] > max(_SEVERITY_RANK[s] for s in permitted):
        return "over"
    return "under"


def _permitted_severities(
    entry: bf.ExpectedFinding,
    produced: br.ProducedFinding,
    *,
    post_image: str | None,
) -> tuple[str, ...]:
    """The expected severities the matched pair is scored against
    (severity-accuracy.md §1): the satisfied entry's ``severity``, or, for
    an ``any_of`` group, the achieving member's ``severity``."""
    if not entry.is_any_of:
        return entry.severities
    outcome = bm.evaluate_entry(entry, [produced], post_image=post_image)
    if outcome.via and outcome.via.startswith("any_of:"):
        member_key = outcome.via.split(":", 1)[1]
        for member in entry.members:
            if member.key == member_key:
                return member.severities
    # Defensive: a paired any_of always resolves to a member above.
    return entry.severities


# ── per-case metric (severity-accuracy.md §4) ──────────────────────────


@dataclass(frozen=True)
class CaseSeverityAccuracy:
    id: str
    status: str  # "executed" | "errored"
    matched: int
    severity_exact: int
    over_severity: int
    under_severity: int
    mismatches: tuple[dict[str, Any], ...]

    @property
    def exact_rate(self) -> Fraction | None:
        if self.matched == 0:
            return None
        return Fraction(self.severity_exact, self.matched)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "matched": self.matched,
            "severity_exact": self.severity_exact,
            "over_severity": self.over_severity,
            "under_severity": self.under_severity,
            "exact_rate": None if self.exact_rate is None else str(self.exact_rate),
            "mismatches": [dict(m) for m in self.mismatches],
        }


def compute_case_severity_accuracy(
    case: bf.BenchmarkCase,
    case_result: br.CaseResult,
    *,
    post_image: str | None = None,
) -> CaseSeverityAccuracy:
    """Severity-accuracy counts for one case (severity-accuracy.md §2–§4)."""
    if case_result.status != _EXECUTED:
        # §2: an errored case produced nothing — the matched set is empty.
        return CaseSeverityAccuracy(case.id, _ERRORED, 0, 0, 0, 0, ())

    produced = case_result.produced_findings
    pairing = bmet.resolve_pairing(case, produced, post_image=post_image)

    exact = over = under = 0
    mismatches: list[dict[str, Any]] = []
    # Fixture entry order for deterministic `mismatches` (severity-accuracy.md §6).
    for entry in case.findings:
        idx = pairing.paired.get(entry.key)
        if idx is None:
            continue
        pf = produced[idx]
        permitted = _permitted_severities(entry, pf, post_image=post_image)
        verdict = _classify(permitted, pf.severity)
        if verdict == "exact":
            exact += 1
            continue
        if verdict == "over":
            over += 1
        else:
            under += 1
        mismatches.append(
            {
                "key": entry.key,
                "produced_index": idx,
                "expected": list(permitted),
                "produced": pf.severity,
                "direction": verdict,
            }
        )

    return CaseSeverityAccuracy(
        id=case.id,
        status=_EXECUTED,
        matched=len(pairing.paired),
        severity_exact=exact,
        over_severity=over,
        under_severity=under,
        mismatches=tuple(mismatches),
    )


# ── aggregate (severity-accuracy.md §4) ────────────────────────────────


@dataclass(frozen=True)
class AggregateSeverityAccuracy:
    total_matched: int
    total_severity_exact: int
    total_over_severity: int
    total_under_severity: int
    cases_with_severity_mismatch: int

    @property
    def exact_rate(self) -> Fraction | None:
        if self.total_matched == 0:
            return None
        return Fraction(self.total_severity_exact, self.total_matched)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_matched": self.total_matched,
            "total_severity_exact": self.total_severity_exact,
            "total_over_severity": self.total_over_severity,
            "total_under_severity": self.total_under_severity,
            "exact_rate": None if self.exact_rate is None else str(self.exact_rate),
            "cases_with_severity_mismatch": self.cases_with_severity_mismatch,
        }


def aggregate(cases: Sequence[CaseSeverityAccuracy]) -> AggregateSeverityAccuracy:
    """Sums only (severity-accuracy.md §4) — the sole ratio is exact_rate."""
    return AggregateSeverityAccuracy(
        total_matched=sum(c.matched for c in cases),
        total_severity_exact=sum(c.severity_exact for c in cases),
        total_over_severity=sum(c.over_severity for c in cases),
        total_under_severity=sum(c.under_severity for c in cases),
        cases_with_severity_mismatch=sum(
            1 for c in cases if c.over_severity + c.under_severity > 0
        ),
    )


@dataclass(frozen=True)
class RunSeverityAccuracy:
    per_case: tuple[CaseSeverityAccuracy, ...]
    aggregate: AggregateSeverityAccuracy

    def by_id(self) -> dict[str, CaseSeverityAccuracy]:
        return {c.id: c for c in self.per_case}

    def as_dict(self) -> dict[str, Any]:
        return {
            "cases": [c.as_dict() for c in sorted(self.per_case, key=lambda c: c.id)],
            "aggregate": self.aggregate.as_dict(),
        }


def compute_run_severity_accuracy(
    cases: Sequence[bf.BenchmarkCase],
    run: br.RunResult | Sequence[br.CaseResult],
    *,
    post_images: Mapping[str, str] | None = None,
) -> RunSeverityAccuracy:
    """Per-case + aggregate severity accuracy for a whole run. A case with
    no result is treated as errored (nothing produced)."""
    results = run.case_results if isinstance(run, br.RunResult) else tuple(run)
    result_by_id = {r.id: r for r in results}
    post_images = post_images or {}

    per_case: list[CaseSeverityAccuracy] = []
    for case in cases:
        result = result_by_id.get(case.id)
        if result is None:
            result = br.CaseResult(
                case.id, case.input_kind, "error", error="no-result-for-case"
            )
        per_case.append(
            compute_case_severity_accuracy(
                case, result, post_image=post_images.get(case.id)
            )
        )

    return RunSeverityAccuracy(tuple(per_case), aggregate(per_case))


# ── rendering alongside the regression report (severity-accuracy.md §5) ──


def _delta_row(baseline: int, candidate: int) -> dict[str, int]:
    return {"baseline": baseline, "candidate": candidate, "delta": candidate - baseline}


def severity_section(
    candidate: RunSeverityAccuracy,
    *,
    baseline: RunSeverityAccuracy | None = None,
) -> dict[str, Any]:
    """The optional ``severity_accuracy`` section the benchmark report gains
    beside a run (severity-accuracy.md §5). Deterministic: cases ordered by
    ``id``; never influences ``has_regressions``."""
    if baseline is None:
        return {"candidate": candidate.as_dict()}

    base_by_id = baseline.by_id()
    cand_by_id = candidate.by_id()
    common = sorted(set(base_by_id) & set(cand_by_id))

    case_deltas = []
    for cid in common:
        b, c = base_by_id[cid], cand_by_id[cid]
        case_deltas.append(
            {
                "id": cid,
                "severity_exact": _delta_row(b.severity_exact, c.severity_exact),
                "over_severity": _delta_row(b.over_severity, c.over_severity),
                "under_severity": _delta_row(b.under_severity, c.under_severity),
            }
        )

    ba, ca = baseline.aggregate, candidate.aggregate
    return {
        "candidate": candidate.as_dict(),
        "cases": case_deltas,
        "aggregate": {
            "total_severity_exact": _delta_row(
                ba.total_severity_exact, ca.total_severity_exact
            ),
            "total_over_severity": _delta_row(
                ba.total_over_severity, ca.total_over_severity
            ),
            "total_under_severity": _delta_row(
                ba.total_under_severity, ca.total_under_severity
            ),
            "exact_rate": {
                "baseline": None if ba.exact_rate is None else str(ba.exact_rate),
                "candidate": None if ca.exact_rate is None else str(ca.exact_rate),
            },
        },
        "added_case_ids": sorted(set(cand_by_id) - set(base_by_id)),
        "removed_case_ids": sorted(set(base_by_id) - set(cand_by_id)),
    }
