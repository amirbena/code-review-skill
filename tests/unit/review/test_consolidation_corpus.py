#!/usr/bin/env python3
"""Contract coverage for the root-cause / duplicate consolidation sub-corpus
(Issue #185, parent #177).

The sub-corpus is ``docs/benchmark/corpus/consolidation/*.yaml``: a small,
focused set of ``benchmark-case/v1`` fixtures that pin the consolidation
outcomes #177 names — shared cause consolidates to one authoritative
finding; look-alike but independent defects stay separate; a shared cause
held at low confidence falls back to separate findings; a re-review
reconciles previously separate findings to the consolidated one.

What is proven here:

1. every fixture decodes and validates through the *same* single reference
   validator (``tests/reference/benchmark/benchmark_fixture.py``) used for the worked
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

import yaml

from tests.reference.benchmark import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus" / "consolidation"

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
        self.assertGreaterEqual(n, MIN_CASES, "an outcome case went missing")
        self.assertLessEqual(
            n, MAX_CASES, "sub-corpus is growing into a bulk library (#185 non-goal)"
        )


class SubCorpusCaseTests(unittest.TestCase):
    """Per-file checks, reported with the file name so a failure points at
    the offending fixture."""

    def setUp(self) -> None:
        self.files = _corpus_files()
        self.assertTrue(self.files, "no consolidation fixtures found")

    def test_every_file_decodes_to_a_mapping(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                self.assertIsInstance(_load(path), dict)

    def test_every_file_parses_and_validates(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                self.assertEqual(case.format, "benchmark-case/v1")

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

    def test_patch_case_anchors_occur_in_the_diff_under_review(self) -> None:
        for path in self.files:
            case = bf.parse_case(_load(path))
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
        self.by_id = {p.stem: bf.parse_case(_load(p)) for p in _corpus_files()}

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


class SubCorpusReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_links_every_fixture(self) -> None:
        for path in _corpus_files():
            self.assertIn(f"]({path.name})", self.raw, f"README omits {path.name}")

    def test_readme_states_the_selection_principle_and_scope(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("Selection principle", text)
        self.assertIn("Intentionally small", text)
        self.assertIn("#185", text)
        self.assertIn("#177", text)
        self.assertIn("not** packaged", text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../tests/reference/benchmark/benchmark_fixture.py)", self.raw
        )
        self.assertIn("never defines a second", self.raw)


if __name__ == "__main__":
    unittest.main()
