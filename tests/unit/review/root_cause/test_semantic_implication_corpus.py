#!/usr/bin/env python3
"""Contract coverage for the semantic-implication benchmark sub-corpus
(Issue #211).

The sub-corpus is ``benchmark/corpus/semantic-implication/*.yaml``: a
small, focused set of ``benchmark-case/v2`` fixtures demonstrating
shared/policies/review-scope.md's "Semantic change-implication reasoning"
base pass — a single dimension activating alone, one change materially
implicating several dimensions at once, a change with no material signal
for any dimension, and a dimension whose signal fires but for which
available evidence cannot support a finding.

Unlike ``test_risk_depth_corpus.py``, this module pairs with no
deterministic reference model: "Semantic change-implication reasoning" is
a judgment-based pass with no mechanical classification function, exactly
like "Architectural placement and execution-lifecycle fidelity" (#153)
before it, which also ships with no reference-model scenarios file. What
is proven here is structural: every fixture decodes and validates through
the *same* single reference validator
(``runtime_platform/benchmark/reference/benchmark_fixture.py``) used for the worked
example and every other corpus — this module never defines a second one.
"""

from __future__ import annotations

import unittest

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from tests.support.corpus_hygiene import (
    CorpusHygieneMixin,
    corpus_files,
    load_fixture,
)
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "semantic-implication"

MIN_CASES = 4
MAX_CASES = 10

SINGLE_DIMENSION_PERSISTENCE = "semantic-implication-single-dimension-persistence"
MULTI_DIMENSION_WEBHOOK_XSS = "semantic-implication-multi-dimension-webhook-xss"
NO_SIGNAL_CLEAN_EXTRACTION = "semantic-implication-no-signal-clean-extraction"
INSUFFICIENT_EVIDENCE_STOP = "semantic-implication-insufficient-evidence-stop"

REQUIRED_CASE_IDS = {
    SINGLE_DIMENSION_PERSISTENCE,
    MULTI_DIMENSION_WEBHOOK_XSS,
    NO_SIGNAL_CLEAN_EXTRACTION,
    INSUFFICIENT_EVIDENCE_STOP,
}

CLEAN_CASE_IDS = {NO_SIGNAL_CLEAN_EXTRACTION, INSUFFICIENT_EVIDENCE_STOP}


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_all_required_cases_are_represented(self) -> None:
        missing = REQUIRED_CASE_IDS - set(self.by_id)
        self.assertEqual(missing, set(), f"missing required fixtures: {missing}")

    def test_single_dimension_case_has_exactly_one_required_finding(self) -> None:
        case = self.by_id[SINGLE_DIMENSION_PERSISTENCE]
        required = [f for f in case.findings if f.required]
        self.assertEqual(len(required), 1)
        self.assertEqual(case.decision, "changes-required")

    def test_multi_dimension_case_stays_one_root_cause_finding(self) -> None:
        # F1: the point of the multi-dimension case is that several
        # dimensions are implicated by one change, never that each
        # implicated dimension must produce its own finding.
        case = self.by_id[MULTI_DIMENSION_WEBHOOK_XSS]
        required = [f for f in case.findings if f.required]
        self.assertEqual(len(required), 1)
        self.assertEqual(case.decision, "changes-required")

    def test_clean_cases_have_no_findings_at_all(self) -> None:
        for case_id in CLEAN_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(list(case.findings), [])
                self.assertEqual(case.decision, "clean")

    def test_at_least_one_case_is_changes_required_and_one_is_clean(self) -> None:
        decisions = {case.decision for case in self.by_id.values()}
        self.assertIn("changes-required", decisions)
        self.assertIn("clean", decisions)


class SubCorpusReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_explains_why_there_is_no_reference_model_file(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("No reference-model scenario file", text)
        self.assertIn("judgment-based reasoning pass", text)
        self.assertIn("#153", text)


class SemanticImplicationCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = MIN_CASES
    max_cases = MAX_CASES
    readme_refs = ("#211",)
    validator_phrase = "never defines a second"


if __name__ == "__main__":
    unittest.main()
