#!/usr/bin/env python3
"""Contract coverage for the Database / Migration deepening benchmark
sub-corpus (Issue #186, extended by Issue #279, parent #179, grandparent
#82).

The sub-corpus is
``benchmark/corpus/database-migration-deepening/*.yaml``: a small,
focused set of ``benchmark-case/v2`` fixtures pinning representative
Database / Migration deepening outcomes as follow-up quality hardening for
the capability #179 already defines — it validates domain correctness
after the capability exists and never redesigns it. Issue #279 extended
the original six relational (Django) fixtures with three storage-model-
agnostic fixtures (DynamoDB and MongoDB) pinning the capability's
generalized, non-relational worked examples; the relational fixtures are
unchanged in substance.

Like ``test_distributed_systems_deepening_corpus.py`` and
``test_security_deepening_corpus.py``, every fixture decodes and validates
through the *same* single reference validator
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
    REPO_ROOT / "benchmark" / "corpus" / "database-migration-deepening"
)

MIN_CASES = 9
MAX_CASES = 10

DESTRUCTIVE_DROP_COLUMN = "database-migration-deepening-destructive-drop-column"
UNSAFE_BLOCKING_LOCK = "database-migration-deepening-unsafe-online-blocking-lock"
NULLABLE_TO_NON_NULL_NO_BACKFILL = (
    "database-migration-deepening-nullable-to-non-null-no-backfill"
)
EXPAND_CONTRACT_SAFE_CLEAN = "database-migration-deepening-expand-contract-safe-clean"
ADDITIVE_NULLABLE_CLEAN = "database-migration-deepening-additive-nullable-column-clean"
COMMENT_ONLY_NOT_IMPLICATED_CLEAN = (
    "database-migration-deepening-comment-only-edit-not-implicated-clean"
)
# Non-relational fixtures added by Issue #279's storage-model-agnostic
# generalization of the capability.
DYNAMODB_GSI_BACKFILL_MISSING = (
    "database-migration-deepening-dynamodb-gsi-backfill-missing"
)
MONGODB_DOCUMENT_SHAPE_RENAME = (
    "database-migration-deepening-mongodb-document-shape-rename"
)
DYNAMODB_CONDITIONAL_WRITE_CLEAN = (
    "database-migration-deepening-dynamodb-conditional-write-no-data-model-change-clean"
)

REQUIRED_CASE_IDS = {
    DESTRUCTIVE_DROP_COLUMN,
    UNSAFE_BLOCKING_LOCK,
    NULLABLE_TO_NON_NULL_NO_BACKFILL,
    EXPAND_CONTRACT_SAFE_CLEAN,
    ADDITIVE_NULLABLE_CLEAN,
    COMMENT_ONLY_NOT_IMPLICATED_CLEAN,
    DYNAMODB_GSI_BACKFILL_MISSING,
    MONGODB_DOCUMENT_SHAPE_RENAME,
    DYNAMODB_CONDITIONAL_WRITE_CLEAN,
}

FLAGGED_CASE_IDS = {
    DESTRUCTIVE_DROP_COLUMN,
    UNSAFE_BLOCKING_LOCK,
    NULLABLE_TO_NON_NULL_NO_BACKFILL,
    DYNAMODB_GSI_BACKFILL_MISSING,
    MONGODB_DOCUMENT_SHAPE_RENAME,
}
CLEAN_CASE_IDS = {
    EXPAND_CONTRACT_SAFE_CLEAN,
    ADDITIVE_NULLABLE_CLEAN,
    COMMENT_ONLY_NOT_IMPLICATED_CLEAN,
    DYNAMODB_CONDITIONAL_WRITE_CLEAN,
}
# Clean cases that carry no finding of any kind (as opposed to
# EXPAND_CONTRACT_SAFE_CLEAN, which carries one optional test note).
STRICTLY_CLEAN_CASE_IDS = {
    ADDITIVE_NULLABLE_CLEAN,
    COMMENT_ONLY_NOT_IMPLICATED_CLEAN,
    DYNAMODB_CONDITIONAL_WRITE_CLEAN,
}


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_all_required_cases_are_represented(self) -> None:
        missing = REQUIRED_CASE_IDS - set(self.by_id)
        self.assertEqual(missing, set(), f"missing required fixtures: {missing}")

    def test_clean_cases_have_no_required_findings(self) -> None:
        # A clean case may still carry an `optional` finding (e.g. the
        # expand/contract case's backfill-interruption-test note) -- what
        # makes it `clean` is that it carries no *required* finding, per
        # severity.md's mechanical decision derivation.
        for case_id in CLEAN_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                self.assertEqual(required, [])
                self.assertEqual(case.decision, "clean")

    def test_strictly_clean_cases_have_no_findings_at_all(self) -> None:
        # Unlike the expand/contract case, these carry no finding of any
        # kind -- the domain isn't implicated, a superficial filename
        # signal alone doesn't trigger engagement, or (the DynamoDB case)
        # the domain is implicated but no data-model evolution signal
        # exists -- so there is nothing to observe at all.
        for case_id in STRICTLY_CLEAN_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(list(case.findings), [])

    def test_expand_contract_case_carries_only_an_optional_test_note(self) -> None:
        case = self.by_id[EXPAND_CONTRACT_SAFE_CLEAN]
        self.assertEqual(len(case.findings), 1)
        finding = case.findings[0]
        self.assertFalse(finding.required)
        self.assertEqual(finding.key, "missing-backfill-interruption-test")

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
                "destructive-migration-still-referenced-column",
                "blocking-lock-large-table-online-migration",
                "nullable-to-non-null-missing-backfill",
                "dynamodb-gsi-missing-backfill",
                "mongodb-document-rename-missing-coexistence",
            },
        )

    def test_at_least_one_case_is_changes_required_and_one_is_clean(self) -> None:
        decisions = {case.decision for case in self.by_id.values()}
        self.assertIn("changes-required", decisions)
        self.assertIn("clean", decisions)

    def test_every_case_is_tagged_correctness(self) -> None:
        for case in self.by_id.values():
            self.assertIn("correctness", case.metadata.get("tags", []))

    def test_no_cross_domain_composition_case_present(self) -> None:
        # Issue #186's explicit non-goal: this corpus is single-domain
        # only. #85 owns any cross-domain composition fixture and reuses
        # this corpus rather than this corpus growing one of its own.
        for case in self.by_id.values():
            tags = case.metadata.get("tags", [])
            self.assertNotIn("concurrency", tags)
            self.assertNotIn("security", tags)


class DatabaseMigrationDeepeningCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = MIN_CASES
    max_cases = MAX_CASES
    readme_refs = ("#186",)


if __name__ == "__main__":
    unittest.main()
