"""Unit tests pinning the large-PR-partitioning reference model (Issue #88).

Canonical behavior: ``shared/policies/large-pr-partitioning.md``.
"""

from __future__ import annotations

import unittest

from tests.reference.large_pr_partitioning import (
    ChangedFile,
    PARTITIONING_CHANGED_FILES,
    PARTITIONING_CHANGED_LINES,
    PARTITION_CAP_CHANGED_FILES,
    PARTITION_CAP_CHANGED_LINES,
    activates,
    build_partitions,
    deduplicate,
    rationale_lines,
)


class ActivationThresholdTests(unittest.TestCase):
    def test_below_threshold_does_not_activate(self) -> None:
        self.assertFalse(activates(PARTITIONING_CHANGED_LINES - 1, 1))
        self.assertFalse(activates(1, PARTITIONING_CHANGED_FILES - 1))

    def test_at_line_threshold_activates(self) -> None:
        self.assertTrue(activates(PARTITIONING_CHANGED_LINES, 1))

    def test_at_file_threshold_activates(self) -> None:
        self.assertTrue(activates(1, PARTITIONING_CHANGED_FILES))

    def test_above_threshold_activates(self) -> None:
        self.assertTrue(activates(PARTITIONING_CHANGED_LINES + 1, 1))

    def test_negative_measurement_rejected(self) -> None:
        with self.assertRaises(ValueError):
            activates(-1, 0)


class PartitionConstructionTests(unittest.TestCase):
    def test_small_change_is_not_partitioned(self) -> None:
        files = [ChangedFile("a.py", "a", 10)]
        result = build_partitions(files)
        self.assertFalse(result.activated)
        self.assertEqual(result.partitions, ())

    def test_activated_change_seeds_by_directory(self) -> None:
        files = [
            ChangedFile("a/x.py", "a", 700),
            ChangedFile("a/y.py", "a", 600),
            ChangedFile("b/z.py", "b", 1),
        ]
        result = build_partitions(files)
        self.assertTrue(result.activated)
        ids_to_files = {p.partition_id: {f.path for f in p.files} for p in result.partitions}
        self.assertIn({"a/x.py", "a/y.py"}, ids_to_files.values())
        self.assertIn({"b/z.py"}, ids_to_files.values())

    def test_coherence_group_merges_across_directories(self) -> None:
        files = [
            ChangedFile("api/controller.py", "api", 400, coherence_group="feature-x"),
            ChangedFile("schema/dto.py", "schema", 300, coherence_group="feature-x"),
            ChangedFile("unrelated/thing.py", "unrelated", 500),
        ]
        result = build_partitions(files)
        self.assertTrue(result.activated)
        merged = [p for p in result.partitions if len(p.files) == 2]
        self.assertEqual(len(merged), 1)
        self.assertEqual(
            {f.path for f in merged[0].files},
            {"api/controller.py", "schema/dto.py"},
        )
        self.assertEqual(len(merged[0].coherence_merges), 1)

    def test_directory_seeded_group_records_no_coherence_merge(self) -> None:
        files = [
            ChangedFile("a/x.py", "a", 700),
            ChangedFile("a/y.py", "a", 600),
        ]
        result = build_partitions(files)
        directory_group = next(p for p in result.partitions if len(p.files) == 2)
        self.assertEqual(directory_group.coherence_merges, ())

    def test_to_machine_model_carries_coherence_merges(self) -> None:
        files = [
            ChangedFile("api/controller.py", "api", 400, coherence_group="feature-x"),
            ChangedFile("schema/dto.py", "schema", 300, coherence_group="feature-x"),
            ChangedFile("unrelated/thing.py", "unrelated", 500),
        ]
        result = build_partitions(files)
        model = result.to_machine_model()["large_pr_partitioning"]
        merged_entry = next(p for p in model["partitions"] if len(p["files"]) == 2)
        self.assertEqual(len(merged_entry["coherence_merges"]), 1)

    def test_oversized_coherent_group_flagged_capped_not_split(self) -> None:
        files = [
            ChangedFile("big/one.py", "big", 400, coherence_group="monolith"),
            ChangedFile("big/two.py", "big", 400, coherence_group="monolith"),
            # Pad the change past the overall activation threshold without
            # joining the "monolith" coherence group.
            ChangedFile("other/pad.py", "other", PARTITIONING_CHANGED_LINES),
        ]
        result = build_partitions(files)
        self.assertTrue(result.activated)
        partition = next(p for p in result.partitions if len(p.files) == 2)
        self.assertTrue(partition.capped)
        self.assertEqual({f.path for f in partition.files}, {"big/one.py", "big/two.py"})

    def test_partition_cap_boundary_is_inclusive(self) -> None:
        files = [ChangedFile("x/a.py", "x", PARTITION_CAP_CHANGED_LINES, coherence_group="g")]
        # Pad the change past the activation threshold without affecting this group.
        files.append(ChangedFile("y/b.py", "y", PARTITIONING_CHANGED_LINES))
        result = build_partitions(files)
        capped = next(p for p in result.partitions if any(f.coherence_group == "g" for f in p.files))
        self.assertTrue(capped.capped)

    def test_deterministic_given_same_input(self) -> None:
        files = [
            ChangedFile("a/x.py", "a", 700),
            ChangedFile("b/y.py", "b", 600),
        ]
        first = build_partitions(files)
        second = build_partitions(list(files))
        self.assertEqual(first, second)


class CrossPartitionDeduplicationTests(unittest.TestCase):
    def test_single_surfacing_is_not_a_duplicate(self) -> None:
        self.assertEqual(deduplicate({"f1": ("P1",)}), ())

    def test_duplicate_attributed_to_lowest_id_partition(self) -> None:
        result = deduplicate({"f1": ("P2", "P1")})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].owning_partition, "P1")
        self.assertEqual(result[0].also_surfaced_in, ("P2",))

    def test_completion_order_does_not_affect_result(self) -> None:
        a = deduplicate({"f1": ("P3", "P1", "P2")})
        b = deduplicate({"f1": ("P1", "P2", "P3")})
        self.assertEqual(a, b)


class RationaleRenderingTests(unittest.TestCase):
    def test_inactive_result_renders_nothing(self) -> None:
        result = build_partitions([ChangedFile("a.py", "a", 1)])
        self.assertEqual(rationale_lines(result), [])

    def test_active_result_renders_partition_count(self) -> None:
        files = [
            ChangedFile("a/x.py", "a", 700),
            ChangedFile("b/y.py", "b", 600),
        ]
        result = build_partitions(files)
        lines = rationale_lines(result)
        self.assertIn("Large-PR partitioning: 2 partitions", lines)

    def test_capped_partition_is_called_out(self) -> None:
        files = [
            ChangedFile("big/one.py", "big", 700, coherence_group="monolith"),
            ChangedFile("big/two.py", "big", 700, coherence_group="monolith"),
            ChangedFile("other/pad.py", "other", PARTITIONING_CHANGED_LINES),
        ]
        result = build_partitions(files)
        lines = rationale_lines(result)
        self.assertTrue(any("capped" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
