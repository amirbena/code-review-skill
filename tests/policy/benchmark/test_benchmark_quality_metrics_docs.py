#!/usr/bin/env python3
"""Structural contract checks for the benchmark missed/incorrect metrics (#55).

Pins runtime_platform/benchmark/missed-and-incorrect-findings.md so the canonical
invariant, the produced↔expected pairing rule, the false-negative and
false-positive accounting, the `match` / `any_of` / `findings_completeness`
interactions, the anti-double-count near-miss rule, the aggregate shape,
the "renders alongside the regression-report deltas, never gates it"
boundary, the determinism rules, the worked-example conformance bar, and
the deferred-scope boundaries cannot drift silently. Prose assertions are
whitespace-normalized; structural ones target headings and literal terms.
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
DOC = BENCH / "missed-and-incorrect-findings.md"

SPEC = BenchmarkDocSpec(
    doc=DOC,
    issue_tokens=("#55", "#54", "#53", "#52", "#50", "#51", "#56", "#57", "#41", "#42"),
    invariant=(
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
        "judgement, or duplicate-clustering enters them."
    ),
    sections=(
        Section(
            "## 7. Determinism and two-reader consistency",
            raw=("Fixed computation order.", "Only `MATCH` counts.", "No scores."),
            text=("two people applying §2–§5 to them must reach the same",),
        ),
        Section(
            "## 8. Worked examples",
            raw=("](../../tests/unit/benchmark/test_benchmark_metrics.py)",),
            text=("encoded verbatim as data-driven cases", "anti-double-count rule"),
        ),
        Section(
            "## 9. Explicitly out of scope",
            body=(
                "issues/56",
                "issues/57",
                "blended quality score",
                "cross-revision stable finding identity",
            ),
        ),
    ),
    status_body=("becomes the design record", "MUST NOT keep evolving the accounting independently"),
    status_raw=(
        "](reference/benchmark_metrics.py)",
        "](../../tests/unit/benchmark/test_benchmark_metrics.py)",
    ),
    readme_link="](missed-and-incorrect-findings.md)",
    readme_issue="#55",
    architecture_name="missed-and-incorrect-findings.md",
    reference=BENCH / "reference" / "benchmark_metrics.py",
    unit_test=REPO_ROOT / "tests" / "unit" / "benchmark" / "test_benchmark_metrics.py",
    unit_import="from runtime_platform.benchmark.reference import benchmark_metrics as bmet",
    unit_phrase="never defines a second match relation",
)


class QualityMetricsContractTests(BenchmarkDocContractMixin, unittest.TestCase):
    spec = SPEC

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


class DirectoryNavigationTests(BenchmarkDocNavigationMixin, unittest.TestCase):
    spec = SPEC


if __name__ == "__main__":
    unittest.main()
