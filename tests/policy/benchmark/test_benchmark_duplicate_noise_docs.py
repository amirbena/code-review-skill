#!/usr/bin/env python3
"""Structural contract checks for the benchmark duplicate-noise metric (#57).

Pins docs/benchmark/duplicate-noise.md so the canonical invariant, the
"same-root-cause edge is the #54 MATCH cell, unchanged" rule, the
connected-component clustering and its transitivity, the redundant-finding
accounting, the aggregate shape with a single exact-rational rate, the
highest-noise-cases list, the "renders alongside the regression-report
deltas, never gates it" boundary, the determinism rules, the worked-example
conformance bar, and the deferred-scope boundaries cannot drift silently.
Prose assertions are whitespace-normalized; structural ones target headings
and literal terms.
"""

import unittest

from tests.support.paths import REPO_ROOT

DOC = REPO_ROOT / "docs" / "benchmark" / "duplicate-noise.md"
README = REPO_ROOT / "docs" / "benchmark" / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "benchmark" / "benchmark_dupes.py"
UNIT_TEST = REPO_ROOT / "tests" / "unit" / "benchmark" / "test_benchmark_dupes.py"


class DuplicateNoiseContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = DOC.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_is_repository_development_only_not_packaged(self) -> None:
        self.assertIn("repository-development doc: not packaged", self.text)
        self.assertIn("no packaged Skill resource depends on it", self.text)

    def test_names_issue_57_and_its_neighbours(self) -> None:
        for token in ("#57", "#56", "#55", "#54", "#53", "#52", "#50", "#51", "#41", "#40", "#42", "#59"):
            self.assertIn(token, self.raw)

    def test_canonical_invariant_is_stated_verbatim(self) -> None:
        self.assertIn(
            "A benchmark run's duplicate noise is two counts per case over "
            "the produced findings alone — how many same-root-cause clusters "
            "the produced findings form, and how many findings are therefore "
            "redundant (every finding in a cluster past its first) — computed "
            "by taking each unordered pair of produced findings, calling it a "
            "same-root-cause edge exactly when the #54 relation is `MATCH` "
            "(location EXACT and defect CORRESPONDS) in either direction, and "
            "grouping the findings into connected components over those edges. "
            "The counts use only the #54 criteria and the produced findings' "
            "own fields; no expected finding, no #55 pairing, no severity "
            "judgement, and no score enters them.",
            self.text,
        )

    def test_edge_is_the_54_match_cell_unchanged(self) -> None:
        self.assertIn("## 2. The same-root-cause edge", self.raw)
        self.assertIn("the #54 matcher, unchanged", self.text)
        self.assertIn("No new axis, no new tolerance.", self.raw)
        self.assertIn("`MATCH` only.", self.raw)
        self.assertIn("A `NEAR_MISS` pair is never an edge", self.text)

    def test_clustering_is_connected_components_and_transitive(self) -> None:
        self.assertIn("## 3. Clustering the produced findings", self.raw)
        self.assertIn("connected components", self.text)
        self.assertIn("deterministic union-find", self.text)
        self.assertIn("transitive by construction", self.text)

    def test_output_shape_and_single_rational_rate(self) -> None:
        self.assertIn("## 4. Per-case and aggregate output", self.raw)
        for field in (
            "`produced`",
            "`clusters`",
            "`duplicate_clusters`",
            "`redundant_findings`",
            "`duplicate_rate`",
            "`total_produced`",
            "`total_redundant_findings`",
            "`cases_with_duplication`",
        ):
            self.assertIn(field, self.raw)
        self.assertIn("The only ratio here is `duplicate_rate`", self.text)
        self.assertIn("no precision, no recall, and no single blended score", self.text)
        self.assertIn("`null` when `produced` is `0` (an undefined rate is not `0`)", self.text)

    def test_renders_alongside_report_without_gating_it(self) -> None:
        self.assertIn("## 5. Rendering alongside the regression report", self.raw)
        self.assertIn("`duplicate_noise`", self.raw)
        self.assertIn("`highest_noise_cases`", self.raw)
        self.assertIn("report lists highest-noise cases", self.text)
        self.assertIn("alongside the per-case deltas", self.text)
        self.assertIn("**never changes** `has_regressions`", self.text)
        self.assertIn("`corpus_id` guard still applies", self.text)
        self.assertIn("added_case_ids` / `removed_case_ids", self.text)

    def test_determinism_rules_are_explicit(self) -> None:
        self.assertIn("## 6. Determinism and two-reader consistency", self.raw)
        self.assertIn("The edge test is the #54 matcher.", self.raw)
        self.assertIn("Fixed clustering order.", self.raw)
        self.assertIn("Integers and exact rationals only.", self.raw)
        self.assertIn("two people applying §2–§4 to them must reach the same", self.text)

    def test_worked_examples_are_the_conformance_bar(self) -> None:
        self.assertIn("## 7. Worked examples", self.raw)
        self.assertIn("encoded verbatim as data-driven cases", self.text)
        self.assertIn("](../../tests/unit/benchmark/test_benchmark_dupes.py)", self.raw)
        self.assertIn("deliberate non-duplicates", self.text)

    def test_scope_boundaries_defer_neighbours(self) -> None:
        self.assertIn("## 8. Explicitly out of scope", self.raw)
        boundary = " ".join(self.raw.split("## 8. Explicitly out of scope", 1)[1].split())
        self.assertIn("issues/54", boundary)
        self.assertIn("issues/55", boundary)
        self.assertIn("issues/56", boundary)
        self.assertIn("blended quality score", boundary)
        self.assertIn("de-duplication behaviour inside the reviewer", boundary)
        self.assertIn("P0/P1/P2 definitions", boundary)

    def test_status_defers_to_an_eventual_canonical_home(self) -> None:
        tail = " ".join(self.raw.split("## Status and canonical home", 1)[1].split())
        self.assertIn("becomes the design record", tail)
        self.assertIn("MUST NOT keep evolving the accounting independently", tail)
        self.assertIn("](../../tests/reference/benchmark/benchmark_dupes.py)", self.raw)
        self.assertIn("](../../tests/unit/benchmark/test_benchmark_dupes.py)", self.raw)


class DirectoryNavigationTests(unittest.TestCase):
    def test_readme_maps_the_duplicate_noise_metric(self) -> None:
        raw = README.read_text(encoding="utf-8")
        self.assertIn("](duplicate-noise.md)", raw)
        self.assertIn("#57", raw)

    def test_architecture_mentions_the_duplicate_noise_metric(self) -> None:
        text = " ".join(ARCHITECTURE.read_text(encoding="utf-8").split())
        self.assertIn("duplicate-noise.md", text)
        self.assertIn("nothing benchmark", text)

    def test_reference_module_is_declared_test_only(self) -> None:
        head = REFERENCE.read_text(encoding="utf-8")[:700]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_unit_test_consumes_the_single_reference_matcher(self) -> None:
        raw = " ".join(UNIT_TEST.read_text(encoding="utf-8").split())
        self.assertIn("from tests.reference.benchmark import benchmark_dupes as bdup", raw)
        self.assertIn("never defines a second match relation or pairing", raw)


if __name__ == "__main__":
    unittest.main()
