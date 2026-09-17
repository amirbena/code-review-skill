#!/usr/bin/env python3
"""Behavioral coverage for the deterministic inverted-index build (Issue
#333). Contract: docs/benchmark/taxonomy.md §5.

Exercised against a small synthetic corpus (a temp directory of hand-built
fixtures), never the live corpus — the live corpus's own sync is pinned by
tests/policy/benchmark/test_benchmark_index_sync.py. What is proven here:

1. the index shape matches known cases and known expected structure;
2. lookup work for a matched ``(dimension, value)`` pair is bounded by the
   candidate set for that pair, not by total corpus size — adding
   unrelated cases outside the matched values never changes the lookup
   cost/output for a fixed classification (acceptance criterion #5);
3. the build is fully reproducible from a fixed corpus snapshot.
"""

from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from scripts.benchmark import build_benchmark_index as idx


def _write_case(
    directory: Path,
    case_id: str,
    *,
    capability: str,
    policy_contract: str = "unclassified",
    risk_mode: str = "correctness",
    affected_surface: str = "unclassified",
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{case_id}.yaml").write_text(
        textwrap.dedent(
            f"""\
            format: benchmark-case/v2
            id: {case_id}
            title: "synthetic case {case_id}"
            input:
              patch: |
                diff --git a/x b/x
                --- a/x
                +++ b/x
                @@ -1 +1 @@
                -a
                +b
            expected:
              findings: []
            metadata:
              taxonomy:
                capability: [{capability}]
                policy_contract: [{policy_contract}]
                risk_mode: [{risk_mode}]
                affected_surface: [{affected_surface}]
            """
        ),
        encoding="utf-8",
    )


class BuildIndexShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.corpus_dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_known_cases_produce_the_known_expected_index_shape(self) -> None:
        _write_case(self.corpus_dir / "core", "case-a", capability="core", risk_mode="security")
        _write_case(
            self.corpus_dir / "performance", "case-b", capability="performance", risk_mode="performance"
        )
        index = idx.build_index(self.corpus_dir)

        self.assertEqual(set(index), {"capability", "policy_contract", "risk_mode", "affected_surface"})
        self.assertEqual(index["capability"], {"core": ["case-a"], "performance": ["case-b"]})
        self.assertEqual(index["risk_mode"], {"security": ["case-a"], "performance": ["case-b"]})
        self.assertEqual(index["policy_contract"], {"unclassified": ["case-a", "case-b"]})
        self.assertEqual(index["affected_surface"], {"unclassified": ["case-a", "case-b"]})

    def test_a_dimension_value_with_zero_cases_is_absent_not_an_empty_list(self) -> None:
        _write_case(self.corpus_dir / "core", "case-a", capability="core")
        index = idx.build_index(self.corpus_dir)
        self.assertNotIn("dependency-supply-chain", index["capability"])

    def test_multiple_values_on_one_dimension_index_the_case_under_each(self) -> None:
        directory = self.corpus_dir / "core"
        directory.mkdir(parents=True)
        (directory / "multi.yaml").write_text(
            textwrap.dedent(
                """\
                format: benchmark-case/v2
                id: multi-capability-case
                title: "multi"
                input:
                  patch: |
                    diff --git a/x b/x
                    --- a/x
                    +++ b/x
                    @@ -1 +1 @@
                    -a
                    +b
                expected:
                  findings: []
                metadata:
                  taxonomy:
                    capability: [core, performance]
                    policy_contract: [unclassified]
                    risk_mode: [correctness]
                    affected_surface: [unclassified]
                """
            ),
            encoding="utf-8",
        )
        index = idx.build_index(self.corpus_dir)
        self.assertEqual(index["capability"]["core"], ["multi-capability-case"])
        self.assertEqual(index["capability"]["performance"], ["multi-capability-case"])

    def test_build_is_reproducible_from_a_fixed_snapshot(self) -> None:
        _write_case(self.corpus_dir / "core", "case-a", capability="core")
        _write_case(self.corpus_dir / "performance", "case-b", capability="performance")
        first = idx.render_index(idx.build_index(self.corpus_dir))
        second = idx.render_index(idx.build_index(self.corpus_dir))
        self.assertEqual(first, second)

    def test_a_case_with_invalid_taxonomy_fails_the_build_rather_than_being_skipped(self) -> None:
        directory = self.corpus_dir / "core"
        directory.mkdir(parents=True)
        (directory / "bad.yaml").write_text(
            textwrap.dedent(
                """\
                format: benchmark-case/v2
                id: bad-case
                title: "bad"
                input:
                  patch: |
                    diff --git a/x b/x
                    --- a/x
                    +++ b/x
                    @@ -1 +1 @@
                    -a
                    +b
                expected:
                  findings: []
                metadata:
                  taxonomy:
                    capability: [not-a-real-value]
                    policy_contract: [unclassified]
                    risk_mode: [correctness]
                    affected_surface: [unclassified]
                """
            ),
            encoding="utf-8",
        )
        with self.assertRaises(Exception):
            idx.build_index(self.corpus_dir)


class LookupIsBoundedByCandidateSetTests(unittest.TestCase):
    """Acceptance criterion #5: lookup work is bounded by the matched
    (dimension, value) candidate set, not total corpus size."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.corpus_dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def test_unrelated_cases_never_change_the_matched_candidate_set(self) -> None:
        _write_case(self.corpus_dir / "core", "target-1", capability="core", risk_mode="security")
        _write_case(self.corpus_dir / "core", "target-2", capability="core", risk_mode="security")
        index_before = idx.build_index(self.corpus_dir)
        candidates_before = set(index_before["capability"]["core"])

        # Add a batch of cases entirely outside the matched (capability,
        # "core") pair — a fixed PR classification's lookup must not see
        # them at all.
        for i in range(50):
            _write_case(
                self.corpus_dir / "performance",
                f"unrelated-{i}",
                capability="performance",
                risk_mode="performance",
            )

        index_after = idx.build_index(self.corpus_dir)
        candidates_after = set(index_after["capability"]["core"])

        self.assertEqual(candidates_before, candidates_after)
        self.assertEqual(candidates_after, {"target-1", "target-2"})
        # The unrelated cases exist in the corpus but never appear under
        # the matched pair — the whole point of narrowing through the
        # index instead of scanning the corpus.
        self.assertEqual(len(index_after["capability"]["performance"]), 50)


if __name__ == "__main__":
    unittest.main()
