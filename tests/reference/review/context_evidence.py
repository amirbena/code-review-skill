#!/usr/bin/env python3
"""Test-only reference for the contextual-evidence model (Issue #118).

Mirrors docs/review-context/contextual-evidence-model.md: the typed
contextual-evidence model, the authoritative/informational marking, the
authority and non-override rules, the deterministic resolution outcomes,
introduced-vs-pre-existing attribution, and the finding-provenance shape
rendered by shared/templates/finding.md.
Not runtime logic, not packaged — the packaged Skills are Markdown/YAML only.

Severity is deliberately not modelled here: provenance never computes,
raises, lowers, or overrides severity (see the design record, "Severity and
provenance are distinct"), so there is nothing severity-shaped to encode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Sequence


# --- The typed evidence model (design record §3) -------------------------


class ContextualEvidenceType(Enum):
    REQUIREMENT = "requirement"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"
    ACCEPTED_DECISION = "accepted_decision"
    REPOSITORY_POLICY = "repository_policy"
    IMPLEMENTATION_FEEDBACK = "implementation_feedback"
    HISTORICAL_CONTEXT = "historical_context"
    PRE_EXISTING_RISK_NOTE = "pre_existing_risk_note"
    INFORMAL_DISCUSSION = "informal_discussion"


class Authority(Enum):
    AUTHORITATIVE = "authoritative"
    INFORMATIONAL = "informational"


AUTHORITATIVE: FrozenSet[ContextualEvidenceType] = frozenset(
    {
        ContextualEvidenceType.REQUIREMENT,
        ContextualEvidenceType.ACCEPTANCE_CRITERIA,
        ContextualEvidenceType.ACCEPTED_DECISION,
        ContextualEvidenceType.REPOSITORY_POLICY,
    }
)
INFORMATIONAL: FrozenSet[ContextualEvidenceType] = frozenset(
    {
        ContextualEvidenceType.IMPLEMENTATION_FEEDBACK,
        ContextualEvidenceType.HISTORICAL_CONTEXT,
        ContextualEvidenceType.PRE_EXISTING_RISK_NOTE,
        ContextualEvidenceType.INFORMAL_DISCUSSION,
    }
)

# Every type is classified exactly once.
assert AUTHORITATIVE | INFORMATIONAL == set(ContextualEvidenceType)
assert not (AUTHORITATIVE & INFORMATIONAL)

# The explicit "what the change must do / was decided to do" sources that an
# informational source may never silently override (design record §5).
EXPLICIT_REQUIREMENT_OR_DECISION: FrozenSet[ContextualEvidenceType] = frozenset(
    {
        ContextualEvidenceType.REQUIREMENT,
        ContextualEvidenceType.ACCEPTANCE_CRITERIA,
        ContextualEvidenceType.ACCEPTED_DECISION,
    }
)


def authority_of(evidence_type: ContextualEvidenceType) -> Authority:
    """Whether a piece of contextual evidence of this type can establish
    scope / intent / a finding (authoritative) or only focus attention and
    corroborate (informational)."""
    return (
        Authority.AUTHORITATIVE
        if evidence_type in AUTHORITATIVE
        else Authority.INFORMATIONAL
    )


# --- Authority / non-override rule (design record §5-§6) ----------------


def can_override(
    source: ContextualEvidenceType, target: ContextualEvidenceType
) -> bool:
    """Whether `source` may silently override `target`'s governing role in
    scope / intent reasoning.

    - An informational source never overrides anything.
    - No source silently overrides an explicit requirement / acceptance
      criterion / approved decision — a genuine conflict there is *reported*
      (`REPORT_CONFLICT`), not resolved by ranking. This is the rule the
      issue names: informal discussion must not silently override an
      explicit requirement or an approved design decision.
    """
    if authority_of(source) is Authority.INFORMATIONAL:
        return False
    if target in EXPLICIT_REQUIREMENT_OR_DECISION:
        return False
    return True


def feedback_is_authoritative(*, ratified_into_accepted_decision: bool) -> bool:
    """`implementation_feedback` stays informational unless the repository
    carries explicit evidence it was ratified — at which point the accepted
    artifact, not the feedback comment, is the authoritative evidence
    (design record §4)."""
    return bool(ratified_into_accepted_decision)


# --- Resolution outcomes (design record §7) -----------------------------


class Resolution(Enum):
    USE_AUTHORITATIVE = "USE_AUTHORITATIVE"
    REPORT_CONFLICT = "REPORT_CONFLICT"
    REPORT_AMBIGUITY = "REPORT_AMBIGUITY"
    TREAT_AS_INFORMATIONAL_ONLY = "TREAT_AS_INFORMATIONAL_ONLY"
    DISREGARD_STALE = "DISREGARD_STALE"


def resolve(
    *,
    supporting_types: Sequence[ContextualEvidenceType],
    contradicting_authoritative: bool = False,
    requirement_vs_repo_policy_conflict: bool = False,
    existing_contract_settles_it: bool = False,
    authoritative_source_is_vague: bool = False,
    expected_requirement_missing: bool = False,
    superseded_by_newer_maintainer_clarification: bool = False,
    contradicted_by_repo_architecture_it_predates: bool = False,
) -> Resolution:
    """The single resolution outcome for the contextual evidence relevant to
    a potential finding. Check order is significant and matches the design
    record's table."""
    if (
        superseded_by_newer_maintainer_clarification
        or contradicted_by_repo_architecture_it_predates
    ):
        return Resolution.DISREGARD_STALE

    if requirement_vs_repo_policy_conflict:
        # §6: an existing repository contract may already settle the
        # precedence; otherwise the conflict is reported, never ranked away.
        return (
            Resolution.USE_AUTHORITATIVE
            if existing_contract_settles_it
            else Resolution.REPORT_CONFLICT
        )

    if contradicting_authoritative:
        return Resolution.REPORT_CONFLICT

    if authoritative_source_is_vague or expected_requirement_missing:
        return Resolution.REPORT_AMBIGUITY

    if any(authority_of(t) is Authority.AUTHORITATIVE for t in supporting_types):
        return Resolution.USE_AUTHORITATIVE

    return Resolution.TREAT_AS_INFORMATIONAL_ONLY


