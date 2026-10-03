"""Test-only reference model: an oversized reviewed-SHA delta (Issue #203).

Not runtime logic and not packaged. Composes the large-PR-partitioning and
delta-re-review reference models per
``shared/policies/large-pr-partitioning.md`` ("Activation") and
``skills/github-pr-review/policies/reviewer-delta-review.md``
("Oversized delta").
"""

from __future__ import annotations

from tests.reference.review.delta_re_review import EscalationSignals, requires_escalation
from tests.reference.review.large_pr_partitioning import (
    ChangedFile,
    build_partitions,
    deduplicate,
)


def review_delta(
    delta_files: list[ChangedFile],
    unchanged_reviewed_files: list[ChangedFile],
    *,
    incomplete_partitions: frozenset[str] = frozenset(),
    surfaced: dict[str, tuple[str, ...]] | None = None,
    signals: EscalationSignals = EscalationSignals(),
) -> dict[str, object]:
    """Delta mode is already selected; measure and partition the delta only,
    aggregate, then reconcile once, then decide."""
    result = build_partitions(delta_files)
    steps = ["partition"] if result.activated else []
    partitioned_paths = {f.path for p in result.partitions for f in p.files}
    if result.activated:
        steps += ["aggregate", "reconcile"]
    else:
        steps += ["reconcile"]
    incomplete = any(p.partition_id in incomplete_partitions for p in result.partitions)
    return {
        "mode": "full" if requires_escalation(signals) else "delta",
        "partitioned": result.activated,
        "partitioned_paths": partitioned_paths,
        "steps": steps,
        "duplicates": deduplicate(surfaced or {}),
        "outcome": "REVIEW INCOMPLETE" if incomplete else "decided",
        "advances_reviewed_state": not incomplete,
        "unchanged_in_partitions": partitioned_paths
        & {f.path for f in unchanged_reviewed_files},
    }
