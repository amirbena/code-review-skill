#!/usr/bin/env python3
"""Contract coverage for the null-like absence-risk benchmark sub-corpus
(Issue #121).

The sub-corpus is ``benchmark/corpus/null-absence-risk/*.yaml``: a
small, focused set of ``benchmark-case/v2`` fixtures demonstrating
shared/policies/review-scope.md's "Null-like absence-risk review"
requirement — a real null/undefined/nil dereference risk surfaced, its
directly guarded counterpart correctly not reported, an optional/lookup-
result path with unchecked absence surfaced, JavaScript/TypeScript
undefined/null property access, and a null-safe-language interoperability
edge case (a Kotlin platform type from Java interop).

Like ``test_semantic_implication_corpus.py``, every fixture decodes and
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

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "null-absence-risk"

MIN_CASES = 6
MAX_CASES = 10

JAVA_UNGUARDED = "null-absence-java-unguarded-dereference"
JAVA_GUARDED_CLEAN = "null-absence-java-guarded-clean"
GO_UNCHECKED_LOOKUP = "null-absence-go-unchecked-map-lookup"
TS_OPTIONAL_PROPERTY = "null-absence-typescript-optional-property-access"
KOTLIN_JAVA_PLATFORM_TYPE = "null-absence-kotlin-java-platform-type"
JAVA_GUARDED_AND_UNGUARDED_COMBINED = "null-absence-java-guarded-and-unguarded-combined"

REQUIRED_CASE_IDS = {
    JAVA_UNGUARDED,
    JAVA_GUARDED_CLEAN,
    GO_UNCHECKED_LOOKUP,
    TS_OPTIONAL_PROPERTY,
    KOTLIN_JAVA_PLATFORM_TYPE,
    JAVA_GUARDED_AND_UNGUARDED_COMBINED,
}

CLEAN_CASE_IDS = {JAVA_GUARDED_CLEAN}


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_all_required_cases_are_represented(self) -> None:
        missing = REQUIRED_CASE_IDS - set(self.by_id)
        self.assertEqual(missing, set(), f"missing required fixtures: {missing}")

    def test_unguarded_case_has_exactly_one_required_finding(self) -> None:
        case = self.by_id[JAVA_UNGUARDED]
        required = [f for f in case.findings if f.required]
        self.assertEqual(len(required), 1)
        self.assertEqual(case.decision, "changes-required")

    def test_guarded_counterpart_has_no_findings_at_all(self) -> None:
        case = self.by_id[JAVA_GUARDED_CLEAN]
        self.assertEqual(list(case.findings), [])
        self.assertEqual(case.decision, "clean")

    def test_guarded_pair_shares_the_same_nullable_source_and_call_site(self) -> None:
        # The pair's point is that reachability, not declared type, decides
        # the outcome — so both cases must share the same nullable
        # repository contract and the same call site shape.
        unguarded = self.by_id[JAVA_UNGUARDED]
        guarded = self.by_id[JAVA_GUARDED_CLEAN]
        for case in (unguarded, guarded):
            self.assertIn(
                "src/main/java/app/user/UserRepository.java", case.input["base"]
            )
        self.assertIn("user.getEmail()", unguarded.input["patch"])
        self.assertIn("user.getEmail()", guarded.input["patch"])

    def test_lookup_and_ts_and_interop_cases_each_have_one_required_finding(
        self,
    ) -> None:
        for case_id in (GO_UNCHECKED_LOOKUP, TS_OPTIONAL_PROPERTY, KOTLIN_JAVA_PLATFORM_TYPE):
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                self.assertEqual(len(required), 1)
                self.assertEqual(case.decision, "changes-required")

    def test_combined_case_has_the_literal_same_fixture_spot_check(self) -> None:
        # Issue #121's Validation section: "a guarded value and an
        # unguarded value in the same fixture produce exactly one
        # finding." This case is the literal, single-diff demonstration —
        # not a matched pair across two files.
        case = self.by_id[JAVA_GUARDED_AND_UNGUARDED_COMBINED]
        required = [f for f in case.findings if f.required]
        self.assertEqual(len(required), 1)
        self.assertEqual(case.decision, "changes-required")
        patch = case.input["patch"]
        self.assertIn("confirm(long orderId)", patch)
        self.assertIn("confirmSafely(long orderId)", patch)
        finding = required[0]
        self.assertEqual(finding.location["symbol"], "confirm")
        self.assertNotEqual(finding.location["symbol"], "confirmSafely")

    def test_cases_span_at_least_three_language_families(self) -> None:
        # Validation requirement: at least Java/Kotlin, JavaScript/TypeScript,
        # and one of C#/Python/Go.
        java_kotlin = {JAVA_UNGUARDED, JAVA_GUARDED_CLEAN, KOTLIN_JAVA_PLATFORM_TYPE}
        js_ts = {TS_OPTIONAL_PROPERTY}
        other = {GO_UNCHECKED_LOOKUP}
        self.assertTrue(java_kotlin & set(self.by_id))
        self.assertTrue(js_ts & set(self.by_id))
        self.assertTrue(other & set(self.by_id))

    def test_at_least_one_case_is_changes_required_and_one_is_clean(self) -> None:
        decisions = {case.decision for case in self.by_id.values()}
        self.assertIn("changes-required", decisions)
        self.assertIn("clean", decisions)


class NullAbsenceCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = MIN_CASES
    max_cases = MAX_CASES
    readme_refs = ("#121",)
    validator_phrase = "never defines a second"


if __name__ == "__main__":
    unittest.main()
