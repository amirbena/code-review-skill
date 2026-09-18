#!/usr/bin/env python3
"""Policy guard: the committed inverted index stays in sync with the live
corpus (Issue #333). Contract: runtime_platform/benchmark/taxonomy.md §5.

The index (docs/benchmark/corpus-index.json) is a build artifact, never
hand-edited: this test regenerates it in memory from the live corpus and
fails if the committed file diverges, exactly the way
runtime_platform/benchmark/scripts/build_benchmark_index.py --check does for local/CI use.
"""

from __future__ import annotations

import unittest

from runtime_platform.benchmark.scripts import build_benchmark_index as idx
from tests.support.paths import REPO_ROOT

INDEX_PATH = REPO_ROOT / "docs" / "benchmark" / "corpus-index.json"


class IndexSyncTests(unittest.TestCase):
    def test_committed_index_exists(self) -> None:
        self.assertTrue(INDEX_PATH.is_file(), f"missing {INDEX_PATH}")

    def test_committed_index_matches_a_fresh_build_from_the_live_corpus(self) -> None:
        fresh = idx.render_index(idx.build_index())
        committed = INDEX_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            committed,
            fresh,
            "docs/benchmark/corpus-index.json is out of sync with the live "
            "corpus — run runtime_platform/benchmark/scripts/build_benchmark_index.py to "
            "regenerate it",
        )


if __name__ == "__main__":
    unittest.main()
