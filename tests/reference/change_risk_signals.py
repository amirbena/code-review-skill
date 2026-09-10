"""Test-only reference model for change-risk signals and review depth (Issue #86).

This is test-only: not runtime logic, not packaged, and not imported by any
Skill. The canonical behavior lives in
``shared/policies/change-risk-signals.md``; this module makes that policy's
deterministic "Classification ordering", its ``>=`` diff-size thresholds,
and its depth-only conservative tie-break executable so the unit tests can
pin them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Sequence


class Tier(Enum):
    ELEVATED = "elevated"
    DEEP = "deep"


class Depth(Enum):
    STANDARD = "standard"
    ELEVATED = "elevated"
    DEEP = "deep"


# Ordered lowest-effort first; used by the depth-only conservative tie-break.
_DEPTH_ORDER = (Depth.STANDARD, Depth.ELEVATED, Depth.DEEP)

# The fixed catalog. ``diff_size`` is intentionally absent here — its tier is
# derived from measurements, not a constant (see ``diff_size_tier``).
SIGNAL_TIERS: dict[str, Tier] = {
    "auth": Tier.DEEP,
    "migration": Tier.DEEP,
    "concurrency": Tier.DEEP,
    "public_api": Tier.DEEP,
    "sensitive_path": Tier.ELEVATED,
    "infra_config": Tier.ELEVATED,
}
CATALOG_SIGNALS = frozenset({*SIGNAL_TIERS, "diff_size"})

# Authoritative diff-size thresholds (change-risk-signals.md, "Diff-size
# thresholds"). Boundary semantics are ``>=``.
ELEVATED_CHANGED_LINES = 150
DEEP_CHANGED_LINES = 600
ELEVATED_CHANGED_FILES = 10
DEEP_CHANGED_FILES = 30


@dataclass(frozen=True)
class ObservedFact:
    """One distinct changed thing (a file, or a coherent group of hunks).

    ``labels`` are the catalog signal keys this single fact supports —
    overlapping labels on one fact are expected and are deduplicated into a
    single occurrence by ``classify``.
    """

    fact_id: str
    labels: frozenset[str]
    evidence: str = ""


@dataclass(frozen=True)
class DiffSize:
    """Change size *after* excluding non-reviewable files (the caller applies
    ``file-reviewability.md`` before constructing this)."""

    changed_lines: int
    changed_files: int


@dataclass(frozen=True)
class Occurrence:
    """One resolved signal occurrence after per-fact deduplication."""

    source: str
    tier: Tier
    signals: tuple[str, ...]
    evidence: str


@dataclass(frozen=True)
class Classification:
    depth: Depth
    occurrences: tuple[Occurrence, ...] = ()

    def to_machine_model(self) -> dict[str, object]:
        """The policy's ``change_risk`` machine-readable shape: one entry per
        resolved occurrence (after deduplication)."""
        return {
            "change_risk": {
                "depth": self.depth.value,
                "occurrences": [
                    {
                        "signals": list(occ.signals),
                        "tier": occ.tier.value,
                        "evidence": occ.evidence,
                    }
                    for occ in self.occurrences
                ],
            }
        }


def _highest_tier(tiers: Iterable[Tier]) -> Tier:
    return Tier.DEEP if any(t is Tier.DEEP for t in tiers) else Tier.ELEVATED


def diff_size_tier(size: DiffSize) -> Tier | None:
    """Return the tier the diff-size signal activates at, or ``None``.

    ``>=`` boundaries; the higher of the line-count and file-count tiers wins.
    """
    if size.changed_lines < 0 or size.changed_files < 0:
        raise ValueError("diff size measurements cannot be negative")
    if size.changed_lines >= DEEP_CHANGED_LINES or size.changed_files >= DEEP_CHANGED_FILES:
        return Tier.DEEP
    if (
        size.changed_lines >= ELEVATED_CHANGED_LINES
        or size.changed_files >= ELEVATED_CHANGED_FILES
    ):
        return Tier.ELEVATED
    return None


def _validate(facts: Sequence[ObservedFact]) -> None:
    seen: set[str] = set()
    # An observed fact carries catalog signal labels only; ``diff_size`` is
    # never a fact label — it is derived from measurements via ``DiffSize``.
    fact_labels = CATALOG_SIGNALS - {"diff_size"}
    for fact in facts:
        if fact.fact_id in seen:
            raise ValueError(f"duplicate observed fact id: {fact.fact_id}")
        seen.add(fact.fact_id)
        unknown = set(fact.labels) - fact_labels
        if unknown:
            raise ValueError(f"unknown catalog signal label(s): {sorted(unknown)}")


def _aggregate(occurrences: Sequence[Occurrence]) -> Depth:
    """Steps 4-7 of "Classification ordering"."""
    if any(occ.tier is Tier.DEEP for occ in occurrences):
        return Depth.DEEP
    elevated = [occ for occ in occurrences if occ.tier is Tier.ELEVATED]
    if len(elevated) >= 2:
        return Depth.DEEP
    if len(elevated) == 1:
        return Depth.ELEVATED
    return Depth.STANDARD


def classify(
    facts: Sequence[ObservedFact] = (),
    diff_size: DiffSize | None = None,
    *,
    ambiguous_depth_candidates: Sequence[Depth] = (),
) -> Classification:
    """Derive the review depth deterministically per "Classification ordering".

    ``ambiguous_depth_candidates`` models the depth-only conservative
    tie-break: when the evidence plausibly supports several depths, the
    highest-effort one wins — and *only* the depth label is affected.
    """
    _validate(facts)
    occurrences: list[Occurrence] = []

    # Steps 1-3: detect labels per fact, dedup into one occurrence per fact,
    # resolve to the highest applicable tier.
    for fact in facts:
        labels = sorted(label for label in fact.labels if label in SIGNAL_TIERS)
        if not labels:
            continue
        tier = _highest_tier(SIGNAL_TIERS[label] for label in labels)
        occurrences.append(
            Occurrence(
                source=fact.fact_id,
                tier=tier,
                signals=tuple(labels),
                evidence=fact.evidence,
            )
        )

    if diff_size is not None:
        tier = diff_size_tier(diff_size)
        if tier is not None:
            occurrences.append(
                Occurrence(
                    source="diff-size",
                    tier=tier,
                    signals=("diff_size",),
                    evidence=(
                        f"{diff_size.changed_lines} changed lines, "
                        f"{diff_size.changed_files} changed files"
                    ),
                )
            )

    depth = _aggregate(occurrences)

    for candidate in ambiguous_depth_candidates:
        if _DEPTH_ORDER.index(candidate) > _DEPTH_ORDER.index(depth):
            depth = candidate

    return Classification(depth=depth, occurrences=tuple(occurrences))


def rationale_lines(classification: Classification) -> list[str]:
    """Human-facing subordinate-metadata rendering of the classification."""
    lines = [f"Change-risk depth: {classification.depth.value}"]
    if not classification.occurrences:
        lines.append("Change-risk signals: none")
        return lines
    for occ in classification.occurrences:
        for name in occ.signals:
            lines.append(
                f"Change-risk signal: {name} ({occ.tier.value}) — {occ.evidence}"
            )
    return lines
