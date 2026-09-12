#!/usr/bin/env python3
"""Test-only reference for the benchmark missed/incorrect finding metrics (Issue #55).

Test-only: not runtime logic, not packaged — the packaged Skills are
Markdown/YAML only. This module mirrors
``docs/benchmark/missed-and-incorrect-findings.md``: the produced↔expected
one-to-one pairing (greedy, fixture document order, ``MATCH`` edges only),
the per-case false-negative (missed finding) and false-positive (incorrect
finding) counts, how ``match: optional`` / ``any_of`` / ``alternatives``
and ``findings_completeness`` change the accounting, and the aggregate
sums rendered alongside the regression report's deltas.

It is a *counter*, not a matcher: every pairwise decision is delegated to
the single reference matcher ``tests/reference/benchmark/benchmark_match.py`` (#54);
this module never defines a second match relation. Severity accuracy over
the paired set (#56), duplicate / same-root-cause noise (#57), and any
blended score / precision / recall (out of scope for #41) are downstream
and out of scope.

The contract is the *accounting and its determinism*; this module is one
executable projection so a test can prove every §8 worked example counts
as documented and that two runs agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from tests.reference.benchmark import benchmark_fixture as bf
from tests.reference.benchmark import benchmark_match as bm
from tests.reference.benchmark import benchmark_runner as br

_EXECUTED = "executed"
_ERRORED = "errored"


# ── pairing (missed-and-incorrect-findings.md §2) ────────────────────────


@dataclass(frozen=True)
class Pairing:
    """Result of the §2 greedy pass over one case."""

    # expected entry key -> consumed produced-finding index
    paired: Mapping[str, int]
    # produced-finding indices not consumed by any entry
    unconsumed_indices: tuple[int, ...]
    # expected entries (by key, fixture order) with no MATCH against the
    # unpaired produced set
    unpaired_entry_keys: tuple[str, ...]


def resolve_pairing(
    case: bf.BenchmarkCase,
    produced: Sequence[br.ProducedFinding],
    *,
    post_image: str | None = None,
) -> Pairing:
    """Greedy one-to-one pairing in fixture document order, ``MATCH`` edges
    only (missed-and-incorrect-findings.md §2). Earlier entries win a
    contested produced finding; a produced finding is consumed at most
    once."""
    consumed: set[int] = set()
    paired: dict[str, int] = {}
    unpaired_keys: list[str] = []

    for entry in case.findings:
        candidates = [i for i in range(len(produced)) if i not in consumed]
        subset = [produced[i] for i in candidates]
        outcome = bm.evaluate_entry(entry, subset, post_image=post_image)
        if outcome.result is bm.MatchResult.MATCH and outcome.produced_index is not None:
            global_idx = candidates[outcome.produced_index]
            paired[entry.key] = global_idx
            consumed.add(global_idx)
        else:
            unpaired_keys.append(entry.key)

    unconsumed = tuple(i for i in range(len(produced)) if i not in consumed)
    return Pairing(
        paired=paired,
        unconsumed_indices=unconsumed,
        unpaired_entry_keys=tuple(unpaired_keys),
    )


# ── union re-check for an unconsumed produced finding (§4) ───────────────


def _best_union_result(
    case: bf.BenchmarkCase,
    finding: br.ProducedFinding,
    *,
    post_image: str | None = None,
) -> bm.MatchResult:
    """Best pairwise result of one produced finding against every
    acceptable spec in the fixture's union — each entry's primary spec and
    ``alternatives``, and every ``any_of`` member (fixture-format.md §9).

    ``bm.evaluate_entry`` already resolves ``alternatives`` and ``any_of``
    for a single-element produced list, so the union re-check is just the
    best entry outcome over all entries.
    """
    best = bm.MatchResult.NO_MATCH
    for entry in case.findings:
        result = bm.evaluate_entry(entry, [finding], post_image=post_image).result
        if result.rank > best.rank:
            best = result
    return best


# ── per-case metrics (§3–§5) ────────────────────────────────────────────


@dataclass(frozen=True)
class CaseMetrics:
    id: str
    status: str  # "executed" | "errored"
    findings_completeness: str
    false_negatives: int
    false_positives: int
    missed_keys: tuple[str, ...]
    incorrect_indices: tuple[int, ...]
    near_misses: int
    absorbed_extra_match: int
    tolerated_unexpected: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "findings_completeness": self.findings_completeness,
            "false_negatives": self.false_negatives,
            "false_positives": self.false_positives,
            "missed_keys": list(self.missed_keys),
            "incorrect_indices": list(self.incorrect_indices),
            "near_misses": self.near_misses,
            "absorbed_extra_match": self.absorbed_extra_match,
            "tolerated_unexpected": self.tolerated_unexpected,
        }


def compute_case_metrics(
    case: bf.BenchmarkCase,
    case_result: br.CaseResult,
    *,
    post_image: str | None = None,
) -> CaseMetrics:
    """Missed/incorrect counts for one case
    (missed-and-incorrect-findings.md §3–§5)."""
    if case_result.status != _EXECUTED:
        # §4: an errored case produced nothing — every required entry is
        # missed, no false positives, flagged so the maximal miss count is
        # not mistaken for a bad-but-complete review.
        missed = tuple(e.key for e in case.findings if e.required)
        return CaseMetrics(
            id=case.id,
            status=_ERRORED,
            findings_completeness=case.findings_completeness,
            false_negatives=len(missed),
            false_positives=0,
            missed_keys=missed,
            incorrect_indices=(),
            near_misses=0,
            absorbed_extra_match=0,
            tolerated_unexpected=0,
        )

    produced = case_result.produced_findings
    pairing = resolve_pairing(case, produced, post_image=post_image)
    entry_by_key = {e.key: e for e in case.findings}

    # §3 false negatives: unpaired `required` entries (any_of counted once).
    missed_keys = tuple(k for k in pairing.unpaired_entry_keys if entry_by_key[k].required)

    # Near-miss (§5): unpaired `required` entry whose best outcome against
    # the whole produced set is NEAR_MISS. A strict subset of the misses,
    # surfaced once — on the expected side only, so one imperfect pair is
    # never counted twice.
    near_misses = 0
    for k in missed_keys:
        outcome = bm.evaluate_entry(entry_by_key[k], list(produced), post_image=post_image)
        if outcome.result is bm.MatchResult.NEAR_MISS:
            near_misses += 1

    # §4 false positives: unconsumed produced findings re-checked against
    # the whole acceptable union.
    incorrect: list[int] = []
    absorbed = 0
    for idx in pairing.unconsumed_indices:
        best = _best_union_result(case, produced[idx], post_image=post_image)
        if best is bm.MatchResult.MATCH:
            absorbed += 1
        elif best is bm.MatchResult.NEAR_MISS:
            # Imprecise description of a real expected defect — not a false
            # positive (§4); the nuance is already surfaced on the expected
            # side as that entry's near_miss.
            pass
        else:
            incorrect.append(idx)

    exhaustive = case.findings_completeness == "exhaustive"
    false_positives = len(incorrect) if exhaustive else 0
    tolerated_unexpected = 0 if exhaustive else len(incorrect)

    return CaseMetrics(
        id=case.id,
        status=_EXECUTED,
        findings_completeness=case.findings_completeness,
        false_negatives=len(missed_keys),
        false_positives=false_positives,
        missed_keys=missed_keys,
        incorrect_indices=tuple(incorrect) if exhaustive else (),
        near_misses=near_misses,
        absorbed_extra_match=absorbed,
        tolerated_unexpected=tolerated_unexpected,
    )


# ── aggregate (§5) ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class AggregateMetrics:
    total_false_negatives: int
    total_false_positives: int
    cases_with_false_negatives: int
    cases_with_false_positives: int
    total_near_misses: int
    errored_cases: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_false_negatives": self.total_false_negatives,
            "total_false_positives": self.total_false_positives,
            "cases_with_false_negatives": self.cases_with_false_negatives,
            "cases_with_false_positives": self.cases_with_false_positives,
            "total_near_misses": self.total_near_misses,
            "errored_cases": self.errored_cases,
        }


def aggregate(case_metrics: Sequence[CaseMetrics]) -> AggregateMetrics:
    """Sums only (missed-and-incorrect-findings.md §5) — no weighting, no
    rate, no blended number."""
    return AggregateMetrics(
        total_false_negatives=sum(c.false_negatives for c in case_metrics),
        total_false_positives=sum(c.false_positives for c in case_metrics),
        cases_with_false_negatives=sum(1 for c in case_metrics if c.false_negatives > 0),
        cases_with_false_positives=sum(1 for c in case_metrics if c.false_positives > 0),
        total_near_misses=sum(c.near_misses for c in case_metrics),
        errored_cases=sum(1 for c in case_metrics if c.status == _ERRORED),
    )


@dataclass(frozen=True)
class RunMetrics:
    per_case: tuple[CaseMetrics, ...]
    aggregate: AggregateMetrics

    def by_id(self) -> dict[str, CaseMetrics]:
        return {c.id: c for c in self.per_case}

    def as_dict(self) -> dict[str, Any]:
        return {
            "cases": [c.as_dict() for c in sorted(self.per_case, key=lambda c: c.id)],
            "aggregate": self.aggregate.as_dict(),
        }


def compute_run_metrics(
    cases: Sequence[bf.BenchmarkCase],
    run: br.RunResult | Sequence[br.CaseResult],
    *,
    post_images: Mapping[str, str] | None = None,
) -> RunMetrics:
    """Per-case + aggregate metrics for a whole run
    (missed-and-incorrect-findings.md §5). Cases are joined to results by
    ``id``; a case with no result is treated as errored (nothing
    produced)."""
    results = run.case_results if isinstance(run, br.RunResult) else tuple(run)
    result_by_id = {r.id: r for r in results}
    post_images = post_images or {}

    per_case: list[CaseMetrics] = []
    for case in cases:
        result = result_by_id.get(case.id)
        if result is None:
            result = br.CaseResult(
                case.id, case.input_kind, "error", error="no-result-for-case"
            )
        per_case.append(
            compute_case_metrics(
                case, result, post_image=post_images.get(case.id)
            )
        )

    return RunMetrics(tuple(per_case), aggregate(per_case))


# ── rendering alongside the regression report (§6) ──────────────────────


def _delta_row(baseline: int, candidate: int) -> dict[str, int]:
    return {"baseline": baseline, "candidate": candidate, "delta": candidate - baseline}


def metrics_section(
    candidate: RunMetrics,
    *,
    baseline: RunMetrics | None = None,
) -> dict[str, Any]:
    """The optional ``quality_metrics`` section the benchmark report gains
    when the fixtures' ``expected`` blocks are available beside a run
    (regression-report.md §11, missed-and-incorrect-findings.md §6).

    Deterministic: cases ordered by ``id``, no wall-clock or path noise.
    Never influences ``has_regressions`` or the report's process status —
    it is a parallel quality view, computed independently of the run-to-run
    diff.
    """
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
                "false_negatives": _delta_row(b.false_negatives, c.false_negatives),
                "false_positives": _delta_row(b.false_positives, c.false_positives),
                "near_misses": _delta_row(b.near_misses, c.near_misses),
            }
        )

    ba, ca = baseline.aggregate, candidate.aggregate
    return {
        "candidate": candidate.as_dict(),
        "cases": case_deltas,
        "aggregate": {
            "total_false_negatives": _delta_row(
                ba.total_false_negatives, ca.total_false_negatives
            ),
            "total_false_positives": _delta_row(
                ba.total_false_positives, ca.total_false_positives
            ),
            "total_near_misses": _delta_row(ba.total_near_misses, ca.total_near_misses),
        },
        "added_case_ids": sorted(set(cand_by_id) - set(base_by_id)),
        "removed_case_ids": sorted(set(base_by_id) - set(cand_by_id)),
    }
