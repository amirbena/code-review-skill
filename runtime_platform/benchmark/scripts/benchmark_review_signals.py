#!/usr/bin/env python3
"""Rendered Result, Decision and Coverage of a review, plus its policy-read compliance (Issue #819).

Report-level only: nothing here changes a sealed record, a fixture or a quality metric.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from runtime_platform.benchmark.reference import benchmark_blocking_verdict as bbv

_RESULT_RE = re.compile(r"\*\*Result:\s*(.+?)\*\*")
_DECISION_RE = re.compile(r"^[\s>*_-]*Decision\b[\s*_]*:[\s*_]*(.+?)[\s*_]*$", re.I | re.M)
_COVERAGE_RE = re.compile(r"^[\s>*_-]*Coverage\b[\s*_]*:[\s*_]*(.+?)[\s*_]*$", re.I | re.M)


def rendered_surfaces(report: str | None) -> dict[str, str | None]:
    """The report's Result, Decision and Coverage text; `None` where it does not render one."""
    text = report or ""
    found = {
        "result": _RESULT_RE.search(text),
        "decision": _DECISION_RE.search(text),
        "coverage": _COVERAGE_RE.search(text),
    }
    return {key: match.group(1).strip() if match else None for key, match in found.items()}


def review_signals(
    skill_md: str,
    tool_calls: Sequence[tuple[str, Mapping[str, Any]]],
    report: str | None,
    *,
    fired_conditional: Sequence[str] = (),
) -> dict[str, Any]:
    """Rendered surfaces and policy-read compliance for one review."""
    surfaces = rendered_surfaces(report)
    check = bbv.check_policy_reads(
        skill_md,
        [(name, dict(tool_input)) for name, tool_input in tool_calls],
        result_label=surfaces["result"],
        decision_label=surfaces["decision"],
        coverage=surfaces["coverage"],
        fired_conditional=fired_conditional,
    )
    return {
        **surfaces,
        "compliant": check.ok,
        "violations": list(check.violations),
        "read_states": {path: state.value for path, state in check.states.items()},
    }
