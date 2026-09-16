#!/usr/bin/env python3
"""Test-only reference for the candidate-finding validation model (Issue #382).
Not runtime logic, not packaged -- the packaged Skills are Markdown/YAML only.

Mirrors docs/candidate-finding-validation/candidate-finding-validation-model.md:
the observation -> candidate claim -> validated finding -> severity pipeline,
semantic-role validation (applicable only to a candidate whose own reasoning
depends on comparing two or more usages -- a standalone candidate is never
gated by it), the evidence/contract grounding hierarchy (with a non-Jira
technically-grounded blocking finding explicitly representable), the causal
validation chain, regression-proof discipline, the disconfirmation pass,
classification before severity, and the claim_valid /
blocking_justification_valid separation.

This module does not redefine evidence.md's confirmed-defect / credible-risk
/ optional-improvement labeling, severity.md's P0/P1/P2 mechanics, or
repository-expansion.md's / architectural-placement.md's ring-based
blast-radius model -- it only encodes the gates a candidate must clear
*before* reaching those contracts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet, Sequence


# --- The pipeline (design record Section 2) -------------------------------


class PipelineStage(Enum):
    OBSERVATION = "observation"
    CANDIDATE_CLAIM = "candidate_claim"
    VALIDATED_FINDING = "validated_finding"


# --- Evidence/contract grounding hierarchy (design record Section 5) ------


class GroundingSource(Enum):
    EXPLICIT_REQUIREMENT = "explicit_requirement"
    TEST_ENCODED_INTENT = "test_encoded_intent"
    ESTABLISHED_PRODUCTION_BEHAVIOR = "established_production_behavior"
    TECHNICAL_INVARIANT = "technical_invariant"
    NEARBY_PRECEDENT = "nearby_precedent"
    LOCAL_DOCS = "local_docs"
    REVIEWER_INFERENCE_ALONE = "reviewer_inference_alone"


# Rank order matches the design record's hierarchy, highest (1) to lowest (7).
GROUNDING_RANK: dict[GroundingSource, int] = {
    GroundingSource.EXPLICIT_REQUIREMENT: 1,
    GroundingSource.TEST_ENCODED_INTENT: 2,
    GroundingSource.ESTABLISHED_PRODUCTION_BEHAVIOR: 3,
    GroundingSource.TECHNICAL_INVARIANT: 4,
    GroundingSource.NEARBY_PRECEDENT: 5,
    GroundingSource.LOCAL_DOCS: 6,
    GroundingSource.REVIEWER_INFERENCE_ALONE: 7,
}

assert set(GROUNDING_RANK) == set(GroundingSource)

# No Jira/tracker reference is required: these sources independently
# establish a blocking premise with no ticket at all.
NO_TICKET_REQUIRED: FrozenSet[GroundingSource] = frozenset(
    {
        GroundingSource.EXPLICIT_REQUIREMENT,
        GroundingSource.TEST_ENCODED_INTENT,
        GroundingSource.ESTABLISHED_PRODUCTION_BEHAVIOR,
        GroundingSource.TECHNICAL_INVARIANT,
        GroundingSource.NEARBY_PRECEDENT,
        GroundingSource.LOCAL_DOCS,
    }
)


def can_establish_blocking_premise(
    sources: Sequence[GroundingSource],
) -> bool:
    """Reviewer inference alone never, by itself, establishes a blocking
    premise (design record Section 5). Any other source in the hierarchy
    may -- including with no requirement/Jira reference at all."""
    return any(s in NO_TICKET_REQUIRED for s in sources)


# --- Semantic-role validation (design record Section 4) -------------------


def semantic_roles_comparable(
    *, same_underlying_primitive: bool, same_responsibility: bool
) -> bool:
    """A difference between two usages of the same field/function/path is a
    candidate only once both usages are established to serve the same
    responsibility. Sharing the same primitive is not, by itself, enough.

    Only meaningful when the candidate's own reasoning depends on comparing
    two or more usages/paths/implementations (design record Section 4,
    "Applicability") -- a standalone candidate with no such comparison never
    calls this at all."""
    return bool(same_underlying_primitive and same_responsibility)


# --- Causal validation chain (design record Section 6) --------------------


@dataclass(frozen=True)
class CausalChain:
    reviewed_change: str
    changed_assumption: str
    concrete_failure_condition: str = ""
    observable_incorrect_result: str = ""

    def is_complete(self) -> bool:
        """All four links must carry concrete evidence, not merely be
        asserted. An empty string means that link was never actually
        established."""
        return bool(
            self.reviewed_change
            and self.changed_assumption
            and self.concrete_failure_condition
            and self.observable_incorrect_result
        )


# --- Regression-proof discipline (design record Section 7) ----------------


@dataclass(frozen=True)
class RegressionClaim:
    prior_behavior_evidence: str = ""
    change_evidence: str = ""
    failure_scenario_evidence: str = ""
    causal_link_evidence: str = ""

    def is_proven(self) -> bool:
        """A regression may be presented as proven only when all four
        pieces of evidence are present."""
        return bool(
            self.prior_behavior_evidence
            and self.change_evidence
            and self.failure_scenario_evidence
            and self.causal_link_evidence
        )


# --- Disconfirmation pass (design record Section 8) ------------------------


class DisconfirmationOutcome(Enum):
    SURVIVES = "SURVIVES"
    DROPPED = "DROPPED"
    DOWNGRADED = "DOWNGRADED"
    RECLASSIFIED = "RECLASSIFIED"


def disconfirm(
    *,
    contradicting_evidence_found: bool = False,
    contradiction_is_authoritative: bool = False,
    contradiction_fully_disproves: bool = False,
    contradiction_reclassifies: bool = False,
) -> DisconfirmationOutcome:
    """The single disconfirmation outcome for a blocking candidate, given
    whatever contradicting evidence the bounded review context supplies.
    Check order mirrors the design record's table."""
    if not contradicting_evidence_found or not contradiction_is_authoritative:
        return DisconfirmationOutcome.SURVIVES
    if contradiction_fully_disproves:
        return DisconfirmationOutcome.DROPPED
    if contradiction_reclassifies:
        return DisconfirmationOutcome.RECLASSIFIED
    return DisconfirmationOutcome.DOWNGRADED


