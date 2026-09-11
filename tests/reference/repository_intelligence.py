#!/usr/bin/env python3
"""Test-only reference for the repository-intelligence model (Issue #129).
Not runtime logic, not packaged — the packaged Skills are Markdown/YAML
only.

Mirrors docs/repository-intelligence/repository-intelligence-model.md: the
typed entity/relationship model, the ring-bounded retrieval it makes
inspectable inside a ring shared/policies/repository-expansion.md (#87)
already authorized, snapshot identity and staleness (reject-and-rebuild,
never silent reuse), relationship-influence attribution
(`influential_relationships`), and safe failure for ambiguous / unsupported
/ missing-data candidates (never a resolved edge, never influential).
`influential_relationships` is *recorded and exposed* per fixture/worked
example here, not computed by a general-purpose materiality algorithm over
arbitrary repository state — proving the contract, not implementing
inference.

#87 (repository-expansion.md) stays canonical for *when* an investigation
expands past the diff, *which trigger* authorizes it, and *how far* (the
ring ceiling). This module never re-derives or loosens that ceiling; it only
models what a ring-authorized investigation resolves.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Sequence


# --- Change-risk depth and the #87 ring ceiling (unchanged, just reused) --


class ChangeRiskDepth(Enum):
    STANDARD = "standard"
    ELEVATED = "elevated"
    DEEP = "deep"


RING_CEILING: dict[ChangeRiskDepth, int] = {
    ChangeRiskDepth.STANDARD: 1,
    ChangeRiskDepth.ELEVATED: 2,
    ChangeRiskDepth.DEEP: 3,
}


def ring_ceiling_for(depth: ChangeRiskDepth) -> int:
    """The maximum ring #87 authorizes for this change-risk depth. This
    model never reaches further than this ceiling and never re-derives it —
    repository-expansion.md stays the sole owner of the ceiling itself."""
    return RING_CEILING[depth]


# --- The typed entity/relationship model (design record §4) --------------


class EntityKind(Enum):
    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    SYMBOL = "symbol"


class RelationshipKind(Enum):
    CALLS = "calls"
    IMPLEMENTS = "implements"
    REFERENCES = "references"
    IMPORTS = "imports"


class Trigger(Enum):
    """The fixed #87 trigger catalog, reused verbatim — this model tags
    every relationship with the trigger that would surface it, it does not
    invent a competing catalog."""

    CALL_SITE = "call_site"
    INTERFACE_CONTRACT = "interface_contract"
    MIGRATION_SCHEMA = "migration_schema"
    CONFIG_CONSUMER = "config_consumer"


# Which (relationship kind, trigger) pairings are meaningful. Closed set —
# an edge outside this set is a modeling error, not a permissive default.
ALLOWED_KIND_TRIGGER_PAIRS: FrozenSet[tuple[RelationshipKind, Trigger]] = frozenset(
    {
        (RelationshipKind.CALLS, Trigger.CALL_SITE),
        (RelationshipKind.IMPORTS, Trigger.CALL_SITE),
        (RelationshipKind.IMPLEMENTS, Trigger.INTERFACE_CONTRACT),
        (RelationshipKind.REFERENCES, Trigger.MIGRATION_SCHEMA),
        (RelationshipKind.REFERENCES, Trigger.CONFIG_CONSUMER),
    }
)


@dataclass(frozen=True)
class Entity:
    kind: EntityKind
    qualified_name: str
    path: str  # repo-relative POSIX path


@dataclass(frozen=True)
class Provenance:
    """Source evidence for one retrieved relationship — the file:line of the
    referencing edge, same evidentiary bar as evidence.md already requires,
    made explicit for graph-sourced facts specifically (design record §6)."""

    path: str
    line: int

    def location(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass(frozen=True)
class Relationship:
    """A single resolved, in-ring edge. Construction validates the
    (kind, trigger) pairing and the ring bound so an invalid edge can never
    be represented, let alone retrieved."""

    kind: RelationshipKind
    trigger: Trigger
    source: Entity
    target: Entity
    ring: int  # the ring (1..3) at which this edge was resolved
    provenance: Provenance

    def __post_init__(self) -> None:
        if (self.kind, self.trigger) not in ALLOWED_KIND_TRIGGER_PAIRS:
            raise ValueError(
                f"relationship kind {self.kind} is not modeled for trigger {self.trigger}"
            )
        if self.ring not in (1, 2, 3):
            raise ValueError(f"ring must be 1, 2, or 3, got {self.ring}")


class UnresolvedReason(Enum):
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED_LANGUAGE = "unsupported_language"
    MISSING_DATA = "missing_data"


@dataclass(frozen=True)
class UnresolvedCandidate:
    """A candidate relationship that did not successfully resolve — dynamic
    dispatch, reflection, an unsupported language shape, or missing data.
    This is *not* a relationship: it is a diagnostic record only, and it
    must never become a resolved edge, appear in `influential_relationships`,
    or support a finding (design record §9)."""

    reason: UnresolvedReason
    note: str


# --- Snapshot identity and staleness (design record §7) ------------------


class StaleIndexError(Exception):
    """Raised when the reviewed worktree's snapshot identity no longer
    matches the index's bound snapshot identity. The index is rejected and
    discarded outright; a rebuild is required. A review must never silently
    continue on stale relationship data — this is a hard reject, not a soft
    warning. Git / the current worktree remains the sole source of truth;
    this index never persists across reviews or claims independent
    authority."""


@dataclass(frozen=True)
class SnapshotIndex:
    """An ephemeral, per-review, trigger-scoped index bound to one explicit
    repository snapshot identity (a commit/worktree token in real use, a
    fixture-declared snapshot id in tests). It is never persisted across
    reviews."""

    snapshot_id: str
    edges: tuple[Relationship, ...] = ()
    unresolved: tuple[UnresolvedCandidate, ...] = ()


@dataclass(frozen=True)
class RetrievalResult:
    snapshot_id: str
    resolved_edges: tuple[Relationship, ...]
    unresolved: tuple[UnresolvedCandidate, ...]
    influential_relationships: tuple[Relationship, ...]

    def is_influential(self, edge: Relationship) -> bool:
        return edge in self.influential_relationships


def retrieve(
    *,
    index: SnapshotIndex,
    reviewed_snapshot_id: str,
    ring_ceiling: int,
    influential: Sequence[Relationship] = (),
) -> RetrievalResult:
    """Resolve an index against the ring #87 already authorized for this
    review.

    - Snapshot mismatch -> `StaleIndexError`: reject and discard, never
      silently continue (design record §7).
    - Only edges within `ring_ceiling` are in the resolved set; the ceiling
      itself is never re-derived here, only respected (design record §5).
    - `influential` is fixture/reference-designated data (design record
      §8), not computed by a general algorithm; every entry MUST already be
      in the resolved set — an edge that was never resolved (including any
      `UnresolvedCandidate`) can never be marked influential.
    - `unresolved` candidates pass through unchanged: they are never
      filtered into, or promoted from, the resolved edge set.
    """
    if reviewed_snapshot_id != index.snapshot_id:
        raise StaleIndexError(
            f"index snapshot {index.snapshot_id!r} does not match reviewed "
            f"snapshot {reviewed_snapshot_id!r}; discard and rebuild"
        )
    if ring_ceiling not in (1, 2, 3):
        raise ValueError(f"ring_ceiling must be 1, 2, or 3, got {ring_ceiling}")

    resolved = tuple(e for e in index.edges if e.ring <= ring_ceiling)

    for edge in influential:
        if edge not in resolved:
            raise ValueError(
                "an influential relationship must already be in the resolved "
                f"edge set: {edge!r}"
            )

    return RetrievalResult(
        snapshot_id=index.snapshot_id,
        resolved_edges=resolved,
        unresolved=index.unresolved,
        influential_relationships=tuple(influential),
    )


def is_safe_failure(result: RetrievalResult) -> bool:
    """A retrieval carrying only unresolved candidates and no resolved edge
    for them is the documented safe-failure shape: 'insufficient evidence',
    never an invented relationship."""
    return bool(result.unresolved)


# --- Governance: this module's own shape never grows persistence,
# cross-repository, mutation, or invented-relationship capability (mirrors
# tests/reference/context_evidence.py) -------------------------------------

PROHIBITED_CAPABILITY_NAME_FRAGMENTS: FrozenSet[str] = frozenset(
    {
        "persist",
        "graph_db",
        "graphdb",
        "cross_repo",
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
        "background_index",
        "daemon",
        "invent_relationship",
        "guess_relationship",
        "assume_resolved",
    }
)


def public_callables() -> tuple[str, ...]:
    """Names a test can assert carry no prohibited capability fragment."""
    return (
        "ring_ceiling_for",
        "retrieve",
        "is_safe_failure",
        "location",
        "is_influential",
    )
