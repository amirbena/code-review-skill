#!/usr/bin/env python3
"""Structural contract checks for the benchmark duplicate-noise metric (#57).

Pins runtime_platform/benchmark/duplicate-noise.md so the canonical invariant, the
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

from tests.support.benchmark_doc_contract import (
    BenchmarkDocContractMixin,
    BenchmarkDocNavigationMixin,
    BenchmarkDocSpec,
    Section,
)
from tests.support.paths import REPO_ROOT

BENCH = REPO_ROOT / "runtime_platform" / "benchmark"
DOC = BENCH / "duplicate-noise.md"

SPEC = BenchmarkDocSpec(
    doc=DOC,
    issue_tokens=(
        "#57", "#56", "#55", "#54", "#53", "#52", "#50", "#51", "#41", "#40", "#42", "#59",
    ),
    invariant=(
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
        "judgement, and no score enters them."
    ),
    sections=(
        Section(
            "## 6. Determinism and two-reader consistency",
            raw=(
                "The edge test is the #54 matcher.",
                "Fixed clustering order.",
                "Integers and exact rationals only.",
            ),
            text=("two people applying §2–§4 to them must reach the same",),
        ),
        Section(
            "## 7. Worked examples",
            raw=("](../../tests/unit/benchmark/test_benchmark_dupes.py)",),
            text=("encoded verbatim as data-driven cases", "deliberate non-duplicates"),
        ),
        Section(
            "## 8. Explicitly out of scope",
            body=(
                "issues/54",
                "issues/55",
                "issues/56",
                "blended quality score",
                "de-duplication behaviour inside the reviewer",
                "P0/P1/P2 definitions",
            ),
        ),
    ),
    status_body=("becomes the design record", "MUST NOT keep evolving the accounting independently"),
    status_raw=(
        "](reference/benchmark_dupes.py)",
        "](../../tests/unit/benchmark/test_benchmark_dupes.py)",
    ),
    readme_link="](duplicate-noise.md)",
    readme_issue="#57",
    architecture_name="duplicate-noise.md",
    reference=BENCH / "reference" / "benchmark_dupes.py",
    unit_test=REPO_ROOT / "tests" / "unit" / "benchmark" / "test_benchmark_dupes.py",
    unit_import="from runtime_platform.benchmark.reference import benchmark_dupes as bdup",
    unit_phrase="never defines a second match relation or pairing",
)


class DuplicateNoiseContractTests(BenchmarkDocContractMixin, unittest.TestCase):
    spec = SPEC

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


class DirectoryNavigationTests(BenchmarkDocNavigationMixin, unittest.TestCase):
    spec = SPEC


if __name__ == "__main__":
    unittest.main()
