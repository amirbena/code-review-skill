#!/usr/bin/env python3
"""Contract coverage for the risk-depth benchmark sub-corpus (Issue #90).

The sub-corpus is ``benchmark/corpus/risk-depth/*.yaml``: a small,
focused set of ``benchmark-case/v2`` fixtures demonstrating that
change-risk-signals.md's catalog signals and diff-size boundary drive
review depth in realistic changes, and that a large multi-area change
retains one finding per area.

What is proven here:

1. every fixture decodes and validates through the *same* single reference
   validator (``runtime_platform/benchmark/reference/benchmark_fixture.py``) used for the
   worked example and the #51 corpus — this module never defines a second
   one;
2. the sub-corpus stays small and documented, and every required case is
   present;
3. every case pins an explicit ``decision`` consistent with its required
   findings;
4. each case's rationale (a specific signal or signal combination) is
   reflected by an equivalent reference-model assertion — the corpus
   fixture pins the expected finding outcome, and this test ties that
   fixture's identity to the depth the same signal shape produces in
   ``tests.reference.change_risk_signals`` (mirroring what
   ``test_repository_intelligence_corpus.py`` does for language shapes);
5. the large-multiarea case's required findings span more than one
   top-level directory, so partitioning-by-directory
   (large-pr-partitioning.md) has more than one area to retain.

Deep depth/expansion/partitioning/coverage *mechanism* assertions — not
tied to a specific corpus fixture — live in
``tests/unit/review/specialist_depth/test_risk_based_review_scenarios.py``. The runner, and
matching a reviewer's output to these expectations, are out of scope here
(Issues #41 / #52 / #54).
"""

from __future__ import annotations

import unittest

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from tests.reference.review import change_risk_signals as crs
from tests.reference.review.change_risk_signals import Depth
from tests.support.corpus_hygiene import (
    CorpusHygieneMixin,
    corpus_files,
    load_fixture,
)
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "risk-depth"

MIN_CASES = 4
MAX_CASES = 10

AUTH_SIGNAL_DEEP = "risk-depth-auth-signal-deep"
CONCURRENCY_SIGNAL_DEEP = "risk-depth-concurrency-signal-deep"
ELEVATED_ESCALATION_DEEP = "risk-depth-elevated-escalation-deep"
DIFFSIZE_ELEVATED_REFACTOR = "risk-depth-diffsize-elevated-refactor"
LARGE_MULTIAREA_PARTITIONING = "risk-depth-large-multiarea-partitioning"

REQUIRED_CASE_IDS = {
    AUTH_SIGNAL_DEEP,
    CONCURRENCY_SIGNAL_DEEP,
    ELEVATED_ESCALATION_DEEP,
    DIFFSIZE_ELEVATED_REFACTOR,
    LARGE_MULTIAREA_PARTITIONING,
}

# Ties each fixture's rationale to the signal shape that produces it,
# fed straight into the same reference model
# tests/unit/review/specialist_depth/test_risk_based_review_scenarios.py exercises directly.
CASE_SIGNAL_FACTS: dict[str, list[crs.ObservedFact]] = {
    AUTH_SIGNAL_DEEP: [crs.ObservedFact("f1", frozenset({"auth"}))],
    CONCURRENCY_SIGNAL_DEEP: [crs.ObservedFact("f1", frozenset({"concurrency"}))],
    ELEVATED_ESCALATION_DEEP: [
        crs.ObservedFact("env-example", frozenset({"sensitive_path"})),
        crs.ObservedFact("ci-workflow", frozenset({"infra_config"})),
    ],
}
CASE_EXPECTED_DEPTH: dict[str, Depth] = {
    AUTH_SIGNAL_DEEP: Depth.DEEP,
    CONCURRENCY_SIGNAL_DEEP: Depth.DEEP,
    ELEVATED_ESCALATION_DEEP: Depth.DEEP,
}

# The diff-size case fires no catalog signal at all; its own patch already
# touches 11 files (>= the 10-file elevated boundary), which alone is
# enough to select `elevated`. `changed_lines=0` isolates the file-count
# boundary specifically, asserted directly rather than duplicating a
# hardcoded fact list -- it does not claim the patch has no line-level
# churn (it does: ~2 changed lines per hunk, independently well under the
# elevated line-count threshold).
DIFFSIZE_CASE_DIFF_SIZE = crs.DiffSize(changed_lines=0, changed_files=11)


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}

    def test_all_required_cases_are_represented(self) -> None:
        missing = REQUIRED_CASE_IDS - set(self.by_id)
        self.assertEqual(missing, set(), f"missing required fixtures: {missing}")

    def test_catalog_signal_cases_select_the_depth_their_rationale_claims(self) -> None:
        for case_id, facts in CASE_SIGNAL_FACTS.items():
            with self.subTest(case=case_id):
                classification = crs.classify(facts)
                self.assertEqual(classification.depth, CASE_EXPECTED_DEPTH[case_id])

    def test_diffsize_case_fires_no_catalog_signal_and_selects_elevated(self) -> None:
        case = self.by_id[DIFFSIZE_ELEVATED_REFACTOR]
        # No catalog signal label applies to this fixture's story -- an
        # empty fact list plus the measured file count is the whole input.
        classification = crs.classify([], DIFFSIZE_CASE_DIFF_SIZE)
        self.assertEqual(classification.depth, Depth.ELEVATED)
        self.assertEqual(classification.occurrences[0].source, "diff-size")
        # The corpus fixture's own patch really does touch >= 10 files.
        touched_files = case.input["patch"].count("diff --git ")
        self.assertGreaterEqual(touched_files, 10)

    def test_every_case_decides_changes_required(self) -> None:
        for case_id, case in self.by_id.items():
            with self.subTest(case=case_id):
                self.assertEqual(case.decision, "changes-required")

    def test_large_multiarea_case_findings_span_more_than_one_directory(self) -> None:
        case = self.by_id[LARGE_MULTIAREA_PARTITIONING]
        required = [f for f in case.findings if f.required]
        self.assertGreaterEqual(len(required), 2)
        top_level_dirs = {f.location["path"].split("/", 1)[0] for f in required}
        self.assertGreaterEqual(
            len(top_level_dirs),
            2,
            "large-multiarea case must expect findings in more than one area, "
            "so directory-based partitioning has more than one area to retain",
        )


class SubCorpusReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_points_to_the_reference_model_scenarios(self) -> None:
        self.assertIn("test_risk_based_review_scenarios.py", self.raw)


class RiskDepthCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = MIN_CASES
    max_cases = MAX_CASES
    readme_refs = ("#90",)
    readme_phrases = ("Intentionally small",)
    validator_phrase = "never defines a second"


if __name__ == "__main__":
    unittest.main()
