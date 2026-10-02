#!/usr/bin/env python3
"""Structural contract checks for the Top-K benchmark selector (#334).

Pins runtime_platform/benchmark/selection.md so the canonical invariant, the Case
Relevance Score weights/bands, the Selection Coverage formula and golden
threshold, the `insufficient-coverage` outcome, the Top-K bound
constants, and the explainability field list cannot drift silently.
Prose assertions are whitespace-normalized; structural ones target
headings and literal terms.
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
DOC = BENCH / "selection.md"
CLI_SCRIPT = BENCH / "scripts" / "select_benchmark_cases.py"

SPEC = BenchmarkDocSpec(
    doc=DOC,
    issue_tokens=("#334", "#333", "#330", "#331", "#335"),
    invariant=(
        "A selector that cannot explain, deterministically, why it "
        "picked what it picked is not trustworthy enough to inform a "
        "merge decision"
    ),
    not_packaged="repository-development doc",
    status_heading="## 6. Status and canonical home",
    status_body=(
        "informational-only",
        "never become a required contributor/merge check",
    ),
    status_raw=("](reference/benchmark_selection.py)",),
    readme_link="](selection.md)",
    readme_issue="#334",
    reference=BENCH / "reference" / "benchmark_selection.py",
    reference_head_chars=800,
    unit_test=REPO_ROOT / "tests" / "unit" / "benchmark" / "test_benchmark_selection.py",
    unit_import="from runtime_platform.benchmark.reference import benchmark_selection as sel",
)


class SelectionContractTests(BenchmarkDocContractMixin, unittest.TestCase):
    spec = SPEC

    def test_case_relevance_weights_are_documented(self) -> None:
        self.assertIn("## 2. Case Relevance Score", self.raw)
        self.assertIn("| `capability` | 40 |", self.raw)
        self.assertIn("| `policy_contract` | 25 |", self.raw)
        self.assertIn("| `risk_mode` | 20 |", self.raw)
        self.assertIn("| `affected_surface` | 15 |", self.raw)

    def test_relevance_bands_are_documented(self) -> None:
        self.assertIn("`primary`", self.raw)
        self.assertIn(">= 60", self.text)
        self.assertIn("`secondary`", self.raw)
        self.assertIn("40–59", self.text)
        self.assertIn("`not-eligible`", self.raw)
        self.assertIn("< 40", self.text)

    def test_selection_coverage_is_a_distinct_concept(self) -> None:
        self.assertIn("## 3. Selection Coverage Score", self.raw)
        self.assertIn("A **distinct concept** from Case Relevance", self.text)
        self.assertIn(
            "Selection Coverage = (sum of covered pairs' weight) / 100", self.text
        )

    def test_golden_threshold_and_insufficient_coverage_outcome(self) -> None:
        self.assertIn("Golden threshold: Selection Coverage >= 60%", self.text)
        self.assertIn("`insufficient-coverage`", self.raw)
        self.assertIn("never** folded into a passing result", self.text)
        self.assertIn("ships informational-only", self.text)

    def test_top_k_bound_constants_are_documented(self) -> None:
        self.assertIn("## 4. Top-K selection algorithm", self.raw)
        self.assertIn("K_DEFAULT = 6", self.raw)
        self.assertIn("K_MAX = 12", self.raw)

    def test_greedy_stopping_rules_are_explicit(self) -> None:
        self.assertIn("largest marginal", self.text)
        self.assertIn("Ties are broken by higher Case Relevance Score", self.text)
        self.assertIn("lexicographically first case id", self.text)

    def test_explainability_fields_are_documented(self) -> None:
        self.assertIn("## 5. Explainability", self.raw)
        for field in (
            "`resolved_taxonomy_classification`",
            "`candidate_pool_size`",
            "`selected_cases`",
            "`selection_coverage`",
            "`coverage_threshold`",
            "`top_k_bound`",
            "`uncovered_pairs`",
            "`outcome`",
        ):
            self.assertIn(field, self.raw)
        self.assertIn("GitHub Actions step summary", self.text)
        self.assertIn("--step-summary", self.raw)

    def test_non_goals_defer_taxonomy_runtime_and_gating(self) -> None:
        self.assertIn("## 1. Scope", self.raw)
        boundary = " ".join(self.raw.split("does **not** own", 1)[1].split())
        self.assertIn("#333", boundary)
        self.assertIn("#330", boundary)
        self.assertIn("issues/335", boundary)
        self.assertIn("informational-only", boundary)


class DirectoryNavigationTests(BenchmarkDocNavigationMixin, unittest.TestCase):
    spec = SPEC

    test_architecture_mentions_the_contract = None

    def test_cli_script_reimplements_no_scoring_logic(self) -> None:
        raw = CLI_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("from runtime_platform.benchmark.reference import benchmark_selection as sel", raw)
        self.assertIn("Reimplements no scoring", raw)


if __name__ == "__main__":
    unittest.main()
