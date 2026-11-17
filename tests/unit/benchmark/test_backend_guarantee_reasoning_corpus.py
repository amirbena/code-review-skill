#!/usr/bin/env python3
"""Contract coverage for the backend guarantee-reasoning sub-corpus
(Issue #874): each dimension is covered by at least two mechanisms and
paired with clean cases for guarded or hypothetical risks."""

from __future__ import annotations

import unittest

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from tests.support.corpus_hygiene import (
    CorpusHygieneMixin,
    corpus_files,
    load_fixture,
)
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "backend-guarantee-reasoning"

DIMENSIONS = ("coordination", "persistence", "external-contract")


class GuaranteeDimensionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def _flagged(self, dimension: str) -> list[str]:
        prefix = f"backend-guarantee-{dimension}-"
        return [i for i in self.cases if i.startswith(prefix)]

    def test_each_dimension_has_two_mechanisms(self) -> None:
        for dimension in DIMENSIONS:
            with self.subTest(dimension=dimension):
                self.assertGreaterEqual(len(self._flagged(dimension)), 2)

    def test_flagged_cases_have_one_required_finding(self) -> None:
        for dimension in DIMENSIONS:
            for case_id in self._flagged(dimension):
                with self.subTest(case=case_id):
                    required = [f for f in self.cases[case_id].findings if f.required]
                    self.assertEqual(len(required), 1)

    def test_mock_only_gaps_stay_p2(self) -> None:
        for case_id in self._flagged("external-contract"):
            with self.subTest(case=case_id):
                required = [f for f in self.cases[case_id].findings if f.required]
                self.assertEqual(required[0].severities, ("P2",))

    def test_clean_cases_carry_no_findings(self) -> None:
        clean = [i for i in self.cases if i.startswith("backend-guarantee-clean-")]
        self.assertGreaterEqual(len(clean), 5)
        for case_id in clean:
            with self.subTest(case=case_id):
                self.assertEqual(list(self.cases[case_id].findings), [])
                self.assertEqual(self.cases[case_id].decision, "clean")


class BackendGuaranteeReasoningCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = 11
    max_cases = 14


if __name__ == "__main__":
    unittest.main()
