#!/usr/bin/env python3
"""Test-only reference for the finding-confidence model (Issue #178).

Not runtime logic, not packaged — the packaged Skills are Markdown/YAML only.
Mirrors docs/finding-confidence/finding-confidence-model.md and the
`confidence` field on shared/templates/finding.md: the one closed-set
machine-readable evidence-state value a finding carries, the mapping that
rolls the #128 runtime-validation state and the #118 authoritative/
informational context provenance into it, the deterministic derivation
order, the `credible` default, and the invariant that a lower value never
lowers the evidence bar, the severity, or the review decision.

Severity is deliberately not modelled here: confidence never computes,
raises, lowers, or overrides severity (design record §6), so there is
nothing severity-shaped to encode.
"""

from __future__ import annotations

from enum import Enum
from typing import FrozenSet, Optional


# --- The closed value set (design record §2) ---------------------------


class Confidence(Enum):
    CONFIRMED = "confirmed"
    CREDIBLE = "credible"
    RUNTIME_VALIDATION_UNAVAILABLE = "runtime-validation-unavailable"
    EXTERNAL_CONTRACT_UNVALIDATED = "external-contract-unvalidated"
    INSUFFICIENT_CONTEXT = "insufficient-context"


# The default and the floor: every reported finding has already cleared the
# "credible engineering risk" bar of evidence.md, so this asserts exactly
# what reporting the finding already asserts and nothing more (§5).
DEFAULT_CONFIDENCE: Confidence = Confidence.CREDIBLE

# The three values that name an unresolved basis on a finding that has
# *already* met the evidence bar. They are annotations, never a licence to
# report a finding that has not cleared it (§6).
OPEN_QUESTION_VALUES: FrozenSet[Confidence] = frozenset(
    {
        Confidence.RUNTIME_VALIDATION_UNAVAILABLE,
        Confidence.EXTERNAL_CONTRACT_UNVALIDATED,
        Confidence.INSUFFICIENT_CONTEXT,
    }
)


# --- Runtime-validation state roll-up (#128; design record §3) ---------

# The finding-validation states from shared/policies/runtime-validation.md.
RUNTIME_STATES: FrozenSet[str] = frozenset(
    {"reasoned", "runtime-confirmed", "attempted-inconclusive"}
)

# evidence.md code-evidence labels that bear on confidence.
CODE_EVIDENCE_LABELS: FrozenSet[str] = frozenset(
    {"confirmed-defect", "credible-risk", "optional-improvement"}
)


def from_runtime_state(state: str) -> Optional[Confidence]:
    """The contribution a runtime-validation state makes to `confidence`.

    `runtime-confirmed` -> confirmed; `attempted-inconclusive` ->
    runtime-validation-unavailable; `reasoned` (the default) -> nothing.
    """
    if state not in RUNTIME_STATES:
        raise ValueError(f"unknown runtime-validation state: {state!r}")
    if state == "runtime-confirmed":
        return Confidence.CONFIRMED
    if state == "attempted-inconclusive":
        return Confidence.RUNTIME_VALIDATION_UNAVAILABLE
    return None  # `reasoned` contributes nothing


# --- Deterministic derivation (design record §4) ----------------------


def derive_confidence(
    *,
    runtime_state: str = "reasoned",
    code_evidence_label: str = "credible-risk",
    authoritative_context_proves_violation: bool = False,
    authoritative_context_question_unresolved: bool = False,
    external_contract_unvalidated: bool = False,
) -> Confidence:
    """The single `confidence` value for a finding, as the first match in
    the design record's order:

    1. any signal contributes `confirmed`            -> CONFIRMED
    2. else a targeted run was attempted, inconclusive -> RUNTIME_VALIDATION_UNAVAILABLE
    3. else correctness turns on an unvalidated external contract -> EXTERNAL_CONTRACT_UNVALIDATED
    4. else a bounded, material contextual question is unresolved -> INSUFFICIENT_CONTEXT
    5. else                                          -> CREDIBLE  (default / floor)
    """
    if code_evidence_label not in CODE_EVIDENCE_LABELS:
        raise ValueError(f"unknown code-evidence label: {code_evidence_label!r}")

    runtime_contribution = from_runtime_state(runtime_state)

    # 1. confirmed wins from any source.
    if (
        runtime_contribution is Confidence.CONFIRMED
        or code_evidence_label == "confirmed-defect"
        or authoritative_context_proves_violation
    ):
        return Confidence.CONFIRMED

    # 2. an attempted-but-inconclusive targeted run.
    if runtime_contribution is Confidence.RUNTIME_VALIDATION_UNAVAILABLE:
        return Confidence.RUNTIME_VALIDATION_UNAVAILABLE

    # 3. correctness hinges on an external contract the reviewer could not
    #    inspect within the review boundary.
    if external_contract_unvalidated:
        return Confidence.EXTERNAL_CONTRACT_UNVALIDATED

    # 4. a bounded, material caller-context question is unresolved
    #    (REPORT_AMBIGUITY, material to this finding).
    if authoritative_context_question_unresolved:
        return Confidence.INSUFFICIENT_CONTEXT

    # 5. floor / default: a credible risk on static evidence.
    return Confidence.CREDIBLE


