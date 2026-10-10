#!/usr/bin/env python3
"""Contract coverage for the code hygiene benchmark sub-corpus (Issue #677,
parent #675, policy #676).

The sub-corpus is ``benchmark/corpus/code-hygiene/*.yaml``. Every fixture
validates through the single reference validator
(``runtime_platform/benchmark/reference/benchmark_fixture.py``); this module
never defines a second one. The default hygiene tier is a severity-less
observation outside the finding set, so non-P2 cases expect no findings.
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

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "code-hygiene"

OBSERVATION_CASE_IDS = {
    "code-hygiene-bare-issue-reference-observation",
    "code-hygiene-obsolete-tracker-comment-observation",
    "code-hygiene-todo-ticket-without-content-observation",
    "code-hygiene-poor-variable-name-observation",
}
CONTROL_CASE_IDS = {
    "code-hygiene-control-active-workaround-reference",
    "code-hygiene-control-known-limitation-reference",
    "code-hygiene-control-external-contract-and-compat-reference",
    "code-hygiene-control-conventional-loop-and-comprehension-names",
    "code-hygiene-control-legitimate-short-and-domain-names",
}
P2_CASE_IDS = {
    "code-hygiene-p2-misleading-name-with-causal-evidence",
    "code-hygiene-p2-reference-to-wrong-place-for-live-constraint",
}
REQUIRED_CASE_IDS = OBSERVATION_CASE_IDS | CONTROL_CASE_IDS | P2_CASE_IDS


class CodeHygieneSemanticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_all_required_shapes_are_represented(self) -> None:
        self.assertEqual(REQUIRED_CASE_IDS - set(self.by_id), set())

    def test_observation_and_control_cases_expect_no_findings_and_clean(self) -> None:
        for case_id in OBSERVATION_CASE_IDS | CONTROL_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(list(case.findings), [])
                self.assertEqual(case.findings_completeness, "exhaustive")
                self.assertEqual(case.decision, "clean")

    def test_p2_cases_carry_exactly_one_required_p2_finding(self) -> None:
        for case_id in P2_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(len(case.findings), 1)
                finding = case.findings[0]
                self.assertTrue(finding.required)
                self.assertEqual(finding.severities, ("P2",))
                # P2-only never blocks: hygiene cannot change the decision.
                self.assertEqual(case.decision, "clean")

    def test_hygiene_never_expects_p0_or_p1(self) -> None:
        for case in self.by_id.values():
            for finding in case.findings:
                self.assertNotIn("P0", finding.severities)
                self.assertNotIn("P1", finding.severities)

    def test_no_finding_cases_form_the_false_positive_basis(self) -> None:
        # The false-positive measurement is the count of findings reported on
        # the no-finding cases; they must exist alongside the P2 detection cases.
        no_finding = [c for c in self.by_id.values() if not c.findings]
        self.assertEqual(len(no_finding), len(OBSERVATION_CASE_IDS | CONTROL_CASE_IDS))

    def test_every_case_is_classified_code_hygiene(self) -> None:
        for case in self.by_id.values():
            self.assertEqual(case.metadata["taxonomy"]["capability"], ["code-hygiene"])


class CodeHygieneCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = 11
    max_cases = 12
    readme_refs = ("#677",)


if __name__ == "__main__":
    unittest.main()
