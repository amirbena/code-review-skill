#!/usr/bin/env python3
"""Structural contract checks for the benchmark severity-accuracy metric (#56).

Pins runtime_platform/benchmark/severity-accuracy.md so the canonical invariant, the
"matched set is the #55 pairing taken verbatim" rule, the exact /
over-severity / under-severity classification and its partition, the
`severity` list and `any_of` member resolution, the aggregate shape with a
single exact-rational rate, the "renders alongside the regression-report
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
DOC = BENCH / "severity-accuracy.md"

SPEC = BenchmarkDocSpec(
    doc=DOC,
    issue_tokens=("#56", "#55", "#54", "#53", "#52", "#50", "#51", "#57", "#41", "#40"),
    invariant=(
        "A benchmark run's severity accuracy is three counts per case "
        "over the matched set — how many matched findings carry a "
        "permitted expected severity (exact), how many the reviewer "
        "rated more severe than expected (over-severity), and how many "
        "less severe (under-severity) — computed by taking the #55 "
        "produced↔expected pairing unchanged, then, for each pair, "
        "comparing the produced severity against the permitted expected "
        "severities for the entry that pair satisfied. The comparison "
        "uses only the P0/P1/P2 ordinal and the fixture's `severity` "
        "field; a `NEAR_MISS`, an unpaired entry, or an unpaired "
        "produced finding never enters it, and no rule here changes "
        "which findings are paired."
    ),
    sections=(
        Section(
            "## 6. Determinism and two-reader consistency",
            raw=(
                "The pairing is an input, not a step.",
                "Fixed classification order.",
                "Integers and exact rationals only.",
            ),
            text=("two people applying §2–§4 to them must reach the same",),
        ),
        Section(
            "## 7. Worked examples",
            raw=("](../../tests/unit/benchmark/test_benchmark_severity.py)",),
            text=("encoded verbatim as data-driven cases", "deliberate severity mismatches"),
        ),
        Section(
            "## 8. Explicitly out of scope",
            body=("issues/55", "issues/57", "blended quality score", "P0/P1/P2 definitions"),
        ),
    ),
    status_body=("becomes the design record", "MUST NOT keep evolving the accounting independently"),
    status_raw=(
        "](reference/benchmark_severity.py)",
        "](../../tests/unit/benchmark/test_benchmark_severity.py)",
    ),
    readme_link="](severity-accuracy.md)",
    readme_issue="#56",
    architecture_name="severity-accuracy.md",
    reference=BENCH / "reference" / "benchmark_severity.py",
    unit_test=REPO_ROOT / "tests" / "unit" / "benchmark" / "test_benchmark_severity.py",
    unit_import="from runtime_platform.benchmark.reference import benchmark_severity as bsev",
    unit_phrase="never defines a second pairing or match relation",
)


class SeverityAccuracyContractTests(BenchmarkDocContractMixin, unittest.TestCase):
    spec = SPEC

    def test_matched_set_is_the_55_pairing_verbatim(self) -> None:
        self.assertIn("## 2. The matched set", self.raw)
        self.assertIn("consumes that map; it never re-runs the greedy pass", self.text)
        self.assertIn("A **`NEAR_MISS`** never pairs", self.text)
        self.assertIn("`required` and `optional` entries that got paired both take part", self.text)

    def test_classification_rules_and_partition(self) -> None:
        self.assertIn("## 3. Classifying a matched pair", self.raw)
        self.assertIn("`p ∈ E` → exact", self.text)
        self.assertIn("more severe than `max(E)` → over-severity", self.text)
        self.assertIn("Otherwise → under-severity", self.text)
        self.assertIn(
            "`exact + over_severity + under_severity == matched` for every case",
            self.text,
        )

    def test_any_of_member_is_the_reference(self) -> None:
        self.assertIn("the achieving **member**", self.text)
        self.assertIn("the member's `severity` is used, not the group's", self.text)

    def test_output_shape_and_single_rational_rate(self) -> None:
        self.assertIn("## 4. Per-case and aggregate output", self.raw)
        for field in (
            "`matched`",
            "`severity_exact`",
            "`over_severity`",
            "`under_severity`",
            "`exact_rate`",
            "`total_matched`",
            "`cases_with_severity_mismatch`",
        ):
            self.assertIn(field, self.raw)
        self.assertIn("The only ratio here is `exact_rate`", self.text)
        self.assertIn("no precision, no recall, and no single blended score", self.text)
        self.assertIn("`null` when `matched` is `0` (an undefined rate is not `0`)", self.text)

    def test_renders_alongside_report_without_gating_it(self) -> None:
        self.assertIn("## 5. Rendering alongside the regression report", self.raw)
        self.assertIn("`severity_accuracy`", self.raw)
        self.assertIn("alongside the per-case deltas", self.text)
        self.assertIn("**never changes** `has_regressions`", self.text)
        self.assertIn("`corpus_id` guard still applies", self.text)
        self.assertIn("added_case_ids` / `removed_case_ids", self.text)


class DirectoryNavigationTests(BenchmarkDocNavigationMixin, unittest.TestCase):
    spec = SPEC


if __name__ == "__main__":
    unittest.main()
