#!/usr/bin/env python3
"""Contract coverage for the API / contract compatibility benchmark
sub-corpus (Issue #184, parent #175).

The sub-corpus is ``docs/benchmark/corpus/api-compatibility/*.yaml``: a
small, focused set of ``benchmark-case/v2`` fixtures pinning the expected
compatible / breaking / context-dependent classification for the change
shapes #175's scope lists — add optional field, remove field, optional to
required, add enum member, remove enum member, rename response property —
before the reviewer capability itself exists.

Like ``test_null_absence_corpus.py``, every fixture decodes and validates
through the *same* single reference validator
(``tests/reference/benchmark/benchmark_fixture.py``) used for every other
corpus — this module never defines a second one.
"""

from __future__ import annotations

import unittest

import yaml

from tests.reference.benchmark import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus" / "api-compatibility"

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


def _corpus_files() -> list:
    return sorted(CORPUS_DIR.glob("*.yaml"))


def _load(path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class SubCorpusPresenceTests(unittest.TestCase):
    def test_directory_exists_with_a_readme(self) -> None:
        self.assertTrue(CORPUS_DIR.is_dir(), f"missing {CORPUS_DIR}")
        self.assertTrue((CORPUS_DIR / "README.md").is_file())

    def test_sub_corpus_is_small(self) -> None:
        n = len(_corpus_files())
        self.assertGreaterEqual(n, MIN_CASES, "a required case went missing")
        self.assertLessEqual(n, MAX_CASES, "sub-corpus is growing into a bulk library")


class SubCorpusCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = _corpus_files()
        self.assertTrue(self.files, "no api-compatibility fixtures found")

    def test_every_file_parses_and_validates(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                self.assertEqual(case.format, "benchmark-case/v2")

    def test_filename_stem_matches_case_id(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                self.assertEqual(case.id, path.stem)

    def test_case_ids_are_unique(self) -> None:
        ids = [bf.parse_case(_load(p)).id for p in self.files]
        self.assertEqual(len(ids), len(set(ids)), "duplicate case id in sub-corpus")

    def test_every_case_records_a_rationale_and_tags(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                rationale = case.metadata.get("rationale", "")
                self.assertTrue(
                    isinstance(rationale, str) and rationale.strip(),
                    "case-selection rationale must be recorded in metadata",
                )
                self.assertTrue(
                    case.metadata.get("tags"), "case must carry >=1 category tag"
                )

    def test_every_case_pins_an_explicit_consistent_decision(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                self.assertIsNotNone(
                    case.decision, "cases state `decision` as a cross-check"
                )
                self.assertEqual(case.decision, case.derived_decision)

    def test_patch_case_anchors_occur_in_the_diff_or_base(self) -> None:
        for path in self.files:
            case = bf.parse_case(_load(path))
            if case.input_kind != "patch":
                continue
            patch = case.input["patch"]
            base = case.input.get("base") or {}
            base_text = "\n".join(base.values())
            for finding in case.findings:
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    locs = [spec.location, *(a.get("location") for a in spec.alternatives)]
                    for loc in locs:
                        anchor = (loc or {}).get("anchor")
                        if anchor:
                            with self.subTest(case=path.name, anchor=anchor):
                                self.assertIn(anchor, patch + base_text)


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(_load(p)) for p in _corpus_files()}

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

    def test_no_finding_carries_a_severity_outside_p0_p1_p2(self) -> None:
        # No-new-severity acceptance criterion: every expected finding in
        # this sub-corpus uses the existing closed severity set.
        for case in self.by_id.values():
            for finding in case.findings:
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    for severity in spec.severities:
                        self.assertIn(severity, {"P0", "P1", "P2"})


class SubCorpusReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_links_every_fixture(self) -> None:
        for path in _corpus_files():
            self.assertIn(f"]({path.name})", self.raw, f"README omits {path.name}")

    def test_readme_states_the_selection_principle_and_scope(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("Selection principle", text)
        self.assertIn("#184", text)
        self.assertIn("not** packaged", text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../tests/reference/benchmark/benchmark_fixture.py)", self.raw
        )
        self.assertIn("never a second one", self.raw)


if __name__ == "__main__":
    unittest.main()
