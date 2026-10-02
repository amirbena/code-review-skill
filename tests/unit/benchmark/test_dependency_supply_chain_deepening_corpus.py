#!/usr/bin/env python3
"""Benchmark-case/v1 fixtures for the Dependency / Supply-Chain deepening
sub-corpus (Issue #188, parent #181).
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
    REPO_ROOT
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


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

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


class DependencySupplyChainDeepeningCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = MIN_CASES
    max_cases = MAX_CASES
    readme_refs = ("#188",)


if __name__ == "__main__":
    unittest.main()
