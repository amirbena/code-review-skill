#!/usr/bin/env python3
"""Structural contract checks for the benchmark severity-accuracy metric (#56).

Pins docs/benchmark/severity-accuracy.md so the canonical invariant, the
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

from tests.support.paths import REPO_ROOT

DOC = REPO_ROOT / "docs" / "benchmark" / "severity-accuracy.md"
README = REPO_ROOT / "docs" / "benchmark" / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "benchmark_severity.py"
UNIT_TEST = REPO_ROOT / "tests" / "unit" / "test_benchmark_severity.py"


class SeverityAccuracyContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = DOC.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_is_repository_development_only_not_packaged(self) -> None:
        self.assertIn("repository-development doc: not packaged", self.text)
        self.assertIn("no packaged Skill resource depends on it", self.text)

    def test_names_issue_56_and_its_neighbours(self) -> None:
        for token in ("#56", "#55", "#54", "#53", "#52", "#50", "#51", "#57", "#41", "#40"):
            self.assertIn(token, self.raw)

    def test_canonical_invariant_is_stated_verbatim(self) -> None:
        self.assertIn(
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
            "which findings are paired.",
            self.text,
        )

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

    def test_determinism_rules_are_explicit(self) -> None:
        self.assertIn("## 6. Determinism and two-reader consistency", self.raw)
        self.assertIn("The pairing is an input, not a step.", self.raw)
        self.assertIn("Fixed classification order.", self.raw)
        self.assertIn("Integers and exact rationals only.", self.raw)
        self.assertIn("two people applying §2–§4 to them must reach the same", self.text)

    def test_worked_examples_are_the_conformance_bar(self) -> None:
        self.assertIn("## 7. Worked examples", self.raw)
        self.assertIn("encoded verbatim as data-driven cases", self.text)
        self.assertIn("](../../tests/unit/test_benchmark_severity.py)", self.raw)
        self.assertIn("deliberate severity mismatches", self.text)

    def test_scope_boundaries_defer_neighbours(self) -> None:
        self.assertIn("## 8. Explicitly out of scope", self.raw)
        boundary = " ".join(self.raw.split("## 8. Explicitly out of scope", 1)[1].split())
        self.assertIn("issues/55", boundary)
        self.assertIn("issues/57", boundary)
        self.assertIn("blended quality score", boundary)
        self.assertIn("P0/P1/P2 definitions", boundary)

    def test_status_defers_to_an_eventual_canonical_home(self) -> None:
        tail = " ".join(self.raw.split("## Status and canonical home", 1)[1].split())
        self.assertIn("becomes the design record", tail)
        self.assertIn("MUST NOT keep evolving the accounting independently", tail)
        self.assertIn("](../../tests/reference/benchmark_severity.py)", self.raw)
        self.assertIn("](../../tests/unit/test_benchmark_severity.py)", self.raw)


class DirectoryNavigationTests(unittest.TestCase):
    def test_readme_maps_the_severity_metric(self) -> None:
        raw = README.read_text(encoding="utf-8")
        self.assertIn("](severity-accuracy.md)", raw)
        self.assertIn("#56", raw)

    def test_architecture_mentions_the_severity_metric(self) -> None:
        text = " ".join(ARCHITECTURE.read_text(encoding="utf-8").split())
        self.assertIn("severity-accuracy.md", text)
        self.assertIn("nothing benchmark", text)

    def test_reference_module_is_declared_test_only(self) -> None:
        head = REFERENCE.read_text(encoding="utf-8")[:700]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_unit_test_consumes_the_single_pairing_reference(self) -> None:
        raw = " ".join(UNIT_TEST.read_text(encoding="utf-8").split())
        self.assertIn("from tests.reference import benchmark_severity as bsev", raw)
        self.assertIn("never defines a second pairing or match relation", raw)


if __name__ == "__main__":
    unittest.main()
