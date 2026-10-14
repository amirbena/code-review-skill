#!/usr/bin/env python3
"""Benchmark-case/v2 fixtures for the Deployment & Infrastructure deepening
sub-corpus (Issue #743, parent #740).
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

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "deployment-infrastructure-deepening"

PREFIX = "deployment-infrastructure-deepening-"
FLAGGED_CASE_IDS = {
    PREFIX + "probe-port-no-longer-matches-listener",
    PREFIX + "workflow-permissions-widened",
    PREFIX + "smoke-test-failure-no-longer-gates-deploy",
    PREFIX + "helm-value-key-renamed-template-unresolved",
}
CLEAN_CASE_IDS = {
    PREFIX + "memory-limit-raise-consistent-clean",
    PREFIX + "db-resize-impact-needs-plan-output",
    PREFIX + "comment-and-unused-label-edit-not-activated-clean",
    PREFIX + "dockerfile-from-only-boundary-clean",
}
GAP_CASE = PREFIX + "db-resize-impact-needs-plan-output"
NON_ACTIVATION_CASE = PREFIX + "comment-and-unused-label-edit-not-activated-clean"
BOUNDARY_CASE = PREFIX + "dockerfile-from-only-boundary-clean"


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_exactly_the_required_cases_are_present(self) -> None:
        self.assertEqual(set(self.by_id), FLAGGED_CASE_IDS | CLEAN_CASE_IDS)

    def test_flagged_cases_each_have_exactly_one_required_p1_finding(self) -> None:
        for case_id in FLAGGED_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                self.assertEqual(len(required), 1)
                self.assertEqual(required[0].severities, ("P1",))
                self.assertEqual(case.decision, "changes-required")

    def test_flagged_cases_are_distinct_defect_kinds(self) -> None:
        kinds = [
            f.defect_kind
            for case_id in FLAGGED_CASE_IDS
            for f in self.by_id[case_id].findings
        ]
        self.assertEqual(len(kinds), len(set(kinds)))
        self.assertNotIn(None, kinds)

    def test_clean_cases_decide_clean_with_no_required_finding(self) -> None:
        for case_id in CLEAN_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(case.decision, "clean")
                self.assertEqual([f for f in case.findings if f.required], [])

    def test_only_the_gap_case_carries_an_optional_finding(self) -> None:
        for case_id in CLEAN_CASE_IDS - {GAP_CASE}:
            self.assertEqual(list(self.by_id[case_id].findings), [], case_id)
        gap = list(self.by_id[GAP_CASE].findings)
        self.assertEqual(len(gap), 1)
        self.assertFalse(gap[0].required)
        self.assertNotIn("P0", gap[0].severities)

    def test_gap_case_states_the_missing_evidence(self) -> None:
        context = self.by_id[GAP_CASE].input["context"]
        self.assertIn("terraform plan", context)

    def test_non_activation_cases_fail_distinct_preconditions(self) -> None:
        # One changes only inert manifest content; the other changes only a
        # property owned by the dependency/supply-chain pass (#181).
        patch = self.by_id[NON_ACTIVATION_CASE].input["patch"]
        self.assertIn("k8s/deployment.yaml", patch)
        self.assertNotIn("replicas:", "\n".join(l for l in patch.splitlines() if l[:1] in "+-"))
        boundary = self.by_id[BOUNDARY_CASE].input["patch"]
        changed = [l for l in boundary.splitlines() if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        self.assertTrue(changed)
        self.assertTrue(all("FROM " in l for l in changed))

    def test_cases_use_the_deployment_taxonomy(self) -> None:
        for case_id, case in self.by_id.items():
            with self.subTest(case=case_id):
                taxonomy = case.metadata["taxonomy"]
                self.assertEqual(taxonomy["capability"], ["deployment-infrastructure"])
                self.assertEqual(
                    taxonomy["policy_contract"], ["deployment-infrastructure-deepening"]
                )

    def test_single_domain_no_cross_domain_composition(self) -> None:
        for case in self.by_id.values():
            self.assertNotIn("concurrency", case.metadata.get("tags", []))


class DeploymentInfrastructureDeepeningCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = 8
    max_cases = 10
    readme_refs = ("#743",)


if __name__ == "__main__":
    unittest.main()
