#!/usr/bin/env python3
"""Benchmark-case/v1 fixtures for the analogue-based placement-pattern-
inference sub-corpus (Issue #328, parent #327).
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

CORPUS_DIR = (
    REPO_ROOT / "benchmark" / "corpus" / "analogue-placement-pattern"
)

MIN_CASES = 4
MAX_CASES = 6

DEVIATION_MISSING_KEY = "analogue-placement-status-label-duplication-missing-key"
CONTROL_TEST_FILE_SPLIT = "analogue-placement-test-file-split-clean"
CONSOLIDATED_DUPLICATION = "analogue-placement-status-label-duplication-consolidated"
DISTINCT_BOUNDARIES = "analogue-placement-distinct-boundaries-not-consolidated"

REQUIRED_CASE_IDS = {
    DEVIATION_MISSING_KEY,
    CONTROL_TEST_FILE_SPLIT,
    CONSOLIDATED_DUPLICATION,
    DISTINCT_BOUNDARIES,
}

FLAGGED_CASE_IDS = {
    DEVIATION_MISSING_KEY,
    CONSOLIDATED_DUPLICATION,
    DISTINCT_BOUNDARIES,
}
CLEAN_CASE_IDS = {CONTROL_TEST_FILE_SPLIT}


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_all_required_cases_are_represented(self) -> None:
        missing = REQUIRED_CASE_IDS - set(self.by_id)
        self.assertEqual(missing, set(), f"missing required fixtures: {missing}")

    def test_control_case_has_no_findings_at_all(self) -> None:
        for case_id in CLEAN_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(list(case.findings), [])
                self.assertEqual(case.decision, "clean")

    def test_flagged_cases_are_changes_required(self) -> None:
        for case_id in FLAGGED_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(case.decision, "changes-required")
                required = [f for f in case.findings if f.required]
                self.assertGreaterEqual(len(required), 1)

    def test_single_deviation_case_has_exactly_one_required_finding(self) -> None:
        case = self.by_id[DEVIATION_MISSING_KEY]
        required = [f for f in case.findings if f.required]
        self.assertEqual(len(required), 1)

    def test_consolidated_case_has_exactly_one_required_finding_naming_all_sites(
        self,
    ) -> None:
        case = self.by_id[CONSOLIDATED_DUPLICATION]
        required = [f for f in case.findings if f.required]
        self.assertEqual(
            len(required), 1, "same-cause deviation at multiple sites must consolidate"
        )
        finding = required[0]
        claim = finding.claim.lower()
        for site in ("cli.py", "metrics.py", "alerts.py"):
            with self.subTest(site=site):
                self.assertIn(site, claim)

    def test_distinct_boundaries_case_has_exactly_two_required_findings(self) -> None:
        case = self.by_id[DISTINCT_BOUNDARIES]
        required = [f for f in case.findings if f.required]
        self.assertEqual(
            len(required),
            2,
            "cosmetically similar but materially different deviations must not merge",
        )
        keys = {f.key for f in required}
        self.assertEqual(
            keys,
            {
                "webhook-cli-inline-status-labels-missing-failed",
                "webhook-client-inline-auth-headers-missing-rotation",
            },
        )

    def test_every_case_is_tagged_quality(self) -> None:
        for case in self.by_id.values():
            self.assertIn("quality", case.metadata.get("tags", []))

    def test_control_case_claims_no_evidenced_boundary(self) -> None:
        # The control case's whole point is a structural difference with
        # no meaningful boundary behind it — confirm it stays literally
        # empty rather than smuggling in a low-severity finding.
        case = self.by_id[CONTROL_TEST_FILE_SPLIT]
        self.assertEqual(list(case.findings), [])

    def test_at_least_one_case_is_changes_required_and_one_is_clean(self) -> None:
        decisions = {case.decision for case in self.by_id.values()}
        self.assertIn("changes-required", decisions)
        self.assertIn("clean", decisions)


class SubCorpusReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_disclaims_any_canonically_correct_structure(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn(
            "does *not* assert", text, "README must disclaim any specific structure"
        )


class AnaloguePlacementPatternCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = MIN_CASES
    max_cases = MAX_CASES
    readme_refs = ("#328",)


if __name__ == "__main__":
    unittest.main()
