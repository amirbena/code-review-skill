#!/usr/bin/env python3
"""Rendered Result, Decision and Coverage of a review (Issue #819).

Report-level only: nothing here changes a sealed record, a fixture or a quality metric.
"""

from __future__ import annotations

import re
from typing import Any

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


def review_signals(report: str | None) -> dict[str, Any]:
    """Rendered surfaces for one review."""
    return dict(rendered_surfaces(report))
