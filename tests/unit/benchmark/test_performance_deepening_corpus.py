#!/usr/bin/env python3
"""Contract coverage for the Performance deepening benchmark sub-corpus
(Issue #187, parent #180, grandparent #82).

The sub-corpus is ``docs/benchmark/corpus/performance-deepening/*.yaml``: a
small, focused set of ``benchmark-case/v2`` fixtures pinning representative
Performance deepening outcomes as follow-up quality hardening for the
capability #180 already defines — it validates domain correctness after
the capability exists and never redesigns it.

Like ``test_database_migration_deepening_corpus.py`` and
``test_distributed_systems_deepening_corpus.py``, every fixture decodes and
validates through the *same* single reference validator
(``tests/reference/benchmark/benchmark_fixture.py``) used for every other
corpus — this module never defines a second one.
"""

from __future__ import annotations

import unittest

import yaml

from tests.reference.benchmark import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus" / "performance-deepening"

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
        self.assertTrue(self.files, "no performance-deepening fixtures found")

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

    def test_no_finding_carries_a_severity_outside_p0_p1_p2(self) -> None:
        for case in self.by_id.values():
            for finding in case.findings:
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    for severity in spec.severities:
                        self.assertIn(severity, {"P0", "P1", "P2"})

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


class SubCorpusReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_links_every_fixture(self) -> None:
        for path in _corpus_files():
            self.assertIn(f"]({path.name})", self.raw, f"README omits {path.name}")

    def test_readme_states_the_selection_principle_and_scope(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("Selection principle", text)
        self.assertIn("#187", text)
        self.assertIn("not** packaged", text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../tests/reference/benchmark/benchmark_fixture.py)", self.raw
        )
        self.assertIn("never a second one", self.raw)


if __name__ == "__main__":
    unittest.main()
