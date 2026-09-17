"""Unit coverage for the capability-loading baseline measurement (#408).

Structural invariants only, not pinned word counts: the static surface
grows and shrinks with ordinary policy edits, so a test asserting exact
totals would fail on unrelated changes. What must hold regardless of
content is the attribution arithmetic itself.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.capability_architecture import capability_loading_baseline as clb


class AttributeTests(unittest.TestCase):
    def test_splits_words_between_capability_and_core(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "owned.md").write_text("one two three", encoding="utf-8")
            (root / "unowned.md").write_text("four five", encoding="utf-8")
            original_root = clb.REPO_ROOT
            clb.REPO_ROOT = root
            try:
                result = clb._attribute(
                    ["owned.md", "unowned.md"], {"some-capability": ["owned.md"]}
                )
            finally:
                clb.REPO_ROOT = original_root

        self.assertEqual(result["total_words"], 5)
        self.assertEqual(result["core_unattributed_words"], 2)
        self.assertEqual(result["by_capability_words"], {"some-capability": 3})

    def test_total_is_always_core_plus_capability_sum(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.md").write_text("a a a a", encoding="utf-8")
            (root / "b.md").write_text("b b", encoding="utf-8")
            (root / "c.md").write_text("c", encoding="utf-8")
            original_root = clb.REPO_ROOT
            clb.REPO_ROOT = root
            try:
                result = clb._attribute(
                    ["a.md", "b.md", "c.md"],
                    {"cap-1": ["a.md"], "cap-2": ["b.md"]},
                )
            finally:
                clb.REPO_ROOT = original_root

        self.assertEqual(
            result["total_words"],
            result["core_unattributed_words"] + sum(result["by_capability_words"].values()),
        )
        self.assertEqual(result["core_unattributed_words"], 1)


class MeasureStaticSurfaceTests(unittest.TestCase):
    def test_every_adapter_section_is_internally_consistent(self) -> None:
        surface = clb.measure_static_surface()

        self.assertEqual(set(surface), set(clb.ADAPTER_SECTIONS))
        for adapter, section in surface.items():
            with self.subTest(adapter=adapter):
                self.assertEqual(
                    section["total_words"],
                    section["core_unattributed_words"]
                    + sum(section["by_capability_words"].values()),
                )
                self.assertGreater(section["total_words"], 0)
                self.assertEqual(
                    section["total_tokens_est"],
                    round(section["total_words"] * clb.WORDS_TO_TOKENS),
                )

    def test_every_attributed_capability_is_a_real_capability_yaml(self) -> None:
        capability_files = clb._load_capability_files()
        surface = clb.measure_static_surface()

        for section in surface.values():
            for capability in section["by_capability_words"]:
                self.assertIn(capability, capability_files)


if __name__ == "__main__":
    unittest.main()
