#!/usr/bin/env python3
"""Structural contract checks for the benchmark finding match criteria (#54).

Pins runtime_platform/benchmark/match-criteria.md so the canonical invariant, the
two-axis model, the fixed tolerances, the §5 combination table, the
allowed-alternative resolution, the determinism rules, the worked-example
conformance bar, and the deferred-scope boundaries cannot drift silently.
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
DOC = BENCH / "match-criteria.md"

SPEC = BenchmarkDocSpec(
    doc=DOC,
    issue_tokens=("#54", "#50", "#52", "#55", "#56", "#57", "#41", "#42", "#59"),
    invariant=(
        "A produced finding MATCHES an expected benchmark finding only "
        "when it corresponds on both axes — the same defect, at the same "
        "location — judged by deterministic criteria over the fixture's "
        "structured fields. Corresponding on one axis while falling short "
        "on the other is a NEAR-MISS; anything else is NO-MATCH. This "
        "relation decides pairing only: it never counts findings, computes "
        "a score, or judges severity."
    ),
    sections=(
        Section(
            "## 7. Determinism and two-reader consistency",
            raw=("Fixed evaluation order.", "No scores.", "Ties resolve deterministically."),
            text=("two people applying §3–§6 to them must reach the same",),
        ),
        Section(
            "## 8. Worked examples",
            raw=(
                "](../../tests/unit/benchmark/test_benchmark_match.py)",
                "**`MATCH`**",
                "**`NEAR_MISS`**",
                "**`NO_MATCH`**",
            ),
            text=("encoded verbatim as data-driven cases", "the **entry outcome** is `MATCH`"),
        ),
        Section(
            "## 9. Explicitly out of scope",
            body=(
                "issues/55",
                "issues/56",
                "issues/57",
                "cross-revision stable finding identity",
                "issues/42",
            ),
        ),
    ),
    status_body=("becomes the design record", "MUST NOT keep evolving the criteria independently"),
    status_raw=(
        "](reference/benchmark_match.py)",
        "](../../tests/unit/benchmark/test_benchmark_match.py)",
    ),
    readme_link="](match-criteria.md)",
    readme_issue="#54",
    architecture_name="match-criteria.md",
    reference=BENCH / "reference" / "benchmark_match.py",
    reference_head_chars=600,
    unit_test=REPO_ROOT / "tests" / "unit" / "benchmark" / "test_benchmark_match.py",
    unit_import="from runtime_platform.benchmark.reference import benchmark_match as bm",
    unit_phrase="never defines a second one",
)


class MatchCriteriaContractTests(BenchmarkDocContractMixin, unittest.TestCase):
    spec = SPEC

    def test_two_axes_borrow_the_finding_matching_discipline(self) -> None:
        self.assertIn("## 2. The two match axes", self.raw)
        self.assertIn("defect continuity + site continuity", self.text)
        self.assertIn("MATCH requires **both** axes to correspond", self.text)
        self.assertIn("Severity is **not** an axis.", self.raw)

    def test_location_axis_gates_on_intent_and_path(self) -> None:
        self.assertIn("## 3. Location correspondence", self.raw)
        self.assertIn("Result is one of **EXACT**, **NEAR**, **NONE**", self.text)
        self.assertIn("A finding in the wrong file is not the same finding.", self.text)
        self.assertIn("proximity window** is a fixed **± 3 lines**", self.text)
        self.assertIn("`lines` are **advisory**", self.text)

    def test_defect_axis_thresholds_are_fixed_in_the_doc(self) -> None:
        self.assertIn("## 4. Defect correspondence", self.raw)
        self.assertIn("Result is one of **CORRESPONDS**, **RELATED**, **UNRELATED**", self.text)
        self.assertIn("Jaccard overlap is **≥ 0.5**", self.text)
        self.assertIn("Jaccard overlap is **≥ 0.25**", self.text)
        self.assertIn("thresholds (0.5, 0.25) are fixed by this document", self.text)
        self.assertIn("never sufficient for a `CORRESPONDS`", self.text)

    def test_compatible_slug_rule_and_revision_boundary_are_documented(self) -> None:
        self.assertIn("**Compatible free-form slugs (issue #570).**", self.text)
        self.assertIn("at least two tokens", self.text)
        self.assertIn("at least two** and are **≥ 0.5**", self.text)
        self.assertIn("pairing is greedy in fixture order", self.text)
        self.assertIn("never a `MATCH`", self.text)
        self.assertIn("## 10. Contract revisions and metric comparability", self.raw)
        self.assertIn("Historical records are not reinterpreted.", self.text)
        self.assertIn("does not extend the sealed `benchmark-result/v1` schema", self.text)

    def test_combination_table_is_present(self) -> None:
        self.assertIn("## 5. Combining the axes", self.raw)
        self.assertIn("| Location \\ Defect | CORRESPONDS | RELATED | UNRELATED |", self.raw)
        for cell in ("`MATCH`", "`NEAR_MISS`", "`NO_MATCH`"):
            self.assertIn(cell, self.raw)
        self.assertIn("A near-miss is **not** a match", self.text)

    def test_allowed_alternatives_resolution_is_documented(self) -> None:
        self.assertIn("## 6. Allowed alternatives and optionality", self.raw)
        for construct in ("`alternatives` (construct 1)", "`any_of` group (construct 2)",
                          "`match: optional` (construct 3)", "`severity` list (construct 4)"):
            self.assertIn(construct, self.raw)
        self.assertIn("Ignored here entirely — matching is severity-independent", self.text)


class DirectoryNavigationTests(BenchmarkDocNavigationMixin, unittest.TestCase):
    spec = SPEC


if __name__ == "__main__":
    unittest.main()
