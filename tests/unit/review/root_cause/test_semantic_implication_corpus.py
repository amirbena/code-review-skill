#!/usr/bin/env python3
"""Contract coverage for the semantic-implication benchmark sub-corpus
(Issue #211).

The sub-corpus is ``docs/benchmark/corpus/semantic-implication/*.yaml``: a
small, focused set of ``benchmark-case/v2`` fixtures demonstrating
shared/policies/review-scope.md's "Semantic change-implication reasoning"
base pass — a single dimension activating alone, one change materially
implicating several dimensions at once, a change with no material signal
for any dimension, and a dimension whose signal fires but for which
available evidence cannot support a finding.

Unlike ``test_risk_depth_corpus.py``, this module pairs with no
deterministic reference model: "Semantic change-implication reasoning" is
a judgment-based pass with no mechanical classification function, exactly
like "Architectural placement and execution-lifecycle fidelity" (#153)
before it, which also ships with no reference-model scenarios file. What
is proven here is structural: every fixture decodes and validates through
the *same* single reference validator
(``runtime_platform/benchmark/reference/benchmark_fixture.py``) used for the worked
example and every other corpus — this module never defines a second one.
"""

from __future__ import annotations

import unittest

import yaml

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus" / "semantic-implication"

MIN_CASES = 4
MAX_CASES = 10

SINGLE_DIMENSION_PERSISTENCE = "semantic-implication-single-dimension-persistence"
MULTI_DIMENSION_WEBHOOK_XSS = "semantic-implication-multi-dimension-webhook-xss"
NO_SIGNAL_CLEAN_EXTRACTION = "semantic-implication-no-signal-clean-extraction"
INSUFFICIENT_EVIDENCE_STOP = "semantic-implication-insufficient-evidence-stop"

REQUIRED_CASE_IDS = {
    SINGLE_DIMENSION_PERSISTENCE,
    MULTI_DIMENSION_WEBHOOK_XSS,
    NO_SIGNAL_CLEAN_EXTRACTION,
    INSUFFICIENT_EVIDENCE_STOP,
}

CLEAN_CASE_IDS = {NO_SIGNAL_CLEAN_EXTRACTION, INSUFFICIENT_EVIDENCE_STOP}


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
        self.assertTrue(self.files, "no semantic-implication fixtures found")

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

    def test_single_dimension_case_has_exactly_one_required_finding(self) -> None:
        case = self.by_id[SINGLE_DIMENSION_PERSISTENCE]
        required = [f for f in case.findings if f.required]
        self.assertEqual(len(required), 1)
        self.assertEqual(case.decision, "changes-required")

    def test_multi_dimension_case_stays_one_root_cause_finding(self) -> None:
        # F1: the point of the multi-dimension case is that several
        # dimensions are implicated by one change, never that each
        # implicated dimension must produce its own finding.
        case = self.by_id[MULTI_DIMENSION_WEBHOOK_XSS]
        required = [f for f in case.findings if f.required]
        self.assertEqual(len(required), 1)
        self.assertEqual(case.decision, "changes-required")

    def test_clean_cases_have_no_findings_at_all(self) -> None:
        for case_id in CLEAN_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(list(case.findings), [])
                self.assertEqual(case.decision, "clean")

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
        self.assertIn("#211", text)
        self.assertIn("not** packaged", text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../runtime_platform/benchmark/reference/benchmark_fixture.py)", self.raw
        )
        self.assertIn("never defines a second", self.raw)

    def test_readme_explains_why_there_is_no_reference_model_file(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("No reference-model scenario file", text)
        self.assertIn("judgment-based reasoning pass", text)
        self.assertIn("#153", text)


if __name__ == "__main__":
    unittest.main()
