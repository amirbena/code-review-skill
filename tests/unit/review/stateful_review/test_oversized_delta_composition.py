"""Composition tests for an oversized reviewed-SHA delta (Issue #203).

Exercises ``tests/reference/review/oversized_delta.py``; canonical behavior:
``shared/policies/large-pr-partitioning.md`` ("Activation") and ``skills/github-pr-review/policies/reviewer-delta-review.md``
("Oversized delta").
"""

from __future__ import annotations

import dataclasses
import unittest

from tests.reference.review.delta_re_review import EscalationSignals, requires_escalation
from tests.reference.review.large_pr_partitioning import (
    ChangedFile,
    PARTITIONING_CHANGED_FILES,
    build_partitions,
)
from tests.reference.review.oversized_delta import review_delta


def _file(path: str, directory: str, lines: int) -> ChangedFile:
    return ChangedFile(path=path, directory=directory, changed_lines=lines)


def _oversized_delta() -> list[ChangedFile]:
    return [
        _file(f"svc/mod{i}/f.py", f"svc/mod{i}", 10)
        for i in range(PARTITIONING_CHANGED_FILES)
    ]


class OversizedDeltaCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.delta = _oversized_delta()
        self.unchanged = [_file(f"old/f{i}.py", "old", 900) for i in range(5)]

    def test_delta_at_threshold_partitions_only_delta_files(self) -> None:
        out = review_delta(self.delta, self.unchanged)
        self.assertTrue(out["partitioned"])
        self.assertEqual(out["partitioned_paths"], {f.path for f in self.delta})
        self.assertEqual(out["unchanged_in_partitions"], set())

    def test_unchanged_reviewed_code_does_not_count_toward_threshold(self) -> None:
        small = self.delta[: PARTITIONING_CHANGED_FILES - 1]
        out = review_delta(small, self.unchanged)
        self.assertFalse(out["partitioned"])
        self.assertEqual(out["steps"], ["reconcile"])

    def test_aggregation_precedes_reconciliation(self) -> None:
        steps = review_delta(self.delta, self.unchanged)["steps"]
        self.assertEqual(steps, ["partition", "aggregate", "reconcile"])

    def test_cross_partition_duplicates_collapse_before_reconciliation(self) -> None:
        out = review_delta(self.delta, self.unchanged, surfaced={"F1": ("P2", "P1")})
        self.assertEqual(len(out["duplicates"]), 1)
        self.assertEqual(out["duplicates"][0].owning_partition, "P1")

    def test_incomplete_partition_is_review_incomplete_and_does_not_advance(self) -> None:
        result = build_partitions(self.delta)
        out = review_delta(
            self.delta,
            self.unchanged,
            incomplete_partitions=frozenset({result.partitions[0].partition_id}),
        )
        self.assertEqual(out["outcome"], "REVIEW INCOMPLETE")
        self.assertFalse(out["advances_reviewed_state"])

    def test_complete_oversized_delta_advances_reviewed_state(self) -> None:
        out = review_delta(self.delta, self.unchanged)
        self.assertEqual(out["outcome"], "decided")
        self.assertTrue(out["advances_reviewed_state"])

    def test_size_is_not_an_escalation_input(self) -> None:
        names = {f.name for f in dataclasses.fields(EscalationSignals)}
        self.assertFalse(any("size" in n or "line" in n or "file" in n for n in names))
        out = review_delta(self.delta, self.unchanged)
        self.assertEqual(out["mode"], "delta")
        self.assertFalse(requires_escalation(EscalationSignals()))

    def test_semantic_trigger_still_escalates_an_oversized_delta(self) -> None:
        out = review_delta(
            self.delta,
            self.unchanged,
            signals=EscalationSignals(blast_radius_untraceable=True),
        )
        self.assertEqual(out["mode"], "full")


if __name__ == "__main__":
    unittest.main()
