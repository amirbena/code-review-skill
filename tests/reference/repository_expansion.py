"""Test-only reference model for repository expansion (Issue #87).

This is test-only: not runtime logic, not packaged, and not imported by any
Skill. The canonical behavior lives in
``shared/policies/repository-expansion.md``; this module makes that policy's
fixed trigger catalog, its ring-based bound, and the depth-scaled ceiling
executable so the unit tests can pin them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tests.reference.change_risk_signals import Depth

# The fixed trigger catalog.
CATALOG_TRIGGERS = frozenset(
    {"call_site", "interface_contract", "migration_schema", "config_consumer"}
)


class Ring(Enum):
    RING_1 = 1
    RING_2 = 2
    RING_3 = 3


# Maximum ring reachable for a given change-risk depth ("Expansion bound
# scales with change-risk depth").
_MAX_RING_FOR_DEPTH: dict[Depth, Ring | None] = {
    Depth.STANDARD: Ring.RING_1,
    Depth.ELEVATED: Ring.RING_2,
    Depth.DEEP: Ring.RING_3,
}


@dataclass(frozen=True)
class FiredTrigger:
    """One expansion trigger that fired, and how far its own resolution
    needed to go before it stopped (see "Stop at the first ring")."""

    trigger: str
    source: str
    resolved_at_ring: Ring
    locations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExpansionResult:
    fired: tuple[FiredTrigger, ...] = ()

    def to_machine_model(self) -> dict[str, object]:
        return {
            "repository_expansion": {
                "triggers": [
                    {
                        "trigger": ft.trigger,
                        "source": ft.source,
                        "ring_reached": ft.resolved_at_ring.value,
                        "locations": list(ft.locations),
                    }
                    for ft in self.fired
                ]
            }
        }


def max_ring_for_depth(depth: Depth) -> Ring:
    return _MAX_RING_FOR_DEPTH[depth]


def resolve(
    candidates: list[FiredTrigger],
    depth: Depth,
) -> ExpansionResult:
    """Cap each candidate trigger's resolution ring at the depth-scaled
    ceiling. A trigger whose own resolution needed a ring beyond the
    ceiling is capped at the ceiling — the ceiling never expands a trigger
    that resolved earlier (see "This is a ceiling, not a target").
    """
    unknown = {c.trigger for c in candidates} - CATALOG_TRIGGERS
    if unknown:
        raise ValueError(f"unknown expansion trigger(s): {sorted(unknown)}")

    ceiling = max_ring_for_depth(depth)
    capped: list[FiredTrigger] = []
    for candidate in candidates:
        ring = candidate.resolved_at_ring
        if ring.value > ceiling.value:
            ring = ceiling
        capped.append(
            FiredTrigger(
                trigger=candidate.trigger,
                source=candidate.source,
                resolved_at_ring=ring,
                locations=candidate.locations,
            )
        )
    return ExpansionResult(fired=tuple(capped))


def rationale_lines(result: ExpansionResult) -> list[str]:
    """Human-facing subordinate-metadata rendering of the expansion result."""
    if not result.fired:
        return ["Repository expansion: none"]
    lines: list[str] = []
    for ft in result.fired:
        locs = ", ".join(ft.locations) if ft.locations else "no locations recorded"
        lines.append(
            f"Repository expansion trigger: {ft.trigger} "
            f"(ring {ft.resolved_at_ring.value}) — {locs}"
        )
    return lines
