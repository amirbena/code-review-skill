#!/usr/bin/env python3
"""Test-only reference for the benchmark duplicate-noise metric (Issue #57).

Test-only: not runtime logic, not packaged — the packaged Skills are
Markdown/YAML only. This module mirrors
``docs/benchmark/duplicate-noise.md``: over a case's *produced* findings
alone, it clusters same-root-cause findings, then reports how many
findings are redundant (each cluster beyond its first), per case and in
aggregate, plus the highest-noise cases, rendered alongside the regression
report.

It is a *clusterer over produced findings*, not a matcher and not a
pairer: every same-root-cause edge is decided by the single #54 reference
matcher ``tests/reference/benchmark/benchmark_match.py`` (``bm.match_pair``) applied
to a pair of produced findings. This module defines no second match relation,
adds no axis, and adds no tolerance. The #55 produced<->expected pairing and
its ``absorbed_extra_match`` count are a different lens and are not consumed
here (duplicate-noise.md §8). Any blended score / precision / recall (out of
scope for #41) is downstream.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Mapping, Sequence

from tests.reference.benchmark import benchmark_fixture as bf
from tests.reference.benchmark import benchmark_match as bm
from tests.reference.benchmark import benchmark_runner as br

_EXECUTED = "executed"
_ERRORED = "errored"


# ── same-root-cause edge: the #54 MATCH cell, symmetrized (§2) ──────────


def _as_spec(finding: br.ProducedFinding) -> dict[str, Any]:
    """View one produced finding as an expected sub-spec so the single #54
    matcher can score it against another produced finding
    (duplicate-noise.md §2). Only the fields ``bm.match_pair`` reads are
    carried; nothing is invented."""
    desc = bm.Descriptor.from_produced(finding)
    location: dict[str, Any] = {}
    if desc.intent is not None:
        location["location_intent"] = desc.intent
    if desc.path is not None:
        location["path"] = desc.path
    if desc.symbol is not None:
        location["symbol"] = desc.symbol
    if desc.anchor is not None:
        location["anchor"] = desc.anchor
    if desc.lines is not None:
        location["lines"] = {"start": desc.lines[0], "end": desc.lines[1]}
    return {
        "location": location or None,
        "claim": desc.claim,
        "defect_kind": desc.defect_kind,
    }


def same_root_cause(
    a: br.ProducedFinding,
    b: br.ProducedFinding,
    *,
    post_image: str | None = None,
) -> bool:
    """Two produced findings name the same root cause when the #54 relation
    is ``MATCH`` — location EXACT *and* defect CORRESPONDS — in either
    direction (duplicate-noise.md §2). The direction only matters for the
    degenerate axis branches (a missing path/side); whenever both findings
    carry a path and a line span the two directions agree."""
    forward = bm.match_pair(_as_spec(a), b, post_image=post_image).result
    if forward is bm.MatchResult.MATCH:
        return True
    backward = bm.match_pair(_as_spec(b), a, post_image=post_image).result
    return backward is bm.MatchResult.MATCH


# ── connected components over the same-root-cause edges (§3) ────────────


def _cluster(
    produced: Sequence[br.ProducedFinding],
    *,
    post_image: str | None = None,
) -> list[list[int]]:
    """Union-find over produced-finding indices; an edge is a
    ``same_root_cause`` pair. Returns clusters as ascending index lists,
    the list ordered by each cluster's smallest index — fully deterministic
    (duplicate-noise.md §3, §6). Singletons are clusters of one."""
    parent = list(range(len(produced)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[max(rx, ry)] = min(rx, ry)

    for i in range(len(produced)):
        for j in range(i + 1, len(produced)):
            if same_root_cause(produced[i], produced[j], post_image=post_image):
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(produced)):
        groups.setdefault(find(i), []).append(i)
    return [sorted(members) for _, members in sorted(groups.items())]


# ── per-case metric (duplicate-noise.md §4) ────────────────────────────


@dataclass(frozen=True)
class CaseDuplicateNoise:
    id: str
    status: str  # "executed" | "errored"
    produced: int
    clusters: int  # singletons included
    duplicate_clusters: int  # clusters of size >= 2
    redundant_findings: int  # produced - clusters
    cluster_members: tuple[dict[str, Any], ...]

    @property
    def duplicate_rate(self) -> Fraction | None:
        if self.produced == 0:
            return None
        return Fraction(self.redundant_findings, self.produced)

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "produced": self.produced,
            "clusters": self.clusters,
            "duplicate_clusters": self.duplicate_clusters,
            "redundant_findings": self.redundant_findings,
            "duplicate_rate": None
            if self.duplicate_rate is None
            else str(self.duplicate_rate),
            "cluster_members": [dict(m) for m in self.cluster_members],
        }


def compute_case_duplicate_noise(
    case: bf.BenchmarkCase,
    case_result: br.CaseResult,
    *,
    post_image: str | None = None,
) -> CaseDuplicateNoise:
    """Duplicate-noise counts for one case (duplicate-noise.md §2–§4)."""
    if case_result.status != _EXECUTED:
        # §4: an errored case produced nothing — no findings to cluster.
        return CaseDuplicateNoise(case.id, _ERRORED, 0, 0, 0, 0, ())

    produced = case_result.produced_findings
    clusters = _cluster(produced, post_image=post_image)

    members = tuple(
        {
            "representative_index": c[0],
            "member_indices": list(c),
            "size": len(c),
        }
        for c in clusters
        if len(c) >= 2
    )

    return CaseDuplicateNoise(
        id=case.id,
        status=_EXECUTED,
        produced=len(produced),
        clusters=len(clusters),
        duplicate_clusters=len(members),
        redundant_findings=len(produced) - len(clusters),
        cluster_members=members,
    )


# ── aggregate (duplicate-noise.md §4) ─────────────────────────────────


@dataclass(frozen=True)
class AggregateDuplicateNoise:
    total_produced: int
    total_redundant_findings: int
    total_duplicate_clusters: int
    cases_with_duplication: int

    @property
    def duplicate_rate(self) -> Fraction | None:
        if self.total_produced == 0:
            return None
        return Fraction(self.total_redundant_findings, self.total_produced)

    def as_dict(self) -> dict[str, Any]:
        return {
            "total_produced": self.total_produced,
            "total_redundant_findings": self.total_redundant_findings,
            "total_duplicate_clusters": self.total_duplicate_clusters,
            "duplicate_rate": None
            if self.duplicate_rate is None
            else str(self.duplicate_rate),
            "cases_with_duplication": self.cases_with_duplication,
        }


def aggregate(cases: Sequence[CaseDuplicateNoise]) -> AggregateDuplicateNoise:
    """Sums only (duplicate-noise.md §4) — the sole ratio is duplicate_rate."""
    return AggregateDuplicateNoise(
        total_produced=sum(c.produced for c in cases),
        total_redundant_findings=sum(c.redundant_findings for c in cases),
        total_duplicate_clusters=sum(c.duplicate_clusters for c in cases),
        cases_with_duplication=sum(1 for c in cases if c.redundant_findings > 0),
    )


@dataclass(frozen=True)
class RunDuplicateNoise:
    per_case: tuple[CaseDuplicateNoise, ...]
    aggregate: AggregateDuplicateNoise

    def by_id(self) -> dict[str, CaseDuplicateNoise]:
        return {c.id: c for c in self.per_case}

    def highest_noise_cases(self) -> list[dict[str, Any]]:
        """The noisiest cases first (duplicate-noise.md §5): cases with
        ``redundant_findings > 0``, ordered by ``redundant_findings``
        descending then ``id`` ascending."""
        noisy = [c for c in self.per_case if c.redundant_findings > 0]
        noisy.sort(key=lambda c: (-c.redundant_findings, c.id))
        return [
            {
                "id": c.id,
                "redundant_findings": c.redundant_findings,
                "duplicate_clusters": c.duplicate_clusters,
                "produced": c.produced,
            }
            for c in noisy
        ]

    def as_dict(self) -> dict[str, Any]:
        return {
            "cases": [c.as_dict() for c in sorted(self.per_case, key=lambda c: c.id)],
            "aggregate": self.aggregate.as_dict(),
            "highest_noise_cases": self.highest_noise_cases(),
        }


def compute_run_duplicate_noise(
    cases: Sequence[bf.BenchmarkCase],
    run: br.RunResult | Sequence[br.CaseResult],
    *,
    post_images: Mapping[str, str] | None = None,
) -> RunDuplicateNoise:
    """Per-case + aggregate duplicate noise for a whole run. A case with no
    result is treated as errored (nothing produced)."""
    results = run.case_results if isinstance(run, br.RunResult) else tuple(run)
    result_by_id = {r.id: r for r in results}
    post_images = post_images or {}

    per_case: list[CaseDuplicateNoise] = []
    for case in cases:
        result = result_by_id.get(case.id)
        if result is None:
            result = br.CaseResult(
                case.id, case.input_kind, "error", error="no-result-for-case"
            )
        per_case.append(
            compute_case_duplicate_noise(
                case, result, post_image=post_images.get(case.id)
            )
        )

    return RunDuplicateNoise(tuple(per_case), aggregate(per_case))


# ── rendering alongside the regression report (duplicate-noise.md §5) ──


def _delta_row(baseline: int, candidate: int) -> dict[str, int]:
    return {"baseline": baseline, "candidate": candidate, "delta": candidate - baseline}


def duplicate_noise_section(
    candidate: RunDuplicateNoise,
    *,
    baseline: RunDuplicateNoise | None = None,
) -> dict[str, Any]:
    """The optional ``duplicate_noise`` section the benchmark report gains
    beside a run (duplicate-noise.md §5). Deterministic: cases ordered by
    ``id``, highest-noise list ordered by the §5 key; never influences
    ``has_regressions``."""
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
                "redundant_findings": _delta_row(
                    b.redundant_findings, c.redundant_findings
                ),
                "duplicate_clusters": _delta_row(
                    b.duplicate_clusters, c.duplicate_clusters
                ),
            }
        )

    ba, ca = baseline.aggregate, candidate.aggregate
    return {
        "candidate": candidate.as_dict(),
        "cases": case_deltas,
        "aggregate": {
            "total_redundant_findings": _delta_row(
                ba.total_redundant_findings, ca.total_redundant_findings
            ),
            "total_duplicate_clusters": _delta_row(
                ba.total_duplicate_clusters, ca.total_duplicate_clusters
            ),
            "duplicate_rate": {
                "baseline": None
                if ba.duplicate_rate is None
                else str(ba.duplicate_rate),
                "candidate": None
                if ca.duplicate_rate is None
                else str(ca.duplicate_rate),
            },
        },
        "highest_noise_cases": candidate.highest_noise_cases(),
        "added_case_ids": sorted(set(cand_by_id) - set(base_by_id)),
        "removed_case_ids": sorted(set(base_by_id) - set(cand_by_id)),
    }
