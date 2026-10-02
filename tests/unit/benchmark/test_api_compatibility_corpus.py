#!/usr/bin/env python3
"""Contract coverage for the API / contract compatibility benchmark
sub-corpus (Issue #184, parent #175).

The sub-corpus is ``benchmark/corpus/api-compatibility/*.yaml``: a
small, focused set of ``benchmark-case/v2`` fixtures pinning the expected
compatible / breaking / context-dependent classification for the change
shapes #175's scope lists — add optional field, remove field, optional to
required, add enum member, remove enum member, rename response property —
before the reviewer capability itself exists.

Like ``test_null_absence_corpus.py``, every fixture decodes and validates
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

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "api-compatibility"

MIN_CASES = 6
MAX_CASES = 10

ADD_OPTIONAL_FIELD = "api-compat-add-optional-field-compatible"
REMOVE_FIELD = "api-compat-remove-field-breaking"
OPTIONAL_TO_REQUIRED = "api-compat-optional-to-required-breaking"
ADD_ENUM_MEMBER = "api-compat-add-enum-member-context-dependent"
REMOVE_ENUM_MEMBER = "api-compat-remove-enum-member-breaking"
RENAME_PROPERTY = "api-compat-rename-response-property-breaking"

REQUIRED_CASE_IDS = {
    ADD_OPTIONAL_FIELD,
    REMOVE_FIELD,
    OPTIONAL_TO_REQUIRED,
    ADD_ENUM_MEMBER,
    REMOVE_ENUM_MEMBER,
    RENAME_PROPERTY,
}

CLEAN_CASE_IDS = {ADD_OPTIONAL_FIELD, ADD_ENUM_MEMBER}
BREAKING_CASE_IDS = {REMOVE_FIELD, OPTIONAL_TO_REQUIRED, REMOVE_ENUM_MEMBER, RENAME_PROPERTY}


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_all_required_cases_are_represented(self) -> None:
        missing = REQUIRED_CASE_IDS - set(self.by_id)
        self.assertEqual(missing, set(), f"missing required fixtures: {missing}")

    def test_compatible_case_has_no_findings_at_all(self) -> None:
        case = self.by_id[ADD_OPTIONAL_FIELD]
        self.assertEqual(list(case.findings), [])
        self.assertEqual(case.decision, "clean")

    def test_breaking_cases_each_have_exactly_one_required_finding(self) -> None:
        for case_id in BREAKING_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                self.assertEqual(len(required), 1)
                self.assertEqual(case.decision, "changes-required")

    def test_context_dependent_case_has_no_required_finding_but_an_optional_one(
        self,
    ) -> None:
        # #175's fail-closed requirement: an unresolvable consumer/intent
        # question produces a deterministic no-finding (clean) outcome,
        # not an invented breaking claim. The ambiguity is still surfaced,
        # but only as an optional finding.
        case = self.by_id[ADD_ENUM_MEMBER]
        required = [f for f in case.findings if f.required]
        optional = [f for f in case.findings if not f.required]
        self.assertEqual(required, [])
        self.assertEqual(len(optional), 1)
        self.assertEqual(case.decision, "clean")

    def test_enum_add_and_remove_cases_edit_the_identical_schema(self) -> None:
        # The deliberately matched pair: same enum, one member changed,
        # the only difference being addition versus removal.
        add_case = self.by_id[ADD_ENUM_MEMBER]
        remove_case = self.by_id[REMOVE_ENUM_MEMBER]
        for case in (add_case, remove_case):
            self.assertIn(
                "schemas/payment_status.schema.json", case.input["base"]
            )
        self.assertIn("refunded", add_case.input["patch"])
        self.assertIn("failed", remove_case.input["patch"])

    def test_all_six_change_shapes_are_distinct_defect_kinds(self) -> None:
        defect_kinds = set()
        for case in self.by_id.values():
            for finding in case.findings:
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    if spec.defect_kind:
                        defect_kinds.add(spec.defect_kind)
        self.assertEqual(
            defect_kinds,
            {
                "breaking-contract-field-removed",
                "breaking-contract-optional-to-required",
                "enum-member-added-context-dependent",
                "breaking-contract-enum-member-removed",
                "breaking-contract-property-renamed",
            },
        )

    def test_at_least_one_case_is_changes_required_and_one_is_clean(self) -> None:
        decisions = {case.decision for case in self.by_id.values()}
        self.assertIn("changes-required", decisions)
        self.assertIn("clean", decisions)


class ApiCompatibilityCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = MIN_CASES
    max_cases = MAX_CASES
    readme_refs = ("#184",)


if __name__ == "__main__":
    unittest.main()
