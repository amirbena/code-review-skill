#!/usr/bin/env python3
"""Reference/test implementation of the severity → decision contract.

Mirrors shared/policies/severity.md, "Decision derivation (mechanical)" and
"Repository conventions and severity" — the single canonical severity model
both `local-code-review` and `github-pr-review` consume. Pure decision-table
logic (no code understanding, no Git/GitHub calls) so
test_decision_semantics.py can exercise the contract deterministically.
This is NOT production/runtime logic: both packaged Skills implement this
behavior through severity.md's policy text itself (already packaged with
each Skill), and neither packaged Skill file imports, invokes, or
otherwise depends on this module at runtime — this module is not part of
either packaged Skill archive. It exists solely so this repository's own
test suite can verify the policy's decision table is internally
consistent.

This module never assigns a finding's severity itself — that requires
actually judging the finding's evidence and impact against severity.md's
P0/P1/P2 definitions, which is each Skill's own job. It only encodes the
*mechanical* relationship between a set of already-severity-classified
findings and the final review decision: there is no independent, subjective
decision path in either Skill that can contradict this derivation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class Severity(Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


# Per severity.md, "Blocking rule": P0 and P1 block; P2 alone never blocks.
BLOCKING_SEVERITIES = frozenset({Severity.P0, Severity.P1})


class Decision(Enum):
    CLEAN = "REVIEW CLEAN"
    CHANGES_REQUIRED = "CHANGES REQUIRED"


@dataclass(frozen=True)
class Finding:
    """A single, already-classified finding.

    `origin` is informational only (e.g. "repository_convention",
    "pr_context", "review_context", "diff") — per severity.md, "Repository
    conventions and severity," a finding's origin never changes how the
    decision derivation below treats it. This module carries the field only
    so tests can prove that fact, never to branch on it.
    """

    id: str
    severity: Severity
    origin: str = "diff"


def blocking_findings(findings: Sequence[Finding]) -> tuple[Finding, ...]:
    """blocking_findings = { f in findings : severity(f) in {P0, P1} }.

    Per severity.md, "Decision derivation (mechanical)". Origin is never
    consulted — see the `Finding.origin` docstring above.
    """
    return tuple(f for f in findings if f.severity in BLOCKING_SEVERITIES)


def derive_decision(findings: Sequence[Finding]) -> Decision:
    """The one, mechanical path from findings to a decision.

    Per severity.md, "Decision derivation (mechanical)": empty
    blocking_findings -> CLEAN, non-empty -> CHANGES_REQUIRED. There is no
    parameter here for "but it's strongly recommended," "but the repository
    convention was emphatic," or any other override — by construction, this
    function cannot express a second decision path.
    """
    return Decision.CLEAN if not blocking_findings(findings) else Decision.CHANGES_REQUIRED


def clean_report_retains_non_blocking_findings(findings: Sequence[Finding]) -> tuple[Finding, ...]:
    """A clean decision never means findings are hidden or discarded.

    Per shared/templates/local-review-report.md / review-summary.md and
    severity.md: `REVIEW CLEAN` means "no blocking findings," not "zero
    findings of any kind." This returns exactly the findings that must still
    appear in the report's Findings section regardless of the decision — the
    full input set, unchanged and undiscarded.
    """
    return tuple(findings)


# --- Governance: this module's own shape never grows a second, overridable
# decision path -------------------------------------------------------------

#: Parameter/attribute name fragments that would indicate a second,
#: overridable decision path has crept into this module — e.g. a caller
#: being able to force CHANGES_REQUIRED despite empty blocking_findings, or
#: suppress it despite non-empty blocking_findings. Checked by
#: test_decision_semantics.py via substring matching against public
#: function signatures, mirroring pr_context_reconciliation.py's governance
#: test pattern.
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
