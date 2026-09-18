#!/usr/bin/env python3
"""Positive completion verification for a Class 2 Cloud Routine run (Issue #415).

Never trusts a Routine's own "green" session status: parses
``run_benchmark.py``'s own JSON stdout and confirms it carries the stable
per-case result shape (``runtime_platform/benchmark/runner-contract.md`` §6) before a
run may be treated as evidence. Contract: `docs/benchmark/cloud-routine-integration.md`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoutineVerification:
    passed: bool
    reason: str
    case_count: int = 0
    case_ids: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {
            "passed": self.passed,
            "reason": self.reason,
            "case_count": self.case_count,
            "case_ids": list(self.case_ids),
        }


def verify_benchmark_output(stdout: str, exit_code: int) -> RoutineVerification:
    """Fail-closed check of one ``run_benchmark.py`` invocation's output.

    A non-zero exit code with no parseable JSON covers the
    ``check_runtime_available`` preflight failure path (no stdout JSON is
    ever printed in that case) as well as any other execution-level crash.
    """
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, TypeError) as exc:
        if exit_code != 0:
            # Covers check_runtime_available's preflight failure path,
            # which prints to stderr and never emits stdout JSON at all.
            return RoutineVerification(False, "runtime-unavailable-or-execution-error")
        return RoutineVerification(False, f"parse-error: {exc}")

    if not isinstance(data, dict) or "run" not in data:
        return RoutineVerification(False, "missing-run-key")

    run = data["run"]
    if not isinstance(run, dict):
        return RoutineVerification(False, "malformed-run-value")

    cases = run.get("cases")
    if not isinstance(cases, list) or not cases:
        return RoutineVerification(False, "no-cases-executed")

    case_ids: list[str] = []
    for case in cases:
        if not isinstance(case, dict) or "id" not in case or "status" not in case:
            return RoutineVerification(False, f"malformed-case-shape: {case!r}")
        case_ids.append(str(case["id"]))
        if case["status"] != "executed":
            error = case.get("error", "unspecified")
            return RoutineVerification(
                False, f"case '{case['id']}' not executed: {error}", len(cases), tuple(case_ids)
            )
        if "produced_findings" not in case:
            return RoutineVerification(
                False, f"case '{case['id']}' missing produced_findings", len(cases), tuple(case_ids)
            )

    if run.get("ok") is not True:
        return RoutineVerification(False, "run-not-ok", len(cases), tuple(case_ids))

    return RoutineVerification(True, "verified", len(cases), tuple(case_ids))
