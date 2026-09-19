#!/usr/bin/env python3
"""Structural contract checks for the benchmark citation-existence check (#349).

Pins runtime_platform/benchmark/citation-fidelity.md so the canonical
invariant, the three statuses and the fixed reason order, the "undecidable
is never a failure" and "any one present quote suffices" defaults, the fixed
tolerances (kept equal to the reference module's constants), the
separate-metric-category and never-gates boundary, the worked-example
conformance bar, and the deferred-scope boundaries cannot drift silently.
Prose assertions are whitespace-normalized; structural ones target headings
and literal terms.
"""

import unittest

from runtime_platform.benchmark.reference import benchmark_citation as bc
from runtime_platform.benchmark.reference import benchmark_runner as br
from tests.support.paths import REPO_ROOT

BENCH = REPO_ROOT / "runtime_platform" / "benchmark"
DOC = BENCH / "citation-fidelity.md"
README = BENCH / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
DESIGN = (
    REPO_ROOT
    / "docs"
    / "benchmark-measurement-architecture"
    / "benchmark-measurement-architecture-model.md"
)
REFERENCE = BENCH / "reference" / "benchmark_citation.py"
UNIT_TEST = REPO_ROOT / "tests" / "unit" / "benchmark" / "test_benchmark_citation.py"


class CitationFidelityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = DOC.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_is_repository_development_only_not_packaged(self) -> None:
        self.assertIn("repository-development doc: not packaged", self.text)
        self.assertIn("no packaged Skill resource depends on it", self.text)

    def test_names_issue_349_its_dependency_and_neighbours(self) -> None:
        for token in ("#349", "#342", "#54", "#55", "#56", "#57", "#348", "§12.3", "§12.2"):
            self.assertIn(token, self.raw)

    def test_canonical_invariant_is_stated_verbatim(self) -> None:
        self.assertIn(
            "A benchmark run's citation fidelity is, per produced finding, one "
            "of three statuses — `verified`, `fabricated`, or `unverifiable` — "
            "decided only from the produced finding's own cited path, line "
            "span, symbol, and quoted evidence against the text of the files "
            "in the reviewed tree that the runner captured before cleanup: a "
            "finding is `fabricated` exactly when a check that could be run "
            "positively fails (the file is not in the tree, the line span is "
            "outside the file, the symbol is absent, or none of its quoted "
            "evidence is present near the cited location), `unverifiable` "
            "when nothing could be checked or existence could not be decided, "
            "and `verified` otherwise. The check proves existence only — "
            "never that the citation was inspected — and no expected finding, "
            "no match result, no severity, and no confidence enters it.",
            self.text,
        )

    def test_capture_rules(self) -> None:
        self.assertIn("## 2. Capturing the reviewed tree", self.raw)
        self.assertIn("`CaseResult.cited_sources`", self.raw)
        self.assertIn("after the reviewer returns and before cleanup", self.text)
        self.assertIn("is not a file of the reviewed tree", self.text)
        self.assertIn("Undecidable is not missing.", self.raw)
        self.assertIn("A capture failure never fails the case.", self.raw)

    def test_check_order_reasons_and_safe_defaults(self) -> None:
        self.assertIn("## 3. The per-finding check", self.raw)
        for reason in ("file-missing", "line-out-of-range", "symbol-absent", "snippet-absent"):
            self.assertIn(f"`{reason}`", self.raw)
        # reasons are documented in the order the module reports them
        positions = [self.raw.index(f"| `{r}` |") for r in
                     ("line-out-of-range", "symbol-absent", "snippet-absent")]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("a prose \"narrow section\" symbol is **never** checked", self.text)
        self.assertIn("**none** is present in the search window", self.text)
        self.assertIn("Nothing the check does depends on whether the finding `MATCH`es a fixture.", self.text)

    def test_tolerances_match_the_reference_module(self) -> None:
        self.assertIn("## 4. Quote rules and fixed tolerances", self.raw)
        self.assertIn(f"`SNIPPET_WINDOW_LINES` ({bc.SNIPPET_WINDOW_LINES})", self.raw)
        self.assertIn(f"`MIN_QUOTE_CHARS` ({bc.MIN_QUOTE_CHARS})", self.raw)
        self.assertIn(
            f"`SNIPPET_TOKEN_COVERAGE` ({bc.SNIPPET_TOKEN_COVERAGE.numerator}/"
            f"{bc.SNIPPET_TOKEN_COVERAGE.denominator}",
            self.raw,
        )
        self.assertIn("`MAX_CITED_FILE_BYTES` (1,000,000)", self.raw)
        self.assertEqual(br.MAX_CITED_FILE_BYTES, 1_000_000)
        self.assertIn(f"`MAX_CITED_PATHS` ({br.MAX_CITED_PATHS})", self.raw)
        self.assertIn("Any one present quote suffices", self.raw)

    def test_output_shape(self) -> None:
        self.assertIn("## 5. Per-case and aggregate output", self.raw)
        for field in (
            "`produced`",
            "`verified`",
            "`fabricated`",
            "`unverifiable`",
            "`fabrication_rate`",
            "`fabricated_findings`",
            "`total_fabricated`",
            "`cases_with_fabricated_citations`",
        ):
            self.assertIn(field, self.raw)
        self.assertIn("plain sums, no weighting, no score", self.text)

    def test_separate_category_and_never_gates(self) -> None:
        self.assertIn("## 6. Rendering and wiring", self.raw)
        self.assertIn("top-level `citation_fidelity` key **beside** `metrics`", self.text)
        self.assertIn("never merged into a match outcome", self.text)
        self.assertIn("Neither ever changes `has_regressions`", self.text)
        self.assertIn("no runtime gate on live reviews", self.text)

    def test_worked_examples_match_the_unit_test_rows(self) -> None:
        self.assertIn("## 7. Worked examples", self.raw)
        rows = [ln for ln in self.raw.splitlines() if ln.startswith("| ") and ln.split("|")[1].strip().isdigit()]
        self.assertEqual(len(rows), 11)
        unit = UNIT_TEST.read_text(encoding="utf-8")
        self.assertIn("class WorkedExampleTests", unit)

    def test_out_of_scope_boundaries(self) -> None:
        self.assertIn("## 8. Explicitly out of scope", self.raw)
        self.assertIn("provenance / citation grounding", self.text)
        self.assertIn("## Status and canonical home", self.raw)

    def test_reference_module_and_tests_exist(self) -> None:
        self.assertTrue(REFERENCE.is_file())
        self.assertTrue(UNIT_TEST.is_file())


class CitationFidelityRoutingTests(unittest.TestCase):
    def test_readme_routes_to_the_contract_and_reference(self) -> None:
        text = " ".join(README.read_text(encoding="utf-8").split())
        self.assertIn("[`citation-fidelity.md`](citation-fidelity.md)", text)
        self.assertIn("reference/benchmark_citation.py", text)
        self.assertIn("#349", text)

    def test_architecture_routes_to_the_contract(self) -> None:
        text = " ".join(ARCHITECTURE.read_text(encoding="utf-8").split())
        self.assertIn("runtime_platform/benchmark/citation-fidelity.md", text)

    def test_design_model_points_at_the_contract_and_no_longer_calls_342_open(self) -> None:
        text = " ".join(DESIGN.read_text(encoding="utf-8").split())
        self.assertIn("runtime_platform/benchmark/citation-fidelity.md", text)
        self.assertNotIn("#342 (open, P1)", text)


if __name__ == "__main__":
    unittest.main()
