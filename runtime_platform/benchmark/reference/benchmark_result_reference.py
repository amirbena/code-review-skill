#!/usr/bin/env python3
"""Test-only builder of `benchmark-result/v1` records from the reference metrics.

Contract: `runtime_platform/benchmark/benchmark-result-schema.md`. Assembles a sealed record
from real per-case metric projections; the `measure` command builds a
silent-reviewer run over a lane's real corpus to size a record.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.reference import benchmark_dupes as bdup  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_fixture as bf  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_metrics as bmet  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_runner as br  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_severity as bsev  # noqa: E402
from runtime_platform.benchmark.scripts import benchmark_result as res  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_history import corpus_digest_for_lane  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_corpus_membership import (  # noqa: E402
    COMPREHENSIVE_LANE,
    SENTINEL_LANE,
    canonical_lane,
    discover_comprehensive_fixtures,
)

DEFAULT_CORPUS_ROOT = REPO_ROOT / "docs" / "benchmark" / "corpus"
_CASE_KEYS_LIFTED = ("id", "status")


@dataclasses.dataclass(frozen=True)
class CaseProjection:
    """One case's fixture digest plus its #55/#56/#57 per-case objects."""

    case_id: str
    fixture_digest: str
    metrics: bmet.CaseMetrics
    severity: bsev.CaseSeverityAccuracy
    duplicate_noise: bdup.CaseDuplicateNoise
    duration_s: float = 0.0

    def as_case(self) -> dict[str, Any]:
        def body(obj: Any) -> dict[str, Any]:
            return {k: v for k, v in obj.as_dict().items() if k not in _CASE_KEYS_LIFTED}

        return {
            "id": self.case_id,
            "status": self.metrics.status,
            "fixture_digest": self.fixture_digest,
            "metrics": body(self.metrics),
            "severity": body(self.severity),
            "duplicate_noise": body(self.duplicate_noise),
            "duration_s": self.duration_s,
        }


def lane_fixtures(lane: str, corpus_root: Path) -> list[tuple[bf.BenchmarkCase, Path]]:
    """The lane's parsed fixtures with their paths, in case-id order."""
    import yaml

    if lane == SENTINEL_LANE:
        paths = sorted(corpus_root.glob("*.yaml"))
    else:
        paths = [fx.fixture_path for fx in discover_comprehensive_fixtures(corpus_root)]
    parsed = [(bf.parse_case(yaml.safe_load(p.read_text(encoding="utf-8"))), p) for p in paths]
    return sorted(parsed, key=lambda pair: pair[0].id)


def silent_run_projections(lane: str, corpus_root: Path) -> list[CaseProjection]:
    """Projections for a reviewer that executes every case and reports nothing."""
    projections = []
    for case, path in lane_fixtures(lane, corpus_root):
        result = br.CaseResult(case.id, case.input_kind, "executed")
        projections.append(
            CaseProjection(
                case_id=case.id,
                fixture_digest=res.fixture_digest(path),
                metrics=bmet.compute_case_metrics(case, result),
                severity=bsev.compute_case_severity_accuracy(case, result),
                duplicate_noise=bdup.compute_case_duplicate_noise(case, result),
                duration_s=1.0,
            )
        )
    return projections


