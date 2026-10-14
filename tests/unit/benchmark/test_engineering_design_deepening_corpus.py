#!/usr/bin/env python3
"""Benchmark-case/v2 fixtures for the Engineering Design deepening
sub-corpus (Issue #750, parent #747).
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

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "engineering-design-deepening"

PREFIX = "engineering-design-deepening-"
P2_FINDING_CASE_IDS = {
    PREFIX + "ack-before-persist-loses-events",
    PREFIX + "claim-contradicted-by-repository",
    PREFIX + "self-declared-accepted-grants-nothing",
}
BLOCKING_CASE_ID = PREFIX + "code-contradicts-accepted-adr"
CLEAN_CASE_IDS = {
    PREFIX + "preference-only-alternative-clean",
    PREFIX + "acknowledged-tradeoff-clean",
    PREFIX + "missing-sections-not-a-finding-clean",
    PREFIX + "unverified-claim-no-finding-clean",
    PREFIX + "typo-only-adr-edit-inert-clean",
}
UNVERIFIED_CASE = PREFIX + "unverified-claim-no-finding-clean"
SELF_ACCEPT_CASE = PREFIX + "self-declared-accepted-grants-nothing"


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_exactly_the_required_cases_are_present(self) -> None:
        self.assertEqual(
            set(self.by_id), P2_FINDING_CASE_IDS | {BLOCKING_CASE_ID} | CLEAN_CASE_IDS
        )

    def test_design_only_findings_are_required_p2_and_non_blocking(self) -> None:
        for case_id in P2_FINDING_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                self.assertEqual(len(required), 1)
                self.assertEqual(required[0].severities, ("P2",))
                self.assertEqual(case.decision, "clean")

    def test_code_contradicting_accepted_decision_is_the_only_blocking_case(self) -> None:
        case = self.by_id[BLOCKING_CASE_ID]
        required = [f for f in case.findings if f.required]
        self.assertEqual(len(required), 1)
        self.assertEqual(required[0].severities, ("P1",))
        self.assertEqual(case.decision, "changes-required")
        # The accepted decision comes from the unchanged pre-image.
        self.assertIn("Status: Accepted", "\n".join(case.input["base"].values()))

    def test_no_case_expects_p0_and_defect_kinds_are_distinct(self) -> None:
        kinds = []
        for case_id, case in self.by_id.items():
            for f in case.findings:
                self.assertNotIn("P0", f.severities, case_id)
                kinds.append(f.defect_kind)
        self.assertNotIn(None, kinds)
        self.assertEqual(len(kinds), len(set(kinds)))

    def test_negative_cases_decide_clean_with_no_findings(self) -> None:
        for case_id in CLEAN_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(case.decision, "clean")
                self.assertEqual(list(case.findings), [])

    def test_unverified_claim_evidence_is_not_reachable(self) -> None:
        case = self.by_id[UNVERIFIED_CASE]
        self.assertNotIn("base", case.input)
        self.assertIn("gateway/limits.yaml", case.input["patch"])

    def test_self_declared_acceptance_case_sets_status_in_the_change(self) -> None:
        patch = self.by_id[SELF_ACCEPT_CASE].input["patch"]
        self.assertIn("+Status: Accepted", patch)
        self.assertNotIn("supersed", patch.lower())

    def test_typo_case_changes_no_decision(self) -> None:
        patch = self.by_id[PREFIX + "typo-only-adr-edit-inert-clean"].input["patch"]
        changed = [l for l in patch.splitlines() if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        self.assertEqual(len(changed), 2)

    def test_cases_use_the_engineering_design_taxonomy(self) -> None:
        for case_id, case in self.by_id.items():
            with self.subTest(case=case_id):
                taxonomy = case.metadata["taxonomy"]
                self.assertEqual(taxonomy["capability"], ["engineering-design"])
                self.assertEqual(taxonomy["policy_contract"], ["engineering-design-deepening"])


class EngineeringDesignDeepeningCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = 8
    max_cases = 10


if __name__ == "__main__":
    unittest.main()