# --- Classification before severity (design record Section 9) -------------


class Classification(Enum):
    PROVEN_CORRECTNESS_DEFECT = "proven_correctness_defect"
    REQUIREMENT_AMBIGUITY = "requirement_ambiguity"
    TEST_COVERAGE_GAP = "test_coverage_gap"
    MAINTAINABILITY_CONCERN = "maintainability_concern"


# Only a proven correctness defect is normally blocking.
NORMALLY_BLOCKING: FrozenSet[Classification] = frozenset(
    {Classification.PROVEN_CORRECTNESS_DEFECT}
)


def is_normally_blocking(classification: Classification) -> bool:
    return classification in NORMALLY_BLOCKING


@dataclass(frozen=True)
class CandidateOutcome:
    """The result of running a candidate claim through the full pipeline.

    claim_valid and blocking_justification_valid are independent booleans
    (design record Section 9, "Finding validity is separate from
    blocking-justification validity") -- a finding may be kept
    (claim_valid=True) while not clearing the blocking bar
    (blocking_justification_valid=False); it is never suppressed on that
    basis alone.
    """

    claim_valid: bool
    blocking_justification_valid: bool
    classification: Classification | None


def evaluate_candidate(
    *,
    involves_comparison: bool = False,
    semantic_roles_ok: bool = True,
    grounding_sources: Sequence[GroundingSource],
    causal_chain: CausalChain,
    is_regression_claim: bool = False,
    regression_claim: RegressionClaim | None = None,
    disconfirmation: DisconfirmationOutcome = DisconfirmationOutcome.SURVIVES,
    material_impact: bool = True,
) -> CandidateOutcome:
    """Run a candidate claim through the full pipeline (design record
    Section 2) and return its outcome. Deterministic given the same inputs.

    `involves_comparison` states whether this candidate's own reasoning
    depends on comparing two or more usages/paths/implementations (design
    record Section 4, "Applicability"). Only then does `semantic_roles_ok`
    gate the candidate at all -- a standalone candidate (a technical
    invariant violation with no compared usage, for example) is not gated
    by semantic-role validation regardless of `semantic_roles_ok`'s value.
    """
    # Section 4: only a comparison-dependent candidate is gated here, and
    # only such a candidate can fail to be comparable in the first place.
    if involves_comparison and not semantic_roles_ok:
        return CandidateOutcome(
            claim_valid=False, blocking_justification_valid=False, classification=None
        )

    # Section 8: an authoritative, fully-disproving contradiction drops the
    # candidate entirely, regardless of what else it satisfies.
    if disconfirmation is DisconfirmationOutcome.DROPPED:
        return CandidateOutcome(
            claim_valid=False, blocking_justification_valid=False, classification=None
        )

    grounded = can_establish_blocking_premise(grounding_sources)
    causally_complete = causal_chain.is_complete()

    # Section 7: a regression claim must independently prove its own
    # four-part evidence set before it may be presented as proven.
    regression_proven = (
        bool(regression_claim) and regression_claim.is_proven()
        if is_regression_claim
        else True
    )

    blocking_justification_valid = bool(
        grounded
        and causally_complete
        and regression_proven
        and material_impact
        and disconfirmation in (DisconfirmationOutcome.SURVIVES,)
    )

    if blocking_justification_valid:
        classification = Classification.PROVEN_CORRECTNESS_DEFECT
    elif disconfirmation is DisconfirmationOutcome.RECLASSIFIED:
        classification = Classification.TEST_COVERAGE_GAP
    elif is_regression_claim and not regression_proven:
        classification = Classification.TEST_COVERAGE_GAP
    elif not grounded:
        classification = Classification.MAINTAINABILITY_CONCERN
    elif not causally_complete:
        classification = Classification.TEST_COVERAGE_GAP
    else:
        classification = Classification.REQUIREMENT_AMBIGUITY

    return CandidateOutcome(
        claim_valid=True,
        blocking_justification_valid=blocking_justification_valid,
        classification=classification,
    )


# --- Governance: this module's own shape never grows retrieval, mutation,
# or severity-computation capability (mirrors
# tests/reference/review/context_evidence.py) --------------------------

PROHIBITED_CAPABILITY_NAME_FRAGMENTS: FrozenSet[str] = frozenset(
    {
        "fetch",
        "retrieve",
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
        "compute_severity",
        "derive_severity",
        "override_severity",
        "render_chain_of_thought",
        "expose_reasoning",
    }
)


def public_callables() -> tuple[str, ...]:
    """Names a test can assert carry no prohibited capability fragment."""
    return (
        "can_establish_blocking_premise",
        "semantic_roles_comparable",
        "disconfirm",
        "is_normally_blocking",
        "evaluate_candidate",
    )
