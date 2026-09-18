#!/usr/bin/env python3
"""Benchmark-case/v1 fixtures for the Dependency / Supply-Chain deepening
sub-corpus (Issue #188, parent #181).
"""

from __future__ import annotations

import unittest

import yaml

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = (
    REPO_ROOT
    / "docs"
    / "benchmark"
    / "corpus"
    / "dependency-supply-chain-deepening"
)

MIN_CASES = 6
MAX_CASES = 8

MAJOR_VERSION_BREAKING_API = (
    "dependency-supply-chain-deepening-major-version-breaking-api-change"
)
RUNTIME_MINIMUM_RAISED = "dependency-supply-chain-deepening-runtime-minimum-raised"
TRANSITIVE_DEPENDENCY_EXPANSION = (
    "dependency-supply-chain-deepening-transitive-dependency-expansion"
)
UNPINNED_GITHUB_ACTIONS_REFERENCE = (
    "dependency-supply-chain-deepening-unpinned-github-actions-reference"
)
SAFE_PATCH_BUMP_CLEAN = "dependency-supply-chain-deepening-safe-patch-bump-clean"
NO_MANIFEST_TOUCHED_NOT_IMPLICATED_CLEAN = (
    "dependency-supply-chain-deepening-no-manifest-touched-not-implicated-clean"
)

REQUIRED_CASE_IDS = {
    MAJOR_VERSION_BREAKING_API,
    RUNTIME_MINIMUM_RAISED,
    TRANSITIVE_DEPENDENCY_EXPANSION,
    UNPINNED_GITHUB_ACTIONS_REFERENCE,
    SAFE_PATCH_BUMP_CLEAN,
    NO_MANIFEST_TOUCHED_NOT_IMPLICATED_CLEAN,
}

FLAGGED_CASE_IDS = {
    MAJOR_VERSION_BREAKING_API,
    RUNTIME_MINIMUM_RAISED,
    TRANSITIVE_DEPENDENCY_EXPANSION,
    UNPINNED_GITHUB_ACTIONS_REFERENCE,
}
CLEAN_CASE_IDS = {
    SAFE_PATCH_BUMP_CLEAN,
    NO_MANIFEST_TOUCHED_NOT_IMPLICATED_CLEAN,
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
        self.assertTrue(self.files, "no dependency-supply-chain-deepening fixtures found")

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

    def test_clean_cases_have_no_findings_at_all(self) -> None:
        for case_id in CLEAN_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(list(case.findings), [])
                self.assertEqual(case.decision, "clean")

    def test_flagged_cases_each_have_exactly_one_required_p1_finding(self) -> None:
        for case_id in FLAGGED_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                self.assertEqual(len(required), 1)
                self.assertEqual(required[0].severities, ("P1",))
                self.assertEqual(case.decision, "changes-required")

    def test_all_flagged_cases_are_distinct_defect_kinds(self) -> None:
        defect_kinds = set()
        for case_id in FLAGGED_CASE_IDS:
            case = self.by_id[case_id]
            for finding in case.findings:
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    if spec.defect_kind:
                        defect_kinds.add(spec.defect_kind)
        self.assertEqual(
            defect_kinds,
            {
                "major-version-bump-removed-api-still-called",
                "runtime-minimum-raise-narrows-documented-support",
                "unexplained-transitive-dependency-expansion",
                "unpinned-automation-reference-inconsistent-with-convention",
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

    def test_every_case_is_tagged_correctness(self) -> None:
        for case in self.by_id.values():
            self.assertIn("correctness", case.metadata.get("tags", []))

    def test_no_cross_domain_composition_case_present(self) -> None:
        # This corpus is single-domain only, matching Issue #188's
        # non-goals and the same discipline as the Database / Migration
        # deepening corpus (#186): #85 owns any cross-domain composition
        # fixture and reuses this corpus rather than this corpus growing
        # one of its own.
        for case in self.by_id.values():
            tags = case.metadata.get("tags", [])
            self.assertNotIn("concurrency", tags)
            self.assertNotIn("security", tags)

    def test_negative_cases_prove_distinct_non_activation_reasons(self) -> None:
        # SAFE_PATCH_BUMP_CLEAN fails the concern-area evidence bar
        # (a qualifying file changes but no concern area is implicated);
        # NO_MANIFEST_TOUCHED_NOT_IMPLICATED_CLEAN fails the diff-
        # recognition signal itself (no qualifying file changes at all).
        # Distinct reasons, so a regression in either is caught even if
        # the other stays correct.
        safe_bump = self.by_id[SAFE_PATCH_BUMP_CLEAN]
        no_manifest = self.by_id[NO_MANIFEST_TOUCHED_NOT_IMPLICATED_CLEAN]
        self.assertIn("package.json", safe_bump.input["patch"])
        for qualifying in ("package.json", "package-lock.json", "Dockerfile", ".github/workflows"):
            self.assertNotIn(qualifying, no_manifest.input["patch"])


class SubCorpusReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_links_every_fixture(self) -> None:
        for path in _corpus_files():
            self.assertIn(f"]({path.name})", self.raw, f"README omits {path.name}")

    def test_readme_states_the_selection_principle_and_scope(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("Selection principle", text)
        self.assertIn("#188", text)
        self.assertIn("not** packaged", text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../runtime_platform/benchmark/reference/benchmark_fixture.py)", self.raw
        )
        self.assertIn("never a second one", self.raw)


if __name__ == "__main__":
    unittest.main()
