#!/usr/bin/env python3
"""Contract coverage for the Security deepening benchmark sub-corpus
(Issue #271, parent #83, grandparent #82).

The sub-corpus is ``benchmark/corpus/security-deepening/*.yaml``: a
small, focused set of ``benchmark-case/v2`` fixtures pinning representative
Security deepening outcomes as follow-up quality hardening for the
capability #83 already defines — it validates domain correctness after the
capability exists and never redesigns it.

Like ``test_api_compatibility_corpus.py``, every fixture decodes and
validates through the *same* single reference validator
(``runtime_platform/benchmark/reference/benchmark_fixture.py``) used for every other
corpus — this module never defines a second one.
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

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "security-deepening"

MIN_CASES = 6
MAX_CASES = 10

ALTERNATE_PATH = "security-deepening-alternate-path-missing-check"
CONFUSED_DEPUTY = "security-deepening-confused-deputy-worker-credential"
SANITIZATION_BYPASS = "security-deepening-sanitization-assumption-bypass"
SINGLE_CALLER_CLEAN = "security-deepening-single-caller-check-enforced-clean"
AUTH_MODULE_CLEAN = "security-deepening-auth-module-no-trust-boundary-clean"
FILENAME_SIGNAL_CLEAN = "security-deepening-filename-signal-suppressed-clean"

REQUIRED_CASE_IDS = {
    ALTERNATE_PATH,
    CONFUSED_DEPUTY,
    SANITIZATION_BYPASS,
    SINGLE_CALLER_CLEAN,
    AUTH_MODULE_CLEAN,
    FILENAME_SIGNAL_CLEAN,
}

FLAGGED_CASE_IDS = {ALTERNATE_PATH, CONFUSED_DEPUTY, SANITIZATION_BYPASS}
CLEAN_CASE_IDS = {SINGLE_CALLER_CLEAN, AUTH_MODULE_CLEAN, FILENAME_SIGNAL_CLEAN}


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_all_required_cases_are_represented(self) -> None:
        missing = REQUIRED_CASE_IDS - set(self.by_id)
        self.assertEqual(missing, set(), f"missing required fixtures: {missing}")

    def test_clean_cases_have_no_findings_at_all(self) -> None:
        for case_id in CLEAN_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(list(case.findings), [])
                self.assertEqual(case.decision, "clean")

    def test_flagged_cases_each_have_exactly_one_required_p0_finding(self) -> None:
        for case_id in FLAGGED_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                self.assertEqual(len(required), 1)
                self.assertEqual(required[0].severities, ("P0",))
                self.assertEqual(case.decision, "changes-required")

    def test_flagged_cases_may_carry_an_optional_missing_test_note(self) -> None:
        for case_id in FLAGGED_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                optional = [f for f in case.findings if not f.required]
                for finding in optional:
                    self.assertFalse(finding.required)

    def test_all_flagged_cases_are_distinct_defect_kinds(self) -> None:
        defect_kinds = set()
        for case_id in FLAGGED_CASE_IDS:
            case = self.by_id[case_id]
            for finding in case.findings:
                if not finding.required:
                    continue
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    if spec.defect_kind:
                        defect_kinds.add(spec.defect_kind)
        self.assertEqual(
            defect_kinds,
            {
                "missing-authorization-alternate-path",
                "confused-deputy-unchecked-delegation",
                "path-traversal-sanitize-order-bypass",
            },
        )

    def test_at_least_one_case_is_changes_required_and_one_is_clean(self) -> None:
        decisions = {case.decision for case in self.by_id.values()}
        self.assertIn("changes-required", decisions)
        self.assertIn("clean", decisions)

    def test_every_case_is_tagged_security(self) -> None:
        for case in self.by_id.values():
            self.assertIn("security", case.metadata.get("tags", []))


class SecurityDeepeningCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = MIN_CASES
    max_cases = MAX_CASES
    readme_refs = ("#271",)


if __name__ == "__main__":
    unittest.main()