def can_establish_finding(resolution: Resolution) -> bool:
    """Only `USE_AUTHORITATIVE` lets contextual evidence establish (not
    merely corroborate) a finding. Every other outcome is a reported
    observation unless a side is independently violated with its own code
    evidence — which the model does not represent here."""
    return resolution is Resolution.USE_AUTHORITATIVE


# --- Introduced-vs-pre-existing attribution (design record §10) ---------


class FindingOrigin(Enum):
    INTRODUCED = "introduced"
    PRE_EXISTING = "pre_existing"
    UNCLEAR = "unclear"


def attribute_finding_origin(
    *,
    note_type: ContextualEvidenceType | None,
    corroborated_by_pre_change_code: bool,
    change_introduces_or_activates: bool,
) -> FindingOrigin:
    """Attribute a finding as introduced by the reviewed change or
    pre-existing. A change that introduces or activates the condition is
    always `INTRODUCED`, regardless of any note. An informational note that
    the code does not corroborate cannot move an introduced defect into the
    pre-existing bucket."""
    if change_introduces_or_activates:
        return FindingOrigin.INTRODUCED
    if (
        note_type
        in (
            ContextualEvidenceType.PRE_EXISTING_RISK_NOTE,
            ContextualEvidenceType.HISTORICAL_CONTEXT,
        )
        and corroborated_by_pre_change_code
    ):
        return FindingOrigin.PRE_EXISTING
    return FindingOrigin.UNCLEAR


# --- Finding provenance shape (design record §8; shared/templates/finding.md,
# "Contextual evidence and provenance") ---------------------------------


@dataclass(frozen=True)
class ContextualEvidenceEntry:
    evidence_type: ContextualEvidenceType
    source_name: str  # e.g. "Jira PROJECT-1234 acceptance criteria", "ADR 0007"
    note: str  # the specific clause / statement that informed the finding


@dataclass(frozen=True)
class FindingProvenance:
    """A finding is always attributable to code evidence; it may additionally
    carry contextual-evidence provenance. This shape never carries or
    influences a severity."""

    code_evidence: str
    context_evidence: tuple[ContextualEvidenceEntry, ...] = ()

    def renders_context_evidence(self) -> bool:
        """The optional `Contextual evidence` field renders only when at
        least one contextual entry informed the finding."""
        return bool(self.context_evidence)

    def render_context_evidence_field(self) -> str:
        """The finding-template `- **Contextual evidence:**` line, or "" when
        there is nothing to render (never an empty placeholder)."""
        if not self.renders_context_evidence():
            return ""
        parts = "; ".join(
            f"{e.evidence_type.value} — {e.source_name}: {e.note}"
            for e in self.context_evidence
        )
        return f"- **Contextual evidence:** {parts}"


# --- Governance: this module's own shape never grows retrieval, mutation,
# approval-bypass, or context-overrides-code capability (mirrors
# tests/reference/review/review_context.py) -----------------------------------

PROHIBITED_CAPABILITY_NAME_FRAGMENTS: FrozenSet[str] = frozenset(
    {
        "fetch",
        "retrieve",
        "resolve_source",
        "ingest",
        "auto_attach",
        "publish",
        "submit",
        "post_",
        "approve",
        "request_changes",
        "merge",
        "delete",
        "push",
        "commit",
        "bypass_approval",
        "skip_approval",
        "auto_approve",
        "override_ownership",
        "context_overrides_code",
        "trust_context_over_code",
        "assume_implemented",
        "severity_from_context",
        "raise_severity",
        "lower_severity",
    }
)


def public_callables() -> tuple[str, ...]:
    """Names a test can assert carry no prohibited capability fragment."""
    return (
        "authority_of",
        "can_override",
        "feedback_is_authoritative",
        "resolve",
        "can_establish_finding",
        "attribute_finding_origin",
        "renders_context_evidence",
        "render_context_evidence_field",
    )
