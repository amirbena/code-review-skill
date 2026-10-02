#!/usr/bin/env python3
"""Structural contract checks for the benchmark regression report (#53).

Pins runtime_platform/benchmark/regression-report.md so the canonical invariant, the
baseline result artifact, the identity guard, the per-case / aggregate
delta model, the regression-vs-improvement separation, deterministic
output, the deliberate baseline-refresh rule, the report-health-vs-
regression-signal split, and the deferred-scope boundaries cannot drift
silently. Prose assertions are whitespace-normalized; structural ones
target headings and literal terms.
"""

import unittest

from tests.support.benchmark_doc_contract import (
    README,
    BenchmarkDocContractMixin,
    BenchmarkDocNavigationMixin,
    BenchmarkDocSpec,
    Section,
)
from tests.support.paths import REPO_ROOT

BENCH = REPO_ROOT / "runtime_platform" / "benchmark"
DOC = BENCH / "regression-report.md"

SPEC = BenchmarkDocSpec(
    doc=DOC,
    issue_tokens=("#53", "#52", "#51", "#50", "#41", "#40"),
    invariant=(
        "A regression report joins a candidate run to a stored baseline "
        "run by case `id`, reports every per-case and aggregate delta "
        "between them, and calls out cases that got worse distinctly from "
        "cases that got better — without deciding whether a produced "
        "finding is *correct*, which is a quality metric (#41), and "
        "without ever writing the baseline itself."
    ),
    sections=(
        Section(
            "## 10. Explicitly out of scope",
            body=(
                "match relation",
                "issues/41",
                "Automatic baseline promotion",
                "per-case result shape this report consumes",
            ),
        ),
    ),
    status_body=("becomes the design record", "MUST NOT keep evolving the reporting behavior independently"),
    status_raw=(
        "](reference/benchmark_report.py)",
        "](../../tests/unit/benchmark/test_benchmark_report.py)",
    ),
    readme_link="](regression-report.md)",
    readme_issue="#53",
    architecture_name="regression-report.md",
    reference=BENCH / "reference" / "benchmark_report.py",
    reference_head_chars=600,
    unit_test=REPO_ROOT / "tests" / "unit" / "benchmark" / "test_benchmark_report.py",
    unit_import="from runtime_platform.benchmark.reference import benchmark_report as brp",
    unit_phrase="never defines a second one",
)


class RegressionReportContractTests(BenchmarkDocContractMixin, unittest.TestCase):
    spec = SPEC

    def test_report_is_external_infra_never_launched_by_a_skill(self) -> None:
        self.assertIn("is **not** a Skill and is never packaged; no Skill launches it", self.text)
        self.assertIn("downstream evaluation infrastructure", self.text)

    def test_baseline_artifact_shape_is_defined(self) -> None:
        self.assertIn("## 2. The baseline result artifact", self.raw)
        for field in ("`results`", "`corpus_id`", "`adapter_id`", "`created_at`"):
            self.assertIn(field, self.raw)
        self.assertIn("It is produced by promoting a prior", self.text)
        self.assertIn("the report never creates or edits it", self.text)

    def test_identity_guard_fails_closed_on_a_corpus_mismatch(self) -> None:
        self.assertIn("## 3. Inputs and the identity guard", self.raw)
        self.assertIn("Corpus identity must match.", self.raw)
        self.assertIn("is not a regression signal", self.text)
        self.assertIn("Adapter identity is recorded, not gated.", self.raw)
        self.assertIn("joined by `id`", self.text)

    def test_per_case_comparison_reads_recorded_output_only(self) -> None:
        self.assertIn("## 4. Per-case comparison", self.raw)
        self.assertIn("never recomputed by re-running the reviewer", self.text)
        for token in ("**dropped**", "**gained**", "**retained**"):
            self.assertIn(token, self.raw)
        self.assertIn("cross-run stability key", self.text)
        self.assertIn("identity-bearing** location fields only", self.text)
        self.assertIn("Positional fields (`line`/`col` and friends) are deliberately **excluded**", self.text)
        self.assertIn("Severity is likewise **not** part of the key", self.text)
        self.assertIn("is **not** the #41 expected-vs-produced match relation", self.text)

    def test_regression_and_improvement_are_distinct_classes(self) -> None:
        self.assertIn("## 5. Regression vs improvement", self.raw)
        self.assertIn("visibly distinct groups", self.text)
        for cls in ("**regression**", "**improvement**", "**mixed**", "**unchanged**"):
            self.assertIn(cls, self.raw)
        self.assertIn("Grouped **with the regressions** — fail closed", self.text)
        self.assertIn("intentionally metric-free", self.text)

    def test_aggregate_report_has_a_single_has_regressions_flag(self) -> None:
        self.assertIn("## 6. Aggregate report", self.raw)
        self.assertIn("**`has_regressions`**", self.raw)
        self.assertIn("a single boolean: true iff", self.text)
        self.assertIn("the flag a CI gate acts on", self.text)
        self.assertIn("No aggregate here is a \"score\"", self.raw)

    def test_output_is_deterministic_and_stable(self) -> None:
        self.assertIn("## 7. Deterministic, stable output", self.raw)
        self.assertIn("Byte-identical for identical inputs.", self.raw)
        self.assertIn("Deterministic ordering.", self.raw)
        self.assertIn("No run-specific noise in the diff body.", self.raw)
        self.assertIn("Empty is a valid, stable report.", self.raw)

    def test_baseline_refresh_is_deliberate_and_never_automatic(self) -> None:
        self.assertIn("## 8. Baseline refresh is a deliberate, documented step", self.raw)
        self.assertIn("The report **never** writes, promotes, or mutates the baseline", self.text)
        self.assertIn("Refreshing the baseline is an explicit human action", self.text)
        self.assertIn("There is no automatic promotion", self.text)
        self.assertIn("explicitly out of scope for #53", self.text)

    def test_report_health_is_separate_from_the_regression_signal(self) -> None:
        self.assertIn("## 9. Report status vs regression signal", self.raw)
        self.assertIn("Process health is separate from findings.", self.raw)
        self.assertIn("Finding regressions is not a report failure.", self.raw)
        self.assertIn("mirrors [`runner-contract.md`](runner-contract.md) §7", self.raw)

    def test_not_a_scorer_section_keeps_the_run_to_run_diff_independent_of_41(self) -> None:
        self.assertIn("## 11. On not being a scorer", self.raw)
        self.assertIn("needs **only** what the runner already recorded", self.text)
        self.assertIn("never the fixtures' `expected` blocks", self.text)
        self.assertIn("before the quality-metric layer (#41) exists", self.text)
        self.assertIn("does not have to change when #41 lands", self.text)


class DirectoryNavigationTests(BenchmarkDocNavigationMixin, unittest.TestCase):
    spec = SPEC

    def test_readme_drops_the_not_yet_written_placeholder(self) -> None:
        raw = README.read_text(encoding="utf-8")
        self.assertNotIn("Not yet written (tracked on #40): regression reporting", raw)


if __name__ == "__main__":
    unittest.main()
