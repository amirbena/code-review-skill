#!/usr/bin/env python3
"""Test-only reference model for shared/policies/design-reference.md.

Not runtime logic, not packaged. It models the deterministic parts of the
contract: trusted-vs-discovered provenance, mode selection, the authority
reducers, mismatch classification, and the evidence record. No design service
is involved.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from tests.reference.review.rendered_inspection import Mode


class Source(Enum):
    INVOCATION = "invocation"
    OUT_OF_BAND = "out-of-band"
    PR_BODY = "pr-body"
    COMMENT = "comment"
    COMMIT_MESSAGE = "commit-message"
    REPOSITORY_FILE = "repository-file"
    ISSUE_TEXT = "issue-text"
    OPERATOR_SUPPLIED_CONTEXT = "operator-supplied-context"


TRUSTED_SOURCES = frozenset({Source.INVOCATION, Source.OUT_OF_BAND})


@dataclass(frozen=True)
class Reference:
    source: Source
    named_as_design_reference: bool = False


def is_trusted(reference: Reference) -> bool:
    """Only an operator-supplied reference is trusted. A link inside
    operator-supplied context stays discovered unless the operator names it."""
    if reference.source in TRUSTED_SOURCES:
        return True
    return (
        reference.source is Source.OPERATOR_SUPPLIED_CONTEXT
        and reference.named_as_design_reference
    )


def may_fetch(reference: Reference) -> bool:
    """A discovered reference is never resolved, fetched, or promoted."""
    return is_trusted(reference)


def limitation_lines(references: Sequence[Reference]) -> int:
    """At most one limitation line says a discovered reference was not used."""
    return 1 if any(not is_trusted(r) for r in references) else 0


@dataclass(frozen=True)
class Retrieval:
    reference: Reference | None
    retrieved: bool
    applicable: bool
    render_inspected: bool


def select_mode(retrieval: Retrieval) -> Mode:
    """Design-reference mode needs a trusted, retrieved, applicable reference
    and an actual render; every other case is analytical."""
    if (
        retrieval.reference is not None
        and is_trusted(retrieval.reference)
        and retrieval.retrieved
        and retrieval.applicable
        and retrieval.render_inspected
    ):
        return Mode.DESIGN_REFERENCE
    return Mode.ANALYTICAL


def may_claim_design_requirement(mode: Mode) -> bool:
    """No "the design says" claim in analytical mode."""
    return mode is Mode.DESIGN_REFERENCE


def review_blocked_by_design(retrieval: Retrieval) -> bool:
    """An inaccessible design never stops the review or makes it incomplete."""
    return False


@dataclass(frozen=True)
class Reducers:
    stale: bool = False
    intentional_divergence: bool = False
    partial_coverage_for_point: bool = False
    responsive_or_state_ambiguity: bool = False
    newer_requirement_addresses_point: bool = False

    def any(self) -> bool:
        return any(
            (
                self.stale,
                self.intentional_divergence,
                self.partial_coverage_for_point,
                self.responsive_or_state_ambiguity,
                self.newer_requirement_addresses_point,
            )
        )


class Route(Enum):
    FINDING = "finding"
    OBSERVATION = "observation"
    NOTE = "note"
    NOT_REPORTED = "not-reported"


@dataclass(frozen=True)
class Mismatch:
    concrete_cost: bool
    in_demonstrated_scope: bool = True
    evidence_on_design_side: bool = True
    evidence_on_rendered_side: bool = True
    tests_pass: bool = False
    reducers: Reducers = Reducers()


def classify(mismatch: Mismatch, mode: Mode) -> Route:
    """Classification of a design mismatch. A passing test never silences a
    concrete in-scope mismatch; a reducer demotes it to a note."""
    if mode is not Mode.DESIGN_REFERENCE:
        return Route.NOT_REPORTED
    if not mismatch.in_demonstrated_scope:
        return Route.NOT_REPORTED
    if not (mismatch.evidence_on_design_side and mismatch.evidence_on_rendered_side):
        return Route.NOT_REPORTED
    if mismatch.reducers.any():
        return Route.NOTE
    return Route.FINDING if mismatch.concrete_cost else Route.OBSERVATION


def record_design_line(
    mode: Mode,
    *,
    reference: str,
    supplied_via: str,
    matched: str,
    match_basis: str,
    coverage: str,
    freshness: str,
) -> str | None:
    """The optional design-reference line: present only in design-reference
    mode, absent in analytical mode."""
    if mode is not Mode.DESIGN_REFERENCE:
        return None
    return (
        f"Design reference: {reference} · supplied via {supplied_via} · "
        f"matched {matched} · basis {match_basis} · coverage {coverage} · "
        f"freshness {freshness}"
    )


def uncertainty_consumes_cap(_line: str) -> bool:
    """Provenance/applicability/freshness uncertainty never uses the cap."""
    return False


MUTATING_OPERATIONS = frozenset({"comment", "edit", "share", "delete"})
PERMISSION_OPERATIONS = frozenset({"request-permission", "authenticate"})


def operation_allowed(operation: str) -> bool:
    """Retrieval is read-only and initiates no permission or auth flow."""
    return operation not in MUTATING_OPERATIONS | PERMISSION_OPERATIONS
