#!/usr/bin/env python3
"""Structural contract checks for the benchmark finding match criteria (#54).

Pins docs/benchmark/match-criteria.md so the canonical invariant, the
two-axis model, the fixed tolerances, the §5 combination table, the
allowed-alternative resolution, the determinism rules, the worked-example
conformance bar, and the deferred-scope boundaries cannot drift silently.
Prose assertions are whitespace-normalized; structural ones target
headings and literal terms.
"""

import unittest

from tests.support.paths import REPO_ROOT

DOC = REPO_ROOT / "docs" / "benchmark" / "match-criteria.md"
README = REPO_ROOT / "docs" / "benchmark" / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "benchmark_match.py"
UNIT_TEST = REPO_ROOT / "tests" / "unit" / "test_benchmark_match.py"


class MatchCriteriaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = DOC.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_is_repository_development_only_not_packaged(self) -> None:
        self.assertIn("repository-development doc: not packaged", self.text)
        self.assertIn("no packaged Skill resource depends on it", self.text)

    def test_names_issue_54_and_its_neighbours(self) -> None:
        for token in ("#54", "#50", "#52", "#55", "#56", "#57", "#41", "#42", "#59"):
            self.assertIn(token, self.raw)

    def test_canonical_invariant_is_stated_verbatim(self) -> None:
        self.assertIn(
            "A produced finding MATCHES an expected benchmark finding only "
            "when it corresponds on both axes — the same defect, at the same "
            "location — judged by deterministic criteria over the fixture's "
            "structured fields. Corresponding on one axis while falling short "
            "on the other is a NEAR-MISS; anything else is NO-MATCH. This "
            "relation decides pairing only: it never counts findings, computes "
            "a score, or judges severity.",
            self.text,
        )

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

    def test_determinism_rules_are_explicit(self) -> None:
        self.assertIn("## 7. Determinism and two-reader consistency", self.raw)
        self.assertIn("Fixed evaluation order.", self.raw)
        self.assertIn("No scores.", self.raw)
        self.assertIn("Ties resolve deterministically.", self.raw)
        self.assertIn("two people applying §3–§6 to them must reach the same", self.text)

    def test_worked_examples_are_the_conformance_bar(self) -> None:
        self.assertIn("## 8. Worked examples", self.raw)
        self.assertIn("encoded verbatim as data-driven cases", self.text)
        self.assertIn("](../../tests/unit/test_benchmark_match.py)", self.raw)
        for result in ("**`MATCH`**", "**`NEAR_MISS`**", "**`NO_MATCH`**"):
            self.assertIn(result, self.raw)
        self.assertIn("the **entry outcome** is `MATCH`", self.text)

    def test_scope_boundaries_defer_metrics_and_identity(self) -> None:
        self.assertIn("## 9. Explicitly out of scope", self.raw)
        boundary = " ".join(self.raw.split("## 9. Explicitly out of scope", 1)[1].split())
        self.assertIn("issues/55", boundary)
        self.assertIn("issues/56", boundary)
        self.assertIn("issues/57", boundary)
        self.assertIn("cross-revision stable finding identity", boundary)
        self.assertIn("issues/42", boundary)

    def test_status_defers_to_an_eventual_canonical_home(self) -> None:
        tail = " ".join(self.raw.split("## Status and canonical home", 1)[1].split())
        self.assertIn("becomes the design record", tail)
        self.assertIn("MUST NOT keep evolving the criteria independently", tail)
        self.assertIn("](../../tests/reference/benchmark_match.py)", self.raw)
        self.assertIn("](../../tests/unit/test_benchmark_match.py)", self.raw)


class DirectoryNavigationTests(unittest.TestCase):
    def test_readme_maps_the_match_criteria(self) -> None:
        raw = README.read_text(encoding="utf-8")
        self.assertIn("](match-criteria.md)", raw)
        self.assertIn("#54", raw)

    def test_architecture_mentions_the_match_criteria(self) -> None:
        text = " ".join(ARCHITECTURE.read_text(encoding="utf-8").split())
        self.assertIn("match-criteria.md", text)
        self.assertIn("nothing benchmark", text)

    def test_reference_module_is_declared_test_only(self) -> None:
        head = REFERENCE.read_text(encoding="utf-8")[:600]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_unit_test_consumes_the_single_reference_matcher(self) -> None:
        raw = UNIT_TEST.read_text(encoding="utf-8")
        self.assertIn("from tests.reference import benchmark_match as bm", raw)
        self.assertIn("never defines a second one", raw)


if __name__ == "__main__":
    unittest.main()
