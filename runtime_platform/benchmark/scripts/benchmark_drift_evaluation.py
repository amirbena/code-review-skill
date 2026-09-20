#!/usr/bin/env python3
"""Execution-side drift evaluation with in-run confirmation, before the seal.

Contract: `runtime_platform/benchmark/scheduled-operations/drift-issue-lifecycle-and-recovery.md` §2.
Classification is the unchanged `benchmark_drift.classify_drift`; this module only
compares, re-observes drifting cases, and reports. It never touches GitHub.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.scripts import benchmark_result as res  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_baseline import BaselineLookup  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_drift import DriftRecord, classify_drift  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_run_record import metrics_from_case, severity_from_case  # noqa: E402

REASON_NOT_REPRODUCED = "not-reproduced"
REASON_TIMEOUT = "unconfirmed-timeout"
REASON_SYSTEMIC_CAP = "systemic-cap"

# Re-observes one case through `selected` mode; raises when the invocation does not verify.
Observe = Callable[[str], Mapping[str, Any]]


@dataclass(frozen=True)
class ConfirmationPolicy:
    reruns: int
    threshold: int
    max_cases: int

    def as_dict(self) -> dict[str, int]:
        return {"reruns": self.reruns, "threshold": self.threshold, "max_cases": self.max_cases}


@dataclass(frozen=True)
class Evaluation:
    baseline: dict[str, Any]
    drift: dict[str, Any]
    reruns_performed: int


def _not_evaluated(reason: str, policy: ConfirmationPolicy) -> dict[str, Any]:
    return {
        "evaluated_scope": [],
        "observations": [],
        "confirmation": policy.as_dict(),
        "confirmed": [],
        "unconfirmed": [],
        "systemic": False,
        "outcome": {"status": "not-evaluated", "reason": reason},
        "attribution": "none",
        "evidence": {},
    }


def _classify(baseline: Mapping[str, Mapping[str, Any]], candidate: Mapping[str, Mapping[str, Any]], ids: Sequence[str]) -> list[DriftRecord]:
    return classify_drift(
        {i: metrics_from_case(baseline[i]) for i in ids},
        {i: metrics_from_case(candidate[i]) for i in ids},
        {i: severity_from_case(baseline[i]) for i in ids},
        {i: severity_from_case(candidate[i]) for i in ids},
    )


def _attribution(baseline_record: Mapping[str, Any], runtime: Mapping[str, str]) -> str:
    base = baseline_record["runtime"]
    changed = base["model_id"] != runtime["model_id"] or base["runtime_version"] != runtime["runtime_version"]
    return "runtime-changed" if changed else "none"


def evaluate_drift(
    candidate_cases: Sequence[Mapping[str, Any]],
    lookup: BaselineLookup,
    policy: ConfirmationPolicy,
    runtime: Mapping[str, str],
    observe: Observe,
    *,
    deadline: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> Evaluation:
    """Compare against the lane baseline and confirm each drifting case by re-running only it."""
    if lookup.state == "bootstrap":
        baseline = {"state": "bootstrap", "run_id": None, "record_sha256": None, "comparable_case_ids": [], "incomparable_cases": []}
        return Evaluation(baseline, _not_evaluated("bootstrap: no baseline to compare against", policy), 0)
    if lookup.state != "compared" or lookup.record is None:
        baseline = {"state": "incomparable", "run_id": None, "record_sha256": None, "comparable_case_ids": [], "incomparable_cases": []}
        return Evaluation(baseline, _not_evaluated(lookup.reason or "baseline is not comparable", policy), 0)

    base_record = lookup.record
    partition = res.partition_case_comparability(candidate_cases, base_record["cases"])
    scope = partition["comparable_case_ids"]
    baseline = {
        "state": "compared",
        "run_id": base_record["run_id"],
        "record_sha256": base_record["content_sha256"],
        "comparable_case_ids": scope,
        "incomparable_cases": partition["incomparable_cases"],
    }
    if not scope:
        return Evaluation(baseline, _not_evaluated("no case is comparable with the baseline", policy), 0)

    base_by_id = {c["id"]: c for c in base_record["cases"]}
    cand_by_id = {c["id"]: c for c in candidate_cases}
    observations = _classify(base_by_id, cand_by_id, scope)

    drifting = sorted({r.case_id for r in observations})
    confirmed_cases, systemic = drifting[: policy.max_cases], len(drifting) > policy.max_cases
    counts = {r.fingerprint: 1 for r in observations}
    timed_out: set[str] = set()
    reruns_performed = 0
    for case_id in confirmed_cases:
        expected = {r.fingerprint for r in observations if r.case_id == case_id}
        for _ in range(policy.reruns):
            if deadline is not None and clock() >= deadline:
                timed_out.add(case_id)
                break
            rerun = observe(case_id)
            reruns_performed += 1
            seen = {r.fingerprint for r in _classify(base_by_id, {case_id: rerun}, [case_id])}
            for fp in expected & seen:
                counts[fp] += 1

    confirmed, unconfirmed = [], []
    for record in observations:
        if counts[record.fingerprint] >= policy.threshold:
            confirmed.append(record.as_dict())
            continue
        if record.case_id not in confirmed_cases:
            reason = REASON_SYSTEMIC_CAP
        elif record.case_id in timed_out:
            reason = REASON_TIMEOUT
        else:
            reason = REASON_NOT_REPRODUCED
        unconfirmed.append({**record.as_dict(), "reason": reason})

    drift = {
        "evaluated_scope": scope,
        "observations": [r.as_dict() for r in observations],
        "confirmation": policy.as_dict(),
        "confirmed": confirmed,
        "unconfirmed": unconfirmed,
        "systemic": systemic,
        "outcome": {"status": "drift" if confirmed else "none", "reason": None},
        "attribution": _attribution(base_record, runtime),
        "evidence": {},
    }
    return Evaluation(baseline, drift, reruns_performed)
