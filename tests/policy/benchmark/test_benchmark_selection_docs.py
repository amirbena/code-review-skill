#!/usr/bin/env python3
"""Structural contract checks for the Top-K benchmark selector (#334).

Pins docs/benchmark/selection.md so the canonical invariant, the Case
Relevance Score weights/bands, the Selection Coverage formula and golden
threshold, the `insufficient-coverage` outcome, the Top-K bound
constants, and the explainability field list cannot drift silently.
Prose assertions are whitespace-normalized; structural ones target
headings and literal terms.
"""

import unittest

from tests.support.paths import REPO_ROOT

DOC = REPO_ROOT / "docs" / "benchmark" / "selection.md"
README = REPO_ROOT / "docs" / "benchmark" / "README.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "benchmark" / "benchmark_selection.py"
UNIT_TEST = REPO_ROOT / "tests" / "unit" / "benchmark" / "test_benchmark_selection.py"
CLI_SCRIPT = REPO_ROOT / "scripts" / "benchmark" / "select_benchmark_cases.py"


class SelectionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = DOC.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_is_repository_development_only_not_packaged(self) -> None:
        self.assertIn("repository-development doc", self.text)
        self.assertIn("no packaged Skill resource depends on it", self.text)

    def test_names_issue_334_and_its_neighbours(self) -> None:
        for token in ("#334", "#333", "#330", "#331", "#335"):
            self.assertIn(token, self.raw)

    def test_canonical_invariant_is_stated(self) -> None:
        self.assertIn(
            "A selector that cannot explain, deterministically, why it "
            "picked what it picked is not trustworthy enough to inform a "
            "merge decision",
            self.text,
        )

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

    def test_status_defers_to_an_eventual_canonical_home(self) -> None:
        tail = " ".join(self.raw.split("## 6. Status and canonical home", 1)[1].split())
        self.assertIn("informational-only", tail)
        self.assertIn("never become a required contributor/merge check", tail)
        self.assertIn(
            "](../../tests/reference/benchmark/benchmark_selection.py)", self.raw
        )


class DirectoryNavigationTests(unittest.TestCase):
    def test_readme_maps_the_selection_contract(self) -> None:
        raw = README.read_text(encoding="utf-8")
        self.assertIn("](selection.md)", raw)
        self.assertIn("#334", raw)

    def test_reference_module_is_declared_test_only(self) -> None:
        head = " ".join(REFERENCE.read_text(encoding="utf-8")[:800].split())
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_unit_test_consumes_the_single_reference_selector(self) -> None:
        raw = UNIT_TEST.read_text(encoding="utf-8")
        self.assertIn("from tests.reference.benchmark import benchmark_selection as sel", raw)

    def test_cli_script_reimplements_no_scoring_logic(self) -> None:
        raw = CLI_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("from tests.reference.benchmark import benchmark_selection as sel", raw)
        self.assertIn("Reimplements no scoring", raw)


if __name__ == "__main__":
    unittest.main()
