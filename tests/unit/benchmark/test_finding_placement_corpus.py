#!/usr/bin/env python3
"""Benchmark-case/v2 fixtures for the finding-placement (fix/action
location derivation) sub-corpus (Issue #387, parent #385, implementation
contract #386).
"""

from __future__ import annotations

import unittest

import yaml

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus" / "finding-placement"

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
        self.assertGreaterEqual(n, MIN_CASES, "a required outcome shape went missing")
        self.assertLessEqual(n, MAX_CASES, "sub-corpus is growing into a bulk library")


class SubCorpusCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = _corpus_files()
        self.assertTrue(self.files, "no finding-placement fixtures found")

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

    def test_every_case_is_changes_required(self) -> None:
        # Every scenario in this corpus flags exactly one real, primary
        # defect -- there is no clean/control case here.
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                self.assertEqual(case.decision, "changes-required")

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

    def test_no_finding_carries_a_severity_outside_p0_p1_p2(self) -> None:
        for path in self.files:
            case = bf.parse_case(_load(path))
            for finding in case.findings:
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    for severity in spec.severities:
                        self.assertIn(severity, {"P0", "P1", "P2"})


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(_load(p)) for p in _corpus_files()}

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

    def test_readme_links_every_fixture(self) -> None:
        for path in _corpus_files():
            self.assertIn(f"]({path.name})", self.raw, f"README omits {path.name}")

    def test_readme_states_the_selection_principle_and_scope(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("Selection principle", text)
        self.assertIn("#387", text)
        self.assertIn("not** packaged", text)

    def test_readme_disclaims_duplicating_164s_fixtures(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("does *not* assert", text)
        self.assertIn("#164", text)
        self.assertIn("No #164 fixture is duplicated here", text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../runtime_platform/benchmark/reference/benchmark_fixture.py)", self.raw
        )
        self.assertIn("never a second one", self.raw)


if __name__ == "__main__":
    unittest.main()
