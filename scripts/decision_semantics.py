#!/usr/bin/env python3
"""Test-only reference for the shared severity → decision contract.

Mirrors shared/policies/severity.md ("Decision derivation (mechanical)").
Not runtime logic, not packaged.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class Severity(Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


# P0/P1 block; P2 alone never does.
BLOCKING_SEVERITIES = frozenset({Severity.P0, Severity.P1})


class Decision(Enum):
    CLEAN = "REVIEW CLEAN"
    CHANGES_REQUIRED = "CHANGES REQUIRED"


@dataclass(frozen=True)
class Finding:
    """An already-classified finding.

    `origin` is informational only; the derivation below never branches on it.
    """

    id: str
    severity: Severity
    origin: str = "diff"


def blocking_findings(findings: Sequence[Finding]) -> tuple[Finding, ...]:
    """Findings with P0/P1 severity. Origin is never consulted."""
    return tuple(f for f in findings if f.severity in BLOCKING_SEVERITIES)


def derive_decision(findings: Sequence[Finding]) -> Decision:
    """The one mechanical path: any blocking finding → CHANGES_REQUIRED.

    By construction there is no override parameter — no second decision path.
    """
    return Decision.CLEAN if not blocking_findings(findings) else Decision.CHANGES_REQUIRED


# `Decision.value` is already the Decision-section text; only the Result line
# needs an emoji/phrasing map, keyed off the same enum.
RESULT_LABELS: dict[Decision, str] = {
    Decision.CLEAN: "✅ Review Clean",
    Decision.CHANGES_REQUIRED: "⚠️ Changes Requested",
}


def render_result_label(decision: Decision) -> str:
    """The report's top-level `Result` line for an already-derived decision."""
    return RESULT_LABELS[decision]


def clean_report_retains_non_blocking_findings(findings: Sequence[Finding]) -> tuple[Finding, ...]:
    """`REVIEW CLEAN` means "no blocking findings", not "no findings" — every
    finding still appears in the report."""
    return tuple(findings)


# Governance: name fragments whose presence would mean a second, overridable
# or provisional decision path crept in. test_decision_semantics.py checks
# public signatures against these.
PROHIBITED_OVERRIDE_PARAM_FRAGMENTS: frozenset[str] = frozenset(
    {
        "override",
        "force",
        "bypass",
        "ignore_severity",
        "manual_decision",
        "recommend_block",
        "should_block",
    }
)

PROHIBITED_CORRECTION_FRAGMENTS: frozenset[str] = frozenset(
    {
        "correction",
        "correct_decision",
        "provisional",
        "supersede",
        "resubmit_decision",
        "revise_decision",
    }
)
