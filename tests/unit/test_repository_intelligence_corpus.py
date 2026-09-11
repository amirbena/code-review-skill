#!/usr/bin/env python3
"""Contract coverage for the repository-intelligence benchmark sub-corpus
(Issue #129).

The sub-corpus is
``docs/benchmark/corpus/repository-intelligence/*.yaml``: a small, focused
set of ``benchmark-case/v1`` fixtures demonstrating relationship-aware
review catching defects a diff-only read of the same patch cannot show, a
safe-failure (ambiguity) case, and a negative/control case proving
retrieval breadth alone is not a finding.

What is proven here:

1. every fixture decodes and validates through the *same* single reference
   validator (``tests/reference/benchmark_fixture.py``) used for the worked
   example and the #51 corpus — this module never defines a second one;
2. the sub-corpus stays small and documented;
3. per **positive** fixture: the relationship-dependent defect's location
   is outside every file the patch itself touches (so a diff-only read of
   the patch cannot show it) and is present in the fixture's expected
   findings (semantic-gain assertion, not a mathematical superset
   requirement — see docs/repository-intelligence/repository-intelligence-model.md
   §10, and the plan wording this mirrors: relationship-aware review may
   refine or replace a weaker diff-only result);
4. the **control** fixture's expected findings equal the diff-only outcome
   (empty) — no added finding, no false positive from retrieval breadth;
5. the **safe-failure** fixture's expected findings are empty;
6. at least two distinct language shapes are represented.

Matching a reviewer's output to these expectations, scoring it, and the
runner are out of scope (Issues #41 / #52 / #54). Relationship-influence
attribution and snapshot-identity/staleness are reference-model concerns
proven in ``tests/unit/test_repository_intelligence.py``, not here — see
the corpus README, "Relationship-influence attribution and staleness are
reference-model concerns."
"""

from __future__ import annotations

import re
import unittest

import yaml

from tests.reference import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus" / "repository-intelligence"

MIN_CASES = 5
MAX_CASES = 10

CALL_SITE_CALLER_NULL_DEREF = "repo-intel-python-call-site-caller-null-deref"
INTERFACE_CONTRACT_IMPLEMENTER_BREAK = (
    "repo-intel-typescript-interface-contract-implementer-break"
)
CONFIG_CONSUMER_STALE_IMPORT = "repo-intel-python-config-consumer-stale-import"
DYNAMIC_DISPATCH_SAFE_FAILURE = "repo-intel-python-dynamic-dispatch-safe-failure"
CONTROL_COMPATIBLE_CALLER = "repo-intel-python-control-compatible-caller-no-finding"

POSITIVE_CASE_IDS = {
    CALL_SITE_CALLER_NULL_DEREF,
    INTERFACE_CONTRACT_IMPLEMENTER_BREAK,
    CONFIG_CONSUMER_STALE_IMPORT,
}
ZERO_FINDING_CASE_IDS = {DYNAMIC_DISPATCH_SAFE_FAILURE, CONTROL_COMPATIBLE_CALLER}

REQUIRED_CASE_IDS = POSITIVE_CASE_IDS | ZERO_FINDING_CASE_IDS

# Language shape carried in the id/title, not in metadata.tags (a closed
# vocabulary with no language values) — see the corpus README.
CASE_LANGUAGE = {
    CALL_SITE_CALLER_NULL_DEREF: "python",
    INTERFACE_CONTRACT_IMPLEMENTER_BREAK: "typescript",
    CONFIG_CONSUMER_STALE_IMPORT: "python",
    DYNAMIC_DISPATCH_SAFE_FAILURE: "python",
    CONTROL_COMPATIBLE_CALLER: "python",
}

_DIFF_GIT_RE = re.compile(r"^diff --git a/(\S+) b/(\S+)$", re.MULTILINE)


def _corpus_files() -> list:
    return sorted(CORPUS_DIR.glob("*.yaml"))


def _load(path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _patch_touched_paths(patch_text: str) -> set:
    touched = set()
    for a_path, b_path in _DIFF_GIT_RE.findall(patch_text):
        touched.add(a_path)
        touched.add(b_path)
    return touched


class SubCorpusPresenceTests(unittest.TestCase):
    def test_directory_exists_with_a_readme(self) -> None:
        self.assertTrue(CORPUS_DIR.is_dir(), f"missing {CORPUS_DIR}")
        self.assertTrue((CORPUS_DIR / "README.md").is_file())

    def test_sub_corpus_is_small(self) -> None:
        n = len(_corpus_files())
        self.assertGreaterEqual(n, MIN_CASES, "a required case went missing")
        self.assertLessEqual(
            n, MAX_CASES, "sub-corpus is growing into a bulk library"
        )


class SubCorpusCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = _corpus_files()
        self.assertTrue(self.files, "no repository-intelligence fixtures found")

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

    def test_patch_case_anchors_occur_in_the_diff_or_base(self) -> None:
        for path in self.files:
            case = bf.parse_case(_load(path))
            if case.input_kind != "patch":
                continue
            patch = case.input["patch"]
            base = case.input.get("base", {})
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

    def test_at_least_two_language_shapes_are_represented(self) -> None:
        languages = {CASE_LANGUAGE[case_id] for case_id in self.by_id}
        self.assertGreaterEqual(
            len(languages), 2, "corpus must cover at least two language shapes"
        )

    def test_every_positive_case_defect_is_outside_the_patch_and_in_expected(
        self,
    ) -> None:
        """Semantic-gain assertion (not a superset requirement): the
        relationship-dependent defect's location is outside every file the
        patch itself touches — a diff-only read of the patch cannot show
        it — and the fixture's (relationship-aware) expected findings
        include exactly the defect this fixture is about."""
        for case_id in POSITIVE_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                touched = _patch_touched_paths(case.input["patch"])
                required = [f for f in case.findings if f.required]
                self.assertGreaterEqual(
                    len(required), 1, "positive case must expect >=1 finding"
                )
                for finding in required:
                    path = finding.location.get("path")
                    self.assertIsNotNone(path)
                    self.assertNotIn(
                        path,
                        touched,
                        "the relationship-dependent defect's location must sit "
                        "outside the patch itself, or a diff-only read would "
                        "already show it",
                    )
                    base = case.input.get("base", {})
                    self.assertIn(
                        path,
                        base,
                        "the defect location must be supplied via input.base "
                        "so relationship-aware retrieval can resolve it",
                    )

    def test_zero_finding_cases_stay_empty_diff_only_and_relationship_aware(
        self,
    ) -> None:
        """Stronger equality assertion for the control and safe-failure
        cases: the relationship-aware expected outcome equals the
        diff-only outcome (both empty) — no added finding, no false
        positive from retrieval breadth or from an unresolved candidate."""
        for case_id in ZERO_FINDING_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(list(case.findings), [])
                self.assertEqual(case.derived_decision, "clean")

    def test_positive_cases_block(self) -> None:
        for case_id in POSITIVE_CASE_IDS:
            with self.subTest(case=case_id):
                self.assertEqual(
                    self.by_id[case_id].derived_decision, "changes-required"
                )


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
        self.assertIn("#129", text)
        self.assertIn("not** packaged", text)

    def test_readme_disclaims_statistical_significance(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("No statistical-significance claim", text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../tests/reference/benchmark_fixture.py)", self.raw
        )
        self.assertIn("never defines a second", self.raw)


if __name__ == "__main__":
    unittest.main()
