#!/usr/bin/env python3
"""Contract coverage for the Performance deepening benchmark sub-corpus
(Issue #187, parent #180, grandparent #82).

The sub-corpus is ``benchmark/corpus/performance-deepening/*.yaml``: a
small, focused set of ``benchmark-case/v2`` fixtures pinning representative
Performance deepening outcomes as follow-up quality hardening for the
capability #180 already defines — it validates domain correctness after
the capability exists and never redesigns it.

Like ``test_database_migration_deepening_corpus.py`` and
``test_distributed_systems_deepening_corpus.py``, every fixture decodes and
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

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "performance-deepening"

MIN_CASES = 6
MAX_CASES = 7

N_PLUS_ONE_REMOTE_CALL = "performance-deepening-n-plus-one-remote-call-in-loop"
NESTED_UNBOUNDED_SCAN_QUADRATIC = "performance-deepening-nested-unbounded-scan-quadratic"
BLOCKING_IO_REQUEST_HOT_PATH = "performance-deepening-blocking-io-request-hot-path"
BATCHED_FIX_BOUNDED_CLEAN = "performance-deepening-batched-fix-bounded-clean"
CONSTANT_SIZE_LOOP_CLEAN = "performance-deepening-constant-size-loop-clean"
NOT_IMPLICATED_CLEAN = "performance-deepening-non-executed-config-constant-not-implicated-clean"

REQUIRED_CASE_IDS = {
    N_PLUS_ONE_REMOTE_CALL,
    NESTED_UNBOUNDED_SCAN_QUADRATIC,
    BLOCKING_IO_REQUEST_HOT_PATH,
    BATCHED_FIX_BOUNDED_CLEAN,
    CONSTANT_SIZE_LOOP_CLEAN,
    NOT_IMPLICATED_CLEAN,
}

FLAGGED_CASE_IDS = {
    N_PLUS_ONE_REMOTE_CALL,
    NESTED_UNBOUNDED_SCAN_QUADRATIC,
    BLOCKING_IO_REQUEST_HOT_PATH,
}
CLEAN_CASE_IDS = {
    BATCHED_FIX_BOUNDED_CLEAN,
    CONSTANT_SIZE_LOOP_CLEAN,
    NOT_IMPLICATED_CLEAN,
}
# Clean cases that carry no finding of any kind (as opposed to
# BATCHED_FIX_BOUNDED_CLEAN, which carries one optional test note).
STRICTLY_CLEAN_CASE_IDS = {
    CONSTANT_SIZE_LOOP_CLEAN,
    NOT_IMPLICATED_CLEAN,
}


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_all_required_cases_are_represented(self) -> None:
        missing = REQUIRED_CASE_IDS - set(self.by_id)
        self.assertEqual(missing, set(), f"missing required fixtures: {missing}")

    def test_clean_cases_have_no_required_findings(self) -> None:
        # A clean case may still carry an `optional` finding (e.g. the
        # batched-fix case's missing-regression-test note) -- what makes it
        # `clean` is that it carries no *required* finding, per severity.md's
        # mechanical decision derivation.
        for case_id in CLEAN_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                self.assertEqual(required, [])
                self.assertEqual(case.decision, "clean")

    def test_strictly_clean_cases_have_no_findings_at_all(self) -> None:
        # Unlike the batched-fix case, these carry no finding of any kind --
        # either the domain isn't implicated at all, or a fixed/small bound
        # means no deeper tracing is warranted -- so there is nothing to
        # observe at all.
        for case_id in STRICTLY_CLEAN_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(list(case.findings), [])

    def test_batched_fix_case_carries_only_an_optional_test_note(self) -> None:
        case = self.by_id[BATCHED_FIX_BOUNDED_CLEAN]
        self.assertEqual(len(case.findings), 1)
        finding = case.findings[0]
        self.assertFalse(finding.required)
        self.assertEqual(finding.key, "missing-batched-invoice-lookup-regression-test")

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
                "n-plus-one-remote-call",
                "accidental-quadratic-scan",
                "blocking-io-in-hot-path",
            },
        )

    def test_at_least_one_case_is_changes_required_and_one_is_clean(self) -> None:
        decisions = {case.decision for case in self.by_id.values()}
        self.assertIn("changes-required", decisions)
        self.assertIn("clean", decisions)

    def test_every_case_is_tagged_performance(self) -> None:
        for case in self.by_id.values():
            self.assertIn("performance", case.metadata.get("tags", []))

    def test_no_cross_domain_composition_case_present(self) -> None:
        # Issue #187's explicit non-goal: this corpus is single-domain only.
        # #85 owns any cross-domain composition fixture and reuses this
        # corpus rather than this corpus growing one of its own.
        for case in self.by_id.values():
            tags = case.metadata.get("tags", [])
            self.assertNotIn("concurrency", tags)
            self.assertNotIn("security", tags)


class PerformanceDeepeningCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = MIN_CASES
    max_cases = MAX_CASES
    readme_refs = ("#187",)


if __name__ == "__main__":
    unittest.main()
