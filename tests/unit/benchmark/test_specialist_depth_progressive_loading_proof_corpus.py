#!/usr/bin/env python3
"""Benchmark-case/v2 fixture for the Specialist-Depth Progressive-Loading
Proof sub-corpus (Issue #411, parent #403)."""

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
    / "specialist-depth-progressive-loading-proof"
)

REQUIRED_CASES = 1

CASE_AMBIGUOUS = (
    "specialist-depth-progressive-loading-proof-ambiguous-cardinality-"
    "forces-fail-closed-load"
)


class AmbiguousCaseShapeTests(unittest.TestCase):
    """The distinguishing assertions this corpus exists to pin: a hedged,
    non-blocking required finding — proof that fail-closed loading
    happened (a finding is produced) without specialist-depth
    manufacturing confidence the ambiguous evidence does not support."""

    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}
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


class SpecialistDepthProgressiveLoadingProofCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = REQUIRED_CASES
    max_cases = REQUIRED_CASES
    readme_refs = ("#411",)


if __name__ == "__main__":
    unittest.main()
