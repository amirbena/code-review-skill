#!/usr/bin/env python3
"""Benchmark-case/v2 fixtures for the finding-placement (fix/action
location derivation) sub-corpus (Issue #387, parent #385, implementation
contract #386).
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

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "finding-placement"

MIN_CASES = 11
MAX_CASES = 14

CAUSAL_SITE = "finding-placement-causal-site-not-symptom"
DOWNSTREAM_UNSAFE = "finding-placement-downstream-unsafe-handling"
CALLER_PRECONDITION = "finding-placement-caller-precondition-violation"
CALLEE_CONTRACT = "finding-placement-callee-contract-violation"
PREEXISTING_CALLEE_BUG = "finding-placement-preexisting-callee-bug-exposed"
CONTEXT_EXPANSION_DRIFT = "finding-placement-context-expansion-drift"
PRECEDENT_TRAP = "finding-placement-precedent-trap"
FALSE_PRECISION = "finding-placement-false-precision-nearest-line"
MULTI_FILE_PRIMARY = "finding-placement-multi-file-primary-selection"
FALLBACK_UNRESOLVED = "finding-placement-fallback-reuses-unresolved-location-state"
TEST_REVEALS_PROD = "finding-placement-test-reveals-production-defect"
DEFECTIVE_TEST = "finding-placement-defective-test-not-production"

REQUIRED_CASE_IDS = {
    CAUSAL_SITE,
    DOWNSTREAM_UNSAFE,
    CALLER_PRECONDITION,
    CALLEE_CONTRACT,
    PREEXISTING_CALLEE_BUG,
    CONTEXT_EXPANSION_DRIFT,
    PRECEDENT_TRAP,
    FALSE_PRECISION,
    MULTI_FILE_PRIMARY,
    FALLBACK_UNRESOLVED,
    TEST_REVEALS_PROD,
    DEFECTIVE_TEST,
}

# Every case in this corpus flags exactly one required finding at one
# expected primary-location path; nothing here is a clean/control case.
EXPECTED_PRIMARY_PATH = {
    CAUSAL_SITE: "pricing/discount.py",
    DOWNSTREAM_UNSAFE: "billing/invoice.py",
    CALLER_PRECONDITION: "orders/api.py",
    CALLEE_CONTRACT: "pricing/tax.py",
    PREEXISTING_CALLEE_BUG: "inventory/adjust.py",
    CONTEXT_EXPANSION_DRIFT: "notifications/email.py",
    PRECEDENT_TRAP: "integrations/webhook/client.py",
    FALSE_PRECISION: "orders/state.py",
    MULTI_FILE_PRIMARY: "config/schema.py",
    FALLBACK_UNRESOLVED: "shared/validators.py",
    TEST_REVEALS_PROD: "math/stats.py",
    DEFECTIVE_TEST: "tests/test_stats.py",
}

# Files a naive/mechanical reviewer might wrongly anchor to instead of the
# true primary location, per case -- proving the corpus actually
# discriminates rather than accepting any touched file.
WRONG_ANCHOR_CANDIDATES = {
    CAUSAL_SITE: {"billing/invoice.py"},
    DOWNSTREAM_UNSAFE: {"pricing/discount.py"},
    CALLER_PRECONDITION: {"orders/repository.py"},
    CALLEE_CONTRACT: {"billing/checkout.py"},
    PREEXISTING_CALLEE_BUG: {"orders/cancel.py"},
    CONTEXT_EXPANSION_DRIFT: {
        "utils/money.py",
        "notifications/sms.py",
        "tests/test_email.py",
    },
    PRECEDENT_TRAP: {"integrations/slack/client.py"},
    MULTI_FILE_PRIMARY: {"config/loader.py", "cli/main.py"},
    FALLBACK_UNRESOLVED: {"signup/api.py"},
    TEST_REVEALS_PROD: {"tests/test_stats.py"},
    DEFECTIVE_TEST: {"math/stats.py"},
}

# The out-of-diff fallback case's location deliberately resolves outside
# the patch; every other case's location must resolve inside the patch it
# actually touches.
OUT_OF_DIFF_LOCATION_CASES = {PREEXISTING_CALLEE_BUG, FALLBACK_UNRESOLVED}


class SubCorpusCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = corpus_files(CORPUS_DIR)
        self.assertTrue(self.files, "no finding-placement fixtures found")

    def test_every_case_is_changes_required(self) -> None:
        # Every scenario in this corpus flags exactly one real, primary
        # defect -- there is no clean/control case here.
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(load_fixture(path))
                self.assertEqual(case.decision, "changes-required")


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_all_required_cases_are_represented(self) -> None:
        missing = REQUIRED_CASE_IDS - set(self.by_id)
        self.assertEqual(missing, set(), f"missing required fixtures: {missing}")

    def test_every_case_has_exactly_one_required_finding(self) -> None:
        for case_id, case in self.by_id.items():
            with self.subTest(case=case_id):
                required = [f for f in case.findings if f.required]
                self.assertEqual(
                    len(required), 1, "each scenario pins exactly one primary defect"
                )

    def test_every_case_anchors_at_its_expected_primary_path(self) -> None:
        for case_id, expected_path in EXPECTED_PRIMARY_PATH.items():
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                self.assertEqual(len(required), 1)
                self.assertEqual(required[0].location["path"], expected_path)

    def test_wrong_anchor_candidates_are_never_the_primary_location(self) -> None:
        for case_id, wrong_paths in WRONG_ANCHOR_CANDIDATES.items():
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                actual_paths = {f.location["path"] for f in required}
                self.assertEqual(
                    actual_paths & wrong_paths,
                    set(),
                    "finding must not anchor at a plausible-but-wrong site",
                )

    def test_out_of_diff_cases_resolve_their_location_outside_the_patch(self) -> None:
        for case_id in OUT_OF_DIFF_LOCATION_CASES:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                patch = case.input["patch"]
                required = [f for f in case.findings if f.required][0]
                path = required.location["path"]
                self.assertNotIn(
                    f"+++ b/{path}",
                    patch,
                    "this case's whole point is a primary location the diff never touches",
                )

    def test_multi_file_case_touches_more_than_its_primary_location(self) -> None:
        # Proves the multi-file case is actually exercising multiple
        # touched files, not degenerating into a single-file case.
        case = self.by_id[MULTI_FILE_PRIMARY]
        patch = case.input["patch"]
        for other_path in WRONG_ANCHOR_CANDIDATES[MULTI_FILE_PRIMARY]:
            with self.subTest(path=other_path):
                self.assertIn(f"+++ b/{other_path}", patch)

    def test_every_case_is_tagged_with_a_known_risk_mode(self) -> None:
        known = {
            "correctness",
            "security",
            "quality",
            "no-op",
            "regression",
            "concurrency",
            "performance",
        }
        for case in self.by_id.values():
            for tag in case.metadata.get("tags", []):
                self.assertIn(tag, known)


class SubCorpusReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_disclaims_duplicating_164s_fixtures(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("does *not* assert", text)
        self.assertIn("#164", text)
        self.assertIn("No #164 fixture is duplicated here", text)


class FindingPlacementCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = MIN_CASES
    max_cases = MAX_CASES
    readme_refs = ("#387",)


if __name__ == "__main__":
    unittest.main()
