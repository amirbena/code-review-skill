#!/usr/bin/env python3
"""Benchmark-case/v1 fixtures for the analogue-based placement-pattern-
inference sub-corpus (Issue #328, parent #327).
"""

from __future__ import annotations

import unittest

import yaml

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = (
    REPO_ROOT / "docs" / "benchmark" / "corpus" / "analogue-placement-pattern"
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
        self.assertTrue(self.files, "no analogue-placement-pattern fixtures found")

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

    def test_no_finding_carries_a_severity_outside_p0_p1_p2(self) -> None:
        for case in self.by_id.values():
            for finding in case.findings:
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    for severity in spec.severities:
                        self.assertIn(severity, {"P0", "P1", "P2"})

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

    def test_readme_links_every_fixture(self) -> None:
        for path in _corpus_files():
            self.assertIn(f"]({path.name})", self.raw, f"README omits {path.name}")

    def test_readme_states_the_selection_principle_and_scope(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("Selection principle", text)
        self.assertIn("#328", text)
        self.assertIn("not** packaged", text)

    def test_readme_disclaims_any_canonically_correct_structure(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn(
            "does *not* assert", text, "README must disclaim any specific structure"
        )

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../runtime_platform/benchmark/reference/benchmark_fixture.py)", self.raw
        )
        self.assertIn("never a second one", self.raw)


if __name__ == "__main__":
    unittest.main()
