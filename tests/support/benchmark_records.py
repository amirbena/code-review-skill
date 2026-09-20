"""Builders for record-shaped cases, fake `run_benchmark.py` output, and sealed records."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

from runtime_platform.benchmark.scripts import benchmark_result as res
from runtime_platform.benchmark.scripts.benchmark_run_record import build_body

REPO_SHA = "a" * 40


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_case(
    case_id: str, *, missed: Sequence[str] = (), fixture: str | None = None, matched: int = 0, exact: int = 0
) -> dict[str, Any]:
    """A record-shaped case; `missed` are required findings the run failed to produce."""
    return {
        "id": case_id,
        "status": "executed",
        "fixture_digest": digest(fixture or case_id),
        "metrics": {
            "findings_completeness": "exhaustive",
            "false_negatives": len(missed),
            "false_positives": 0,
            "missed_keys": list(missed),
            "incorrect_indices": [],
            "near_misses": 0,
            "absorbed_extra_match": 0,
            "tolerated_unexpected": 0,
        },
        "severity": {
            "matched": matched,
            "severity_exact": exact,
            "over_severity": matched - exact,
            "under_severity": 0,
            "exact_rate": str(Fraction(exact, matched)) if matched else None,
            "mismatches": [],
        },
        "duplicate_noise": {
            "produced": 0,
            "clusters": 0,
            "duplicate_clusters": 0,
            "redundant_findings": 0,
            "duplicate_rate": None,
            "cluster_members": [],
        },
        "duration_s": 1.0,
    }


def run_output(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """What `run_benchmark.py` prints for `cases`."""

    def section(key: str) -> dict[str, Any]:
        return {"cases": [{"id": c["id"], "status": c["status"], **c[key]} for c in cases]}

    return {
        "run": {
            "ok": True,
            "cases": [
                {"id": c["id"], "input_kind": "diff", "status": "executed", "produced_findings": []} for c in cases
            ],
        },
        "metrics": section("metrics"),
        "severity": section("severity"),
        "duplicate_noise": section("duplicate_noise"),
    }


def sealed_record(
    lane: str,
    cases: Sequence[Mapping[str, Any]],
    *,
    started_at: str = "2026-09-01T01:00:00Z",
    model_id: str = "model-a",
    runtime_version: str = "cli-1",
) -> dict[str, Any]:
    """A valid bootstrap record, usable as a published baseline."""
    ids = [c["id"] for c in cases]
    body = build_body(
        lane=lane,
        mode=lane,
        trigger="scheduled",
        started_at=started_at,
        finished_at=started_at,
        sealed_at=started_at,
        corpus_id="0" * 64,
        cases=cases,
        provenance={
            "repo": "amirbena/code-review-skill",
            "repo_sha": REPO_SHA,
            "ref": "refs/heads/main",
            "entrypoint_version": "run_benchmark_routine.py@aaaaaaaaaaaa",
            "spec_sha256": digest("spec"),
        },
        runtime={
            "runtime_name": "cli",
            "runtime_version": runtime_version,
            "model_id": model_id,
            "adapter_id": "adapter",
        },
        verification={
            "overall_verified": True,
            "runs": [{"passed": True, "reason": "verified", "case_count": len(ids), "case_ids": ids}],
        },
        baseline={"state": "bootstrap", "run_id": None, "record_sha256": None, "comparable_case_ids": [], "incomparable_cases": []},
        drift={
            "evaluated_scope": [],
            "observations": [],
            "confirmation": {"reruns": 2, "threshold": 2, "max_cases": 10},
            "confirmed": [],
            "unconfirmed": [],
            "systemic": False,
            "outcome": {"status": "not-evaluated", "reason": "bootstrap: no baseline to compare against"},
            "attribution": "none",
            "evidence": {},
        },
        execution={"duration_s": 1.0, "confirmation_reruns": 0, "session_ref": None, "warnings": []},
        reproduction={"command": "run", "case_ids": ids, "python_version": "3", "nondeterminism": "yes"},
        raw_bundle_sha256=digest("raw"),
        raw_location="claude/benchmark-result-x:raw-bundle.json",
    )
    return res.seal_record(body)


def write_history(root: Path, record: Mapping[str, Any], *, pointer_lane: str = "sentinel", **pointer_overrides: object) -> None:
    """Lay out `record` and the `baselines/<lane>.json` pointer as `benchmark-history` does."""
    record_path = f"records/{record['lane']}/2026/{record['run_id']}.json"
    (root / Path(record_path).parent).mkdir(parents=True, exist_ok=True)
    (root / record_path).write_text(json.dumps(record), encoding="utf-8")
    pointer = {
        "lane": pointer_lane,
        "run_id": record["run_id"],
        "record_path": record_path,
        "record_sha256": record["content_sha256"],
        "source": "bootstrap",
    }
    (root / "baselines").mkdir(exist_ok=True)
    (root / "baselines" / f"{pointer_lane}.json").write_text(json.dumps({**pointer, **pointer_overrides}), encoding="utf-8")
