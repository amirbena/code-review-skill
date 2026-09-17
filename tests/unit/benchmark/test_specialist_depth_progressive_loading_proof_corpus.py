#!/usr/bin/env python3
"""Benchmark-case/v2 fixture for the Specialist-Depth Progressive-Loading
Proof sub-corpus (Issue #411, parent #403)."""

from __future__ import annotations

import unittest

import yaml

from tests.reference.benchmark import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = (
    REPO_ROOT
    / "docs"
    / "benchmark"
    / "corpus"
    / "specialist-depth-progressive-loading-proof"
)

REQUIRED_CASES = 1

CASE_AMBIGUOUS = (
    "specialist-depth-progressive-loading-proof-ambiguous-cardinality-"
    "forces-fail-closed-load"
)


def _corpus_files() -> list:
    return sorted(CORPUS_DIR.glob("*.yaml"))


def _load(path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class SubCorpusPresenceTests(unittest.TestCase):
    def test_directory_exists_with_a_readme(self) -> None:
        self.assertTrue(CORPUS_DIR.is_dir(), f"missing {CORPUS_DIR}")
        self.assertTrue((CORPUS_DIR / "README.md").is_file())

    def test_sub_corpus_has_exactly_the_one_required_case(self) -> None:
        n = len(_corpus_files())
        self.assertEqual(
            n, REQUIRED_CASES, "one net-new case; cases 1/2 are reused by id"
        )


class SubCorpusCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = _corpus_files()
        self.assertTrue(self.files, "no progressive-loading-proof fixtures found")

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


class AmbiguousCaseShapeTests(unittest.TestCase):
    """The distinguishing assertions this corpus exists to pin: a hedged,
    non-blocking required finding — proof that fail-closed loading
    happened (a finding is produced) without specialist-depth
    manufacturing confidence the ambiguous evidence does not support."""

    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(_load(p)) for p in _corpus_files()}
        self.assertIn(CASE_AMBIGUOUS, self.by_id)

    def test_case_id_present(self) -> None:
        self.assertIn(CASE_AMBIGUOUS, self.by_id)

    def test_decision_is_clean(self) -> None:
        # A P2-only required finding derives `clean` mechanically
        # (severity.md, "Decision derivation") -- this is the same
        # mechanical outcome as confident non-activation, reached for a
        # different reason (see README).
        case = self.by_id[CASE_AMBIGUOUS]
        self.assertEqual(case.decision, "clean")

    def test_carries_exactly_one_required_hedged_finding(self) -> None:
        case = self.by_id[CASE_AMBIGUOUS]
        required = [f for f in case.findings if f.required]
        self.assertEqual(len(required), 1)
        finding = required[0]
        self.assertFalse(finding.is_any_of)
        # Severity may range P1-P2 (genuine reviewer judgment under real
        # ambiguity) but never P0 (that would read as confident, evidenced
        # escalation the ambiguous evidence does not support) -- and,
        # since not every permitted severity blocks, the finding must not
        # force `changes-required` on its own (README).
        self.assertEqual(set(finding.severities), {"P1", "P2"})
        self.assertFalse(finding.can_block)

    def test_differs_from_composition_case_d_by_carrying_a_finding(self) -> None:
        # Case D (specialist-depth-composition) is `clean` with *zero*
        # findings: confident non-activation. This case is `clean` with a
        # finding present: ambiguity still loaded the capability.
        case = self.by_id[CASE_AMBIGUOUS]
        self.assertNotEqual(list(case.findings), [])

    def test_carries_an_optional_missing_test_note(self) -> None:
        # Mirrors the convention every reused composition/domain fixture
        # already uses (Case A/B's own optional missing-test entries): an
        # `optional` note so a reviewer that raises it is neither
        # penalized nor required to.
        case = self.by_id[CASE_AMBIGUOUS]
        optional = [f for f in case.findings if not f.required]
        self.assertEqual(len(optional), 1)
        self.assertEqual(optional[0].defect_kind, "missing-test-coverage")


class SubCorpusReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_links_the_fixture(self) -> None:
        for path in _corpus_files():
            self.assertIn(f"]({path.name})", self.raw, f"README omits {path.name}")

    def test_readme_states_the_selection_principle_and_scope(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("Selection principle", text)
        self.assertIn("#411", text)
        self.assertIn("not** packaged", text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../tests/reference/benchmark/benchmark_fixture.py)", self.raw
        )
        self.assertIn("never a second one", self.raw)


if __name__ == "__main__":
    unittest.main()
