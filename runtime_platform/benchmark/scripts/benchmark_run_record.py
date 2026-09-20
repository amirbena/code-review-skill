#!/usr/bin/env python3
"""Assembles the `benchmark-result/v1` sealed body from verified run output.

Contract: `runtime_platform/benchmark/benchmark-result-schema.md`. Pure: no I/O, no GitHub.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.reference import benchmark_dupes as bdup  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_metrics as bmet  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_severity as bsev  # noqa: E402
from runtime_platform.benchmark.scripts import benchmark_result as res  # noqa: E402

_LIFTED = ("id", "status")


class RecordAssemblyError(RuntimeError):
    """Verified output could not be projected into a sealed record."""


def _rows_by_id(output: Mapping[str, Any], section: str) -> dict[str, dict[str, Any]]:
    block = output.get(section)
    rows = block.get("cases") if isinstance(block, dict) else None
    if not isinstance(rows, list):
        raise RecordAssemblyError(f"run output has no per-case {section!r} section")
    return {row["id"]: row for row in rows}


def _body(row: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k not in _LIFTED}


def cases_from_output(
    output: Mapping[str, Any], fixture_digests: Mapping[str, str], duration_s: float
) -> list[dict[str, Any]]:
    """Record-shaped cases for one `run_benchmark.py` invocation.

    `duration_s` is the invocation's wall time, shared evenly by its cases.
    """
    metrics = _rows_by_id(output, "metrics")
    severity = _rows_by_id(output, "severity")
    noise = _rows_by_id(output, "duplicate_noise")
    share = round(duration_s / max(len(metrics), 1), 3)
    cases = []
    for case_id, row in sorted(metrics.items()):
        if case_id not in fixture_digests or case_id not in severity or case_id not in noise:
            raise RecordAssemblyError(f"case {case_id!r} is missing a digest or a metric section")
        cases.append(
            {
                "id": case_id,
                "status": row["status"],
                "fixture_digest": fixture_digests[case_id],
                "metrics": _body(row),
                "severity": _body(severity[case_id]),
                "duplicate_noise": _body(noise[case_id]),
                "duration_s": share,
            }
        )
    return cases


def metrics_from_case(case: Mapping[str, Any]) -> bmet.CaseMetrics:
    m = case["metrics"]
    return bmet.CaseMetrics(
        id=case["id"],
        status=case["status"],
        findings_completeness=m["findings_completeness"],
        false_negatives=m["false_negatives"],
        false_positives=m["false_positives"],
        missed_keys=tuple(m["missed_keys"]),
        incorrect_indices=tuple(m["incorrect_indices"]),
        near_misses=m["near_misses"],
        absorbed_extra_match=m["absorbed_extra_match"],
        tolerated_unexpected=m["tolerated_unexpected"],
    )


def severity_from_case(case: Mapping[str, Any]) -> bsev.CaseSeverityAccuracy:
    s = case["severity"]
    return bsev.CaseSeverityAccuracy(
        id=case["id"],
        status=case["status"],
        matched=s["matched"],
        severity_exact=s["severity_exact"],
        over_severity=s["over_severity"],
        under_severity=s["under_severity"],
        mismatches=tuple(s["mismatches"]),
    )


def noise_from_case(case: Mapping[str, Any]) -> bdup.CaseDuplicateNoise:
    n = case["duplicate_noise"]
    return bdup.CaseDuplicateNoise(
        id=case["id"],
        status=case["status"],
        produced=n["produced"],
        clusters=n["clusters"],
        duplicate_clusters=n["duplicate_clusters"],
        redundant_findings=n["redundant_findings"],
        cluster_members=tuple(n["cluster_members"]),
    )


def aggregate_block(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "metrics": bmet.aggregate([metrics_from_case(c) for c in cases]).as_dict(),
        "severity": bsev.aggregate([severity_from_case(c) for c in cases]).as_dict(),
        "duplicate_noise": bdup.aggregate([noise_from_case(c) for c in cases]).as_dict(),
    }


def build_body(
    *,
    lane: str,
    mode: str,
    trigger: str,
    started_at: str,
    finished_at: str,
    sealed_at: str,
    corpus_id: str,
    cases: Sequence[Mapping[str, Any]],
    provenance: Mapping[str, str],
    runtime: Mapping[str, str],
    verification: Mapping[str, Any],
    baseline: Mapping[str, Any],
    drift: Mapping[str, Any],
    execution: Mapping[str, Any],
    reproduction: Mapping[str, Any],
    raw_bundle_sha256: str,
    raw_location: str,
) -> dict[str, Any]:
    """The sealed body (a record without `content_sha256`), cases in id order."""
    ordered = sorted(cases, key=lambda c: c["id"])
    case_ids = [c["id"] for c in ordered]
    return {
        "schema": res.RESULT_SCHEMA_ID,
        "run_id": res.make_run_id(lane, started_at, provenance["repo_sha"]),
        "trigger": trigger,
        "started_at": started_at,
        "finished_at": finished_at,
        "sealed_at": sealed_at,
        "lane": lane,
        "mode": mode,
        "corpus": {
            "corpus_id": corpus_id,
            "case_count": len(ordered),
            "membership_digest": res.membership_digest(case_ids),
        },
        "provenance": dict(provenance),
        "runtime": dict(runtime),
        "aggregate": aggregate_block(ordered),
        "cases": [dict(c) for c in ordered],
        "verification": dict(verification),
        "baseline": dict(baseline),
        "drift": dict(drift),
        "execution": dict(execution),
        "reproduction": dict(reproduction),
        "raw": {"bundle_sha256": raw_bundle_sha256, "location": raw_location},
    }
