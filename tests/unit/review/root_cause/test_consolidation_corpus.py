#!/usr/bin/env python3
"""Contract coverage for the root-cause / duplicate consolidation sub-corpus
(Issue #185, parent #177).

The sub-corpus is ``benchmark/corpus/consolidation/*.yaml``: a small,
focused set of ``benchmark-case/v2`` fixtures that pin the consolidation
outcomes #177 names — shared cause consolidates to one authoritative
finding; look-alike but independent defects stay separate; a shared cause
held at low confidence falls back to separate findings; a re-review
reconciles previously separate findings to the consolidated one.

What is proven here:

1. every fixture decodes and validates through the *same* single reference
   validator (``runtime_platform/benchmark/reference/benchmark_fixture.py``) used for the worked
   example and the #51 corpus — this module never defines a second one;
2. the sub-corpus stays small and documented — bounded size, filename ==
   case ``id``, a non-empty rationale and tag set per case, an explicit
   ``decision`` matching the mechanical derivation, and patch anchors that
   occur in the diff under review;
3. all four #185 outcomes are represented, including the re-review case,
   which carries its prior-review evidence in ``input.context``.

Matching a reviewer's output to these expectations, scoring, and the runner
are out of scope (Issues #41 / #52 / #54).
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

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "consolidation"

# #185 asks for "a focused, representative set only" — the four named
# outcomes. This band lets it grow deliberately without becoming a bulk
# library.
MIN_CASES = 4
MAX_CASES = 10

# The four outcomes #185 enumerates, keyed by case id.
SHARED_CAUSE_CONSOLIDATES = "consolidation-shared-validator-many-call-paths"
INDEPENDENT_STAY_SEPARATE = "consolidation-similar-but-independent-defects"
LOW_CONFIDENCE_FALLBACK = "consolidation-shared-cause-low-confidence-fallback"
REREVIEW_RECONCILES = "consolidation-rereview-reconciles-to-authoritative"

REQUIRED_CASE_IDS = {
    SHARED_CAUSE_CONSOLIDATES,
    INDEPENDENT_STAY_SEPARATE,
    LOW_CONFIDENCE_FALLBACK,
    REREVIEW_RECONCILES,
}


class SubCorpusCaseTests(unittest.TestCase):
    """Per-file checks, reported with the file name so a failure points at
    the offending fixture."""

    def setUp(self) -> None:
        self.files = corpus_files(CORPUS_DIR)
        self.assertTrue(self.files, "no consolidation fixtures found")

    def test_every_file_decodes_to_a_mapping(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                self.assertIsInstance(load_fixture(path), dict)

    def test_patch_case_anchors_occur_in_the_diff_under_review(self) -> None:
        for path in self.files:
            case = bf.parse_case(load_fixture(path))
            if case.input_kind != "patch":
                continue
            patch = case.input["patch"]
            for finding in case.findings:
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    locs = [spec.location, *(a.get("location") for a in spec.alternatives)]
                    for loc in locs:
                        anchor = (loc or {}).get("anchor")
                        if anchor:
                            with self.subTest(case=path.name, anchor=anchor):
                                self.assertIn(anchor, patch)


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_all_four_named_outcomes_are_represented(self) -> None:
        missing = REQUIRED_CASE_IDS - set(self.by_id)
        self.assertEqual(missing, set(), f"missing outcome fixtures: {missing}")

    def test_shared_cause_case_expects_a_single_authoritative_finding(self) -> None:
        case = self.by_id[SHARED_CAUSE_CONSOLIDATES]
        required = [f for f in case.findings if f.required]
        self.assertEqual(
            len(required), 1, "shared-cause case must expect exactly one authoritative finding"
        )
        self.assertEqual(required[0].location.get("location_intent"), "cross-file")

    def test_independent_case_expects_multiple_separate_findings(self) -> None:
        case = self.by_id[INDEPENDENT_STAY_SEPARATE]
        required = [f for f in case.findings if f.required]
        self.assertGreaterEqual(
            len(required), 2, "look-alike-but-independent case must stay separate findings"
        )

    def test_low_confidence_fallback_case_expects_separate_findings(self) -> None:
        case = self.by_id[LOW_CONFIDENCE_FALLBACK]
        required = [f for f in case.findings if f.required]
        self.assertGreaterEqual(
            len(required), 2, "low-confidence shared cause must fall back to separate findings"
        )

    def test_rereview_case_carries_prior_review_evidence_and_one_finding(self) -> None:
        case = self.by_id[REREVIEW_RECONCILES]
        context = case.input.get("context", "")
        self.assertTrue(
            isinstance(context, str) and "re-review" in context.lower(),
            "the re-review case must supply prior-review evidence via input.context",
        )
        required = [f for f in case.findings if f.required]
        self.assertEqual(
            len(required), 1, "the re-review must reconcile to one authoritative finding"
        )

    def test_every_case_blocks(self) -> None:
        for case_id, case in self.by_id.items():
            with self.subTest(case=case_id):
                self.assertEqual(case.derived_decision, "changes-required")


class ConsolidationCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = MIN_CASES
    max_cases = MAX_CASES
    readme_refs = ("#185", "#177")
    readme_phrases = ("Intentionally small",)
    validator_phrase = "never defines a second"
    size_hint = "(#185 non-goal)"


if __name__ == "__main__":
    unittest.main()
