#!/usr/bin/env python3
"""Structural contract checks for the benchmark missed/incorrect metrics (#55).

Pins docs/benchmark/missed-and-incorrect-findings.md so the canonical
invariant, the produced↔expected pairing rule, the false-negative and
false-positive accounting, the `match` / `any_of` / `findings_completeness`
interactions, the anti-double-count near-miss rule, the aggregate shape,
the "renders alongside the regression-report deltas, never gates it"
boundary, the determinism rules, the worked-example conformance bar, and
the deferred-scope boundaries cannot drift silently. Prose assertions are
whitespace-normalized; structural ones target headings and literal terms.
"""

import unittest

from tests.support.paths import REPO_ROOT

DOC = REPO_ROOT / "docs" / "benchmark" / "missed-and-incorrect-findings.md"
README = REPO_ROOT / "docs" / "benchmark" / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "benchmark" / "benchmark_metrics.py"
UNIT_TEST = REPO_ROOT / "tests" / "unit" / "benchmark" / "test_benchmark_metrics.py"


class QualityMetricsContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = DOC.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_is_repository_development_only_not_packaged(self) -> None:
        self.assertIn("repository-development doc: not packaged", self.text)
        self.assertIn("no packaged Skill resource depends on it", self.text)

    def test_names_issue_55_and_its_neighbours(self) -> None:
        for token in ("#55", "#54", "#53", "#52", "#50", "#51", "#56", "#57", "#41", "#42"):
            self.assertIn(token, self.raw)

    def test_canonical_invariant_is_stated_verbatim(self) -> None:
        self.assertIn(
            "A benchmark run's quality, on this axis, is two counts per case "
            "— how many expected findings the reviewer missed (false "
            "negatives) and how many findings it produced that correspond to "
            "no expected finding (false positives) — computed by first "
            "resolving a one-to-one pairing between produced findings and "
            "expected entries using only the #54 `MATCH` relation, then "
            "counting what is left unpaired on each side, gated by the "
            "fixture's `match` flags and `findings_completeness`. The counts "
            "derive entirely from the documented match criteria and the "
            "fixture's structured fields; no score, ratio, severity "
            "judgement, or duplicate-clustering enters them.",
            self.text,
        )

    def test_pairing_is_greedy_document_order_and_one_to_one(self) -> None:
        self.assertIn("## 2. The produced↔expected pairing", self.raw)
        self.assertIn("at most one", self.text)
        self.assertIn("deterministic greedy pass in fixture document order", self.text)
        self.assertIn("the earlier entry wins it and the later entry is a miss", self.text)
        self.assertIn("Only `MATCH` pairs", self.text)

    def test_any_of_group_is_one_entry_with_absorbed_extra(self) -> None:
        self.assertIn("### 2.1 `any_of` groups in the pairing", self.raw)
        self.assertIn("satisfied by **exactly one** member `MATCH`", self.text)
        self.assertIn("is **absorbed**", self.text)
        self.assertIn("`absorbed_extra_match`", self.raw)

    def test_false_negative_rules(self) -> None:
        self.assertIn("## 3. False negatives (missed findings)", self.raw)
        self.assertIn("`required` entry, unpaired → one false negative", self.text)
        self.assertIn("`optional` entry, unpaired → not a false negative", self.text)
        self.assertIn("the whole group is one missed finding, not one per member", self.text)

    def test_false_positive_rules_and_completeness_gate(self) -> None:
        self.assertIn("## 4. False positives (incorrect findings)", self.raw)
        self.assertIn("every acceptable spec in the fixture's union", self.text)
        self.assertIn("false positive only when `findings_completeness` is `exhaustive`", self.text)
        self.assertIn("`0` when it is `at-least`", self.text)
        self.assertIn("would double-penalize one imperfect report", self.text)

    def test_errored_case_accounting(self) -> None:
        self.assertIn(
            "its false-positive count is `0` and its false-negative count is "
            "the number of `required` entries",
            self.text,
        )
        self.assertIn("flagged `errored`", self.text)

    def test_aggregate_is_sums_only_no_rate(self) -> None:
        self.assertIn("## 5. Per-case and aggregate output", self.raw)
        for field in (
            "`false_negatives`",
            "`false_positives`",
            "`near_misses`",
            "`total_false_negatives`",
            "`total_false_positives`",
            "`cases_with_false_negatives`",
        ):
            self.assertIn(field, self.raw)
        self.assertIn("no precision, no recall, no pass percentage, no single number", self.text)

    def test_renders_alongside_report_without_gating_it(self) -> None:
        self.assertIn("## 6. Rendering alongside the regression report", self.raw)
        self.assertIn("`quality_metrics`", self.raw)
        self.assertIn("alongside the per-case deltas", self.text)
        self.assertIn("**never changes** `has_regressions`", self.text)
        self.assertIn("`corpus_id` guard still applies", self.text)

    def test_determinism_rules_are_explicit(self) -> None:
        self.assertIn("## 7. Determinism and two-reader consistency", self.raw)
        self.assertIn("Fixed computation order.", self.raw)
        self.assertIn("Only `MATCH` counts.", self.raw)
        self.assertIn("No scores.", self.raw)
        self.assertIn("two people applying §2–§5 to them must reach the same", self.text)

    def test_worked_examples_are_the_conformance_bar(self) -> None:
        self.assertIn("## 8. Worked examples", self.raw)
        self.assertIn("encoded verbatim as data-driven cases", self.text)
        self.assertIn("](../../tests/unit/benchmark/test_benchmark_metrics.py)", self.raw)
        self.assertIn("anti-double-count rule", self.text)

    def test_scope_boundaries_defer_neighbours(self) -> None:
        self.assertIn("## 9. Explicitly out of scope", self.raw)
        boundary = " ".join(self.raw.split("## 9. Explicitly out of scope", 1)[1].split())
        self.assertIn("issues/56", boundary)
        self.assertIn("issues/57", boundary)
        self.assertIn("blended quality score", boundary)
        self.assertIn("cross-revision stable finding identity", boundary)

    def test_status_defers_to_an_eventual_canonical_home(self) -> None:
        tail = " ".join(self.raw.split("## Status and canonical home", 1)[1].split())
        self.assertIn("becomes the design record", tail)
        self.assertIn("MUST NOT keep evolving the accounting independently", tail)
        self.assertIn("](../../tests/reference/benchmark/benchmark_metrics.py)", self.raw)
        self.assertIn("](../../tests/unit/benchmark/test_benchmark_metrics.py)", self.raw)


class DirectoryNavigationTests(unittest.TestCase):
    def test_readme_maps_the_quality_metrics(self) -> None:
        raw = README.read_text(encoding="utf-8")
        self.assertIn("](missed-and-incorrect-findings.md)", raw)
        self.assertIn("#55", raw)

    def test_architecture_mentions_the_quality_metrics(self) -> None:
        text = " ".join(ARCHITECTURE.read_text(encoding="utf-8").split())
        self.assertIn("missed-and-incorrect-findings.md", text)
        self.assertIn("nothing benchmark", text)

    def test_reference_module_is_declared_test_only(self) -> None:
        head = REFERENCE.read_text(encoding="utf-8")[:700]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_unit_test_consumes_the_single_reference_matcher(self) -> None:
        raw = " ".join(UNIT_TEST.read_text(encoding="utf-8").split())
        self.assertIn("from tests.reference.benchmark import benchmark_metrics as bmet", raw)
        self.assertIn("never defines a second match relation", raw)


if __name__ == "__main__":
    unittest.main()