# --- Rendering gate (design record §7) --------------------------------


def renders(value: Confidence) -> bool:
    """The base human-surface gate: a `Confidence` line is a candidate for
    rendering only when the value is not the `credible` default — the same
    rule every other optional field follows. See
    :func:`renders_human_confidence` for the full gate, which also drops a
    value an already-shown `Runtime validation` line conveys."""
    return value is not DEFAULT_CONFIDENCE


def human_confidence_line_suppressed(
    value: Confidence, *, runtime_state: str = "reasoned"
) -> bool:
    """True when the human `Confidence` line would only restate a `Runtime
    validation` line already shown on the finding, so it is omitted from
    human output (design record §7). Suppression happens exactly when the
    value equals the roll-up of the shown runtime state:

    - `runtime-confirmed` shown  + `confidence` `confirmed`                 -> suppressed
    - `attempted-inconclusive` shown + `confidence` `runtime-validation-unavailable` -> suppressed

    A `confirmed` reached on static or contextual evidence while the runtime
    run was inconclusive is **not** suppressed — the two lines then say
    different things. The machine-readable schema is unaffected (see
    :func:`carried_in_machine_schema`).
    """
    return from_runtime_state(runtime_state) is value and value is not DEFAULT_CONFIDENCE


def renders_human_confidence(
    value: Confidence, *, runtime_state: str = "reasoned"
) -> bool:
    """The full human-surface gate: render the `Confidence` line only when it
    is not the `credible` default **and** it is not already conveyed by a
    shown `Runtime validation` line."""
    return renders(value) and not human_confidence_line_suppressed(
        value, runtime_state=runtime_state
    )


def carried_in_machine_schema(value: Confidence) -> bool:
    """A machine-readable output schema always carries `confidence`,
    regardless of the human-surface suppression above."""
    return True


def confidence_field_line(
    value: Confidence, *, runtime_state: str = "reasoned"
) -> str:
    """The finding-template `- **Confidence:**` line, or "" when the value is
    the default or is suppressed as redundant with a shown `Runtime
    validation` line (never an empty placeholder line)."""
    if not renders_human_confidence(value, runtime_state=runtime_state):
        return ""
    return f"- **Confidence:** {value.value}"


# --- Non-weakening invariant (design record §6) ----------------------


def lowers_evidence_bar(value: Confidence) -> bool:
    """No confidence value lowers the evidence bar for reporting. A value
    below `confirmed` annotates a finding that has already cleared
    evidence.md's bar; it never reports one that has not."""
    return False


def changes_severity(value: Confidence) -> bool:
    """Confidence never calculates, raises, lowers, or overrides severity.
    `confirmed` does not escalate a P2; the open-question values do not
    de-escalate a P1 or suppress a finding."""
    return False


def changes_decision(value: Confidence) -> bool:
    """The mechanical REVIEW CLEAN / CHANGES REQUIRED derivation never reads
    `confidence`; there is no second decision path."""
    return False


def changes_identity(value: Confidence) -> bool:
    """Confidence never changes a finding's identity or deduplication. A
    re-review may move a finding's confidence without that being a new
    finding."""
    return False


# --- Governance: this module's own shape never grows retrieval, mutation,
# scoring, or severity-moving capability (mirrors
# tests/reference/context_evidence.py) -------------------------------

PROHIBITED_CAPABILITY_NAME_FRAGMENTS: FrozenSet[str] = frozenset(
    {
        "fetch",
        "retrieve",
        "ingest",
        "auto_attach",
        "publish",
        "submit",
        "approve",
        "request_changes",
        "merge",
        "push",
        "commit",
        "probability",
        "score",
        "percent",
        "confidence_pct",
        "raise_severity",
        "lower_severity",
        "severity_from_confidence",
        "escalate",
        "de_escalate",
        "suppress_finding",
        "override_decision",
        "lower_evidence_bar",
        "report_speculative",
    }
)


def public_callables() -> tuple[str, ...]:
    """Names a test can assert carry no prohibited capability fragment."""
    return (
        "from_runtime_state",
        "derive_confidence",
        "renders",
        "human_confidence_line_suppressed",
        "renders_human_confidence",
        "carried_in_machine_schema",
        "confidence_field_line",
        "lowers_evidence_bar",
        "changes_severity",
        "changes_decision",
        "changes_identity",
    )
