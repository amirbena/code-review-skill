"""Test-only reference model for large-PR partitioning (Issue #88).

This is test-only: not runtime logic, not packaged, and not imported by
any Skill. The canonical behavior lives in
``shared/policies/large-pr-partitioning.md``; this module makes that
policy's activation threshold, its deterministic partition-construction
ordering, and its cross-partition aggregation executable so the unit
tests can pin them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

# Authoritative partitioning threshold (large-pr-partitioning.md,
# "Partitioning threshold"). Boundary semantics are ``>=`` and exactly
# double change-risk-signals.md's ``deep`` threshold.
PARTITIONING_CHANGED_LINES = 1200
PARTITIONING_CHANGED_FILES = 60

# Per-partition size cap (large-pr-partitioning.md, "Partition
# construction", step 3) — change-risk-signals.md's own ``deep`` threshold
# measured on one partition.
PARTITION_CAP_CHANGED_LINES = 600
PARTITION_CAP_CHANGED_FILES = 30


@dataclass(frozen=True)
class ChangedFile:
    """One in-scope changed file (non-reviewable files already excluded)."""

    path: str
    directory: str
    changed_lines: int
    coherence_group: str | None = None


def activates(total_changed_lines: int, total_changed_files: int) -> bool:
    """Whether the change's diff-size measurement activates partitioning."""
    if total_changed_lines < 0 or total_changed_files < 0:
        raise ValueError("diff size measurements cannot be negative")
    return (
        total_changed_lines >= PARTITIONING_CHANGED_LINES
        or total_changed_files >= PARTITIONING_CHANGED_FILES
    )


@dataclass(frozen=True)
class Partition:
    partition_id: str
    files: tuple[ChangedFile, ...]
    capped: bool = False

    @property
    def changed_lines(self) -> int:
        return sum(f.changed_lines for f in self.files)

    @property
    def changed_files(self) -> int:
        return len(self.files)


@dataclass(frozen=True)
class PartitioningResult:
    activated: bool
    partitions: tuple[Partition, ...] = field(default_factory=tuple)

    def to_machine_model(self) -> dict[str, object]:
        return {
            "large_pr_partitioning": {
                "activated": self.activated,
                "threshold": {
                    "changed_lines": PARTITIONING_CHANGED_LINES,
                    "changed_files": PARTITIONING_CHANGED_FILES,
                },
                "partitions": [
                    {
                        "id": p.partition_id,
                        "files": [f.path for f in p.files],
                        "changed_lines": p.changed_lines,
                        "changed_files": p.changed_files,
                        "capped": p.capped,
                    }
                    for p in self.partitions
                ]
                if self.activated
                else [],
            }
        }


def _exceeds_cap(files: tuple[ChangedFile, ...]) -> bool:
    lines = sum(f.changed_lines for f in files)
    return (
        lines >= PARTITION_CAP_CHANGED_LINES
        or len(files) >= PARTITION_CAP_CHANGED_FILES
    )


def build_partitions(files: Sequence["ChangedFile"]) -> PartitioningResult:
    """Deterministic partition construction per "Partition construction".

    Steps 1-2 (directory seed, then evidence-based coherence merge) are
    modeled by grouping first on ``coherence_group`` when present (the
    evidence-established merge target), else on ``directory``. Step 3 (the
    per-partition size cap) flags a cluster that still exceeds the cap
    after grouping as ``capped`` rather than breaking a coherence group to
    shrink it (coherence is never broken for size — see step 5,
    "Oversized-partition flag").
    """
    total_lines = sum(f.changed_lines for f in files)
    total_files = len(files)
    if not activates(total_lines, total_files):
        return PartitioningResult(activated=False)

    groups: dict[str, list[ChangedFile]] = {}
    for f in files:
        key = f.coherence_group or f.directory
        groups.setdefault(key, []).append(f)

    partitions = []
    for idx, key in enumerate(sorted(groups), start=1):
        group_files = tuple(groups[key])
        partitions.append(
            Partition(
                partition_id=f"P{idx}",
                files=group_files,
                capped=_exceeds_cap(group_files),
            )
        )
    return PartitioningResult(activated=True, partitions=tuple(partitions))


@dataclass(frozen=True)
class CrossPartitionDuplicate:
    owning_partition: str
    also_surfaced_in: tuple[str, ...]


def deduplicate(
    candidate_locations: dict[str, tuple[str, ...]],
) -> tuple[CrossPartitionDuplicate, ...]:
    """Centralized cross-partition aggregation ("Aggregation and
    cross-partition de-duplication"): a finding surfaced from more than one
    partition is attributed once, to the first (lowest-id) partition that
    observed it — partition completion order never affects the result."""
    result = []
    for finding_id, partitions in candidate_locations.items():
        if len(partitions) <= 1:
            continue
        ordered = tuple(sorted(partitions))
        result.append(
            CrossPartitionDuplicate(
                owning_partition=ordered[0],
                also_surfaced_in=ordered[1:],
            )
        )
    return tuple(result)


def rationale_lines(result: PartitioningResult) -> list[str]:
    """Human-facing subordinate-metadata rendering — rendered only when
    partitioning activated (see "Reporting"); an inactive result renders
    nothing at all, unlike the always-on change-risk/expansion pair."""
    if not result.activated:
        return []
    lines = [f"Large-PR partitioning: {len(result.partitions)} partitions"]
    for p in result.partitions:
        if p.capped:
            lines.append(f"Large-PR partitioning: {p.partition_id} capped")
    return lines
