#!/usr/bin/env python3
"""Contract coverage for the initial benchmark corpus (Issue #51).

The corpus is ``docs/benchmark/corpus/*.yaml``: a small, deliberately
minimal set of ``benchmark-case/v1`` fixtures, one per review category, with
a case-selection rationale recorded in each fixture's ``metadata`` block and
in ``docs/benchmark/corpus/README.md``.

What is proven here:

1. every corpus file decodes and validates through the single reference
   validator (``tests/reference/benchmark_fixture.py``) — the same checker
   used for the worked example; this module never defines a second one;
2. the corpus stays *small* and *documented* — bounded size, filename ==
   case ``id``, a non-empty rationale and tag set per case, and no clash
   with the worked example;
3. the categories #51 calls for — correctness, security, quality, no-op —
   are all present, and each case's declared ``decision`` matches the
   mechanical derivation.

Matching a reviewer's output to these expectations, scoring, and the runner
are out of scope (Issues #41 / #52 / #53).
"""

from __future__ import annotations

import unittest

import yaml

from tests.reference import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus"
EXAMPLE_ID = "example-sqli-and-unsafe-path"

# #51 non-goal: "Hundreds of fixtures." The initial corpus is one case per
# review category; this band lets it grow deliberately without becoming a
# bulk library.
MIN_CASES = 4
MAX_CASES = 12

REQUIRED_CATEGORY_TAGS = {"correctness", "security", "quality", "no-op"}


def _corpus_files() -> list:
    return sorted(CORPUS_DIR.glob("*.yaml"))


def _load(path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class CorpusPresenceTests(unittest.TestCase):
    def test_corpus_directory_exists_with_a_readme(self) -> None:
        self.assertTrue(CORPUS_DIR.is_dir(), f"missing {CORPUS_DIR}")
        self.assertTrue((CORPUS_DIR / "README.md").is_file())

    def test_corpus_is_small(self) -> None:
        n = len(_corpus_files())
        self.assertGreaterEqual(n, MIN_CASES, "corpus lost a category case")
        self.assertLessEqual(
            n, MAX_CASES, "corpus is growing into a bulk library (#51 non-goal)"
        )


class CorpusCaseTests(unittest.TestCase):
    """Per-file checks, reported with the file name so a failure points at
    the offending fixture."""

    def setUp(self) -> None:
        self.files = _corpus_files()
        self.assertTrue(self.files, "no corpus fixtures found")

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

    def test_case_ids_are_unique_and_exclude_the_worked_example(self) -> None:
        ids = [bf.parse_case(_load(p)).id for p in self.files]
        self.assertEqual(len(ids), len(set(ids)), "duplicate case id in corpus")
        self.assertNotIn(
            EXAMPLE_ID, ids, "the worked example is not a corpus case"
        )

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
                    case.decision, "corpus cases state `decision` as a cross-check"
                )
                self.assertEqual(case.decision, case.derived_decision)

    def test_patch_cases_anchor_in_the_diff_under_review(self) -> None:
        for path in self.files:
            case = bf.parse_case(_load(path))
            if case.input_kind != "patch":
                continue
            patch = case.input["patch"]
            for finding in case.findings:
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    for loc in [spec.location, *(a.get("location") for a in spec.alternatives)]:
                        anchor = (loc or {}).get("anchor")
                        if anchor:
                            with self.subTest(case=path.name, anchor=anchor):
                                self.assertIn(anchor, patch)


class CorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = [bf.parse_case(_load(p)) for p in _corpus_files()]

    def test_all_four_review_categories_are_represented(self) -> None:
        tags = set().union(*(set(c.metadata.get("tags", [])) for c in self.cases))
        missing = REQUIRED_CATEGORY_TAGS - tags
        self.assertEqual(missing, set(), f"corpus is missing categories: {missing}")

    def test_corpus_has_a_blocking_case_and_a_clean_case(self) -> None:
        decisions = {c.derived_decision for c in self.cases}
        self.assertIn("changes-required", decisions)
        self.assertIn("clean", decisions)

    def test_corpus_has_an_empty_expectation_no_op_case(self) -> None:
        self.assertTrue(
            any(
                not c.findings and c.findings_completeness == "exhaustive"
                for c in self.cases
            ),
            "a no-op case with an empty exhaustive expectation must exist",
        )


class ReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_links_every_corpus_fixture(self) -> None:
        for path in _corpus_files():
            self.assertIn(f"]({path.name})", self.raw, f"README omits {path.name}")

    def test_readme_states_the_selection_principle_and_non_goals(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("Selection principle", text)
        self.assertIn("Intentionally small", text)
        self.assertIn("#51", text)
        self.assertIn("not** packaged", text)


if __name__ == "__main__":
    unittest.main()