def build_record(
    *,
    lane: str,
    projections: Sequence[CaseProjection],
    corpus_id: str,
    repo_sha: str,
    started_at: str,
    baseline: Mapping[str, Any],
    drift: Mapping[str, Any],
    mode: str | None = None,
    model_id: str = "claude-sonnet-5",
) -> dict[str, Any]:
    """A sealed record whose aggregates are computed from `projections`."""
    case_ids = [p.case_id for p in projections]
    body = {
        "schema": res.RESULT_SCHEMA_ID,
        "run_id": res.make_run_id(lane, started_at, repo_sha),
        "trigger": "scheduled",
        "started_at": started_at,
        "finished_at": _shift(started_at, 60),
        "sealed_at": _shift(started_at, 61),
        "lane": lane,
        "mode": mode or lane,
        "corpus": {
            "corpus_id": corpus_id,
            "case_count": len(projections),
            "membership_digest": res.membership_digest(case_ids),
        },
        "provenance": {
            "repo": "amirbena/code-review-skill",
            "repo_sha": repo_sha,
            "ref": "refs/heads/main",
            "entrypoint_version": "run_benchmark_routine.py@" + repo_sha[:12],
            "spec_sha256": res.sha256_hex("routine-prompt-spec"),
        },
        "runtime": {
            "runtime_name": "claude-code-cloud-routine",
            "runtime_version": "example",
            "model_id": model_id,
            "adapter_id": repo_sha[:12],
        },
        "aggregate": {
            "metrics": bmet.aggregate([p.metrics for p in projections]).as_dict(),
            "severity": bsev.aggregate([p.severity for p in projections]).as_dict(),
            "duplicate_noise": bdup.aggregate([p.duplicate_noise for p in projections]).as_dict(),
        },
        "cases": [p.as_case() for p in projections],
        "verification": {
            "overall_verified": True,
            "runs": [{"passed": True, "reason": "verified", "case_count": len(case_ids), "case_ids": case_ids}],
        },
        "baseline": dict(baseline),
        "drift": dict(drift),
        "execution": {"duration_s": 60.0, "confirmation_reruns": 0, "session_ref": None, "warnings": []},
        "reproduction": {
            "command": f"python3 runtime_platform/benchmark/scripts/run_benchmark_routine.py --mode {mode or lane}",
            "case_ids": case_ids,
            "python_version": "3.12",
            "nondeterminism": "Model output is nondeterministic; a rerun may differ.",
        },
        "raw": {"bundle_sha256": res.sha256_hex("raw-bundle"), "location": "claude/benchmark-result-" + res.make_run_id(lane, started_at, repo_sha)},
    }
    return res.seal_record(body)


def bootstrap_baseline() -> dict[str, Any]:
    return {"state": "bootstrap", "run_id": None, "record_sha256": None, "comparable_case_ids": [], "incomparable_cases": []}


def not_evaluated_drift(reason: str, *, confirmation: Mapping[str, int] | None = None) -> dict[str, Any]:
    return {
        "evaluated_scope": [],
        "observations": [],
        "confirmation": dict(confirmation or {"reruns": 2, "threshold": 2, "max_cases": 10}),
        "confirmed": [],
        "unconfirmed": [],
        "systemic": False,
        "outcome": {"status": "not-evaluated", "reason": reason},
        "attribution": "none",
        "evidence": {},
    }


def _shift(timestamp: str, seconds: int) -> str:
    from datetime import datetime, timedelta

    moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00")) + timedelta(seconds=seconds)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def measure(lane: str, corpus_root: Path) -> dict[str, Any]:
    """Size of a bootstrap record for a silent-reviewer run over the lane's real corpus."""
    projections = silent_run_projections(lane, corpus_root)
    record = build_record(
        lane=lane,
        projections=projections,
        corpus_id=corpus_digest_for_lane(lane, corpus_root),
        repo_sha="0" * 40,
        started_at="2026-09-19T01:00:00Z",
        baseline=bootstrap_baseline(),
        drift=not_evaluated_drift("bootstrap: no baseline to compare against"),
    )
    assert not res.validate_record(record)
    pretty = json.dumps(record, indent=2, sort_keys=True).encode("utf-8")
    compact = res.canonical_json(record).encode("utf-8")
    largest = max(len(res.canonical_json(c)) for c in record["cases"])
    return {
        "lane": lane,
        "cases": len(projections),
        "canonical_bytes": len(compact),
        "pretty_bytes": len(pretty),
        "mean_case_bytes": round(sum(len(res.canonical_json(c)) for c in record["cases"]) / len(projections)),
        "largest_case_bytes": largest,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["measure"])
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    args = parser.parse_args(argv)
    for lane in (SENTINEL_LANE, COMPREHENSIVE_LANE):
        print(json.dumps(measure(canonical_lane(lane), args.corpus_root), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
