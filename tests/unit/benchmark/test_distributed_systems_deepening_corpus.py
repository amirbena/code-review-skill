#!/usr/bin/env python3
"""Contract coverage for the Distributed Systems deepening benchmark
sub-corpus (Issue #272, parent #84, grandparent #82).

The sub-corpus is
``benchmark/corpus/distributed-systems-deepening/*.yaml``: a small,
focused set of ``benchmark-case/v2`` fixtures pinning representative
Distributed Systems deepening outcomes as follow-up quality hardening for
the capability #84 already defines — it validates domain correctness
after the capability exists and never redesigns it.

Like ``test_security_deepening_corpus.py``, every fixture decodes and
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

CORPUS_DIR = (
    REPO_ROOT / "benchmark" / "corpus" / "distributed-systems-deepening"
)

MIN_CASES = 6
MAX_CASES = 10

CONCURRENT_INTERLEAVING = (
    "distributed-systems-deepening-concurrent-interleaving-inventory-race"
)
RETRY_MISSING_IDEMPOTENCY = (
    "distributed-systems-deepening-retry-interaction-missing-idempotency"
)
OWNERSHIP_VIOLATED = "distributed-systems-deepening-ownership-assumption-violated"
RETRY_GUARDED_CLEAN = "distributed-systems-deepening-retry-idempotency-guarded-clean"
NOT_IMPLICATED_CLEAN = "distributed-systems-deepening-not-materially-implicated-clean"
FILENAME_SIGNAL_CLEAN = "distributed-systems-deepening-filename-signal-suppressed-clean"

REQUIRED_CASE_IDS = {
    CONCURRENT_INTERLEAVING,
    RETRY_MISSING_IDEMPOTENCY,
    OWNERSHIP_VIOLATED,
    RETRY_GUARDED_CLEAN,
    NOT_IMPLICATED_CLEAN,
    FILENAME_SIGNAL_CLEAN,
}

FLAGGED_CASE_IDS = {
    CONCURRENT_INTERLEAVING,
    RETRY_MISSING_IDEMPOTENCY,
    OWNERSHIP_VIOLATED,
}
CLEAN_CASE_IDS = {RETRY_GUARDED_CLEAN, NOT_IMPLICATED_CLEAN, FILENAME_SIGNAL_CLEAN}


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_all_required_cases_are_represented(self) -> None:
        missing = REQUIRED_CASE_IDS - set(self.by_id)
        self.assertEqual(missing, set(), f"missing required fixtures: {missing}")

    def test_clean_cases_have_no_required_findings(self) -> None:
        # A clean case may still carry an `optional` finding (e.g. the
        # guarded-retry case's durability note) -- what makes it `clean`
        # is that it carries no *required* finding, per severity.md's
        # mechanical decision derivation.
        for case_id in CLEAN_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                self.assertEqual(required, [])
                self.assertEqual(case.decision, "clean")

    def test_strictly_clean_cases_have_no_findings_at_all(self) -> None:
        # Unlike the guarded-retry case, these two carry no finding of
        # any kind -- the domain isn't implicated / naming alone doesn't
        # trigger engagement, so there is nothing to observe at all.
        for case_id in {NOT_IMPLICATED_CLEAN, FILENAME_SIGNAL_CLEAN}:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(list(case.findings), [])

    def test_guarded_clean_case_carries_only_an_optional_durability_note(self) -> None:
        case = self.by_id[RETRY_GUARDED_CLEAN]
        self.assertEqual(len(case.findings), 1)
        finding = case.findings[0]
        self.assertFalse(finding.required)
        self.assertEqual(finding.key, "in-memory-idempotency-guard-not-durable")

    def test_flagged_cases_each_have_exactly_one_required_p1_finding(self) -> None:
        for case_id in FLAGGED_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                self.assertEqual(len(required), 1)
                self.assertEqual(required[0].severities, ("P1",))
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
                "concurrent-read-decide-write-race",
                "retry-redelivery-missing-idempotency-guard",
                "coordination-assumption-violated-multi-writer",
            },
        )

    def test_at_least_one_case_is_changes_required_and_one_is_clean(self) -> None:
        decisions = {case.decision for case in self.by_id.values()}
        self.assertIn("changes-required", decisions)
        self.assertIn("clean", decisions)

    def test_every_case_is_tagged_concurrency(self) -> None:
        for case in self.by_id.values():
            self.assertIn("concurrency", case.metadata.get("tags", []))


class DistributedSystemsDeepeningCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = MIN_CASES
    max_cases = MAX_CASES
    readme_refs = ("#272",)


if __name__ == "__main__":
    unittest.main()
