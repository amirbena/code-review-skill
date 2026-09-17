#!/usr/bin/env python3
"""Contract coverage for the null-like absence-risk benchmark sub-corpus
(Issue #121).

The sub-corpus is ``docs/benchmark/corpus/null-absence-risk/*.yaml``: a
small, focused set of ``benchmark-case/v2`` fixtures demonstrating
shared/policies/review-scope.md's "Null-like absence-risk review"
requirement — a real null/undefined/nil dereference risk surfaced, its
directly guarded counterpart correctly not reported, an optional/lookup-
result path with unchecked absence surfaced, JavaScript/TypeScript
undefined/null property access, and a null-safe-language interoperability
edge case (a Kotlin platform type from Java interop).

Like ``test_semantic_implication_corpus.py``, every fixture decodes and
validates through the *same* single reference validator
(``tests/reference/benchmark/benchmark_fixture.py``) used for every other
corpus — this module never defines a second one.
"""

from __future__ import annotations

import unittest

import yaml

from tests.reference.benchmark import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus" / "null-absence-risk"

MIN_CASES = 6
MAX_CASES = 10

JAVA_UNGUARDED = "null-absence-java-unguarded-dereference"
JAVA_GUARDED_CLEAN = "null-absence-java-guarded-clean"
GO_UNCHECKED_LOOKUP = "null-absence-go-unchecked-map-lookup"
TS_OPTIONAL_PROPERTY = "null-absence-typescript-optional-property-access"
KOTLIN_JAVA_PLATFORM_TYPE = "null-absence-kotlin-java-platform-type"
JAVA_GUARDED_AND_UNGUARDED_COMBINED = "null-absence-java-guarded-and-unguarded-combined"

REQUIRED_CASE_IDS = {
    JAVA_UNGUARDED,
    JAVA_GUARDED_CLEAN,
    GO_UNCHECKED_LOOKUP,
    TS_OPTIONAL_PROPERTY,
    KOTLIN_JAVA_PLATFORM_TYPE,
    JAVA_GUARDED_AND_UNGUARDED_COMBINED,
}

CLEAN_CASE_IDS = {JAVA_GUARDED_CLEAN}


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
        self.assertTrue(self.files, "no null-absence-risk fixtures found")

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

    def test_unguarded_case_has_exactly_one_required_finding(self) -> None:
        case = self.by_id[JAVA_UNGUARDED]
        required = [f for f in case.findings if f.required]
        self.assertEqual(len(required), 1)
        self.assertEqual(case.decision, "changes-required")

    def test_guarded_counterpart_has_no_findings_at_all(self) -> None:
        case = self.by_id[JAVA_GUARDED_CLEAN]
        self.assertEqual(list(case.findings), [])
        self.assertEqual(case.decision, "clean")

    def test_guarded_pair_shares_the_same_nullable_source_and_call_site(self) -> None:
        # The pair's point is that reachability, not declared type, decides
        # the outcome — so both cases must share the same nullable
        # repository contract and the same call site shape.
        unguarded = self.by_id[JAVA_UNGUARDED]
        guarded = self.by_id[JAVA_GUARDED_CLEAN]
        for case in (unguarded, guarded):
            self.assertIn(
                "src/main/java/app/user/UserRepository.java", case.input["base"]
            )
        self.assertIn("user.getEmail()", unguarded.input["patch"])
        self.assertIn("user.getEmail()", guarded.input["patch"])

    def test_lookup_and_ts_and_interop_cases_each_have_one_required_finding(
        self,
    ) -> None:
        for case_id in (GO_UNCHECKED_LOOKUP, TS_OPTIONAL_PROPERTY, KOTLIN_JAVA_PLATFORM_TYPE):
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required]
                self.assertEqual(len(required), 1)
                self.assertEqual(case.decision, "changes-required")

    def test_combined_case_has_the_literal_same_fixture_spot_check(self) -> None:
        # Issue #121's Validation section: "a guarded value and an
        # unguarded value in the same fixture produce exactly one
        # finding." This case is the literal, single-diff demonstration —
        # not a matched pair across two files.
        case = self.by_id[JAVA_GUARDED_AND_UNGUARDED_COMBINED]
        required = [f for f in case.findings if f.required]
        self.assertEqual(len(required), 1)
        self.assertEqual(case.decision, "changes-required")
        patch = case.input["patch"]
        self.assertIn("confirm(long orderId)", patch)
        self.assertIn("confirmSafely(long orderId)", patch)
        finding = required[0]
        self.assertEqual(finding.location["symbol"], "confirm")
        self.assertNotEqual(finding.location["symbol"], "confirmSafely")

    def test_cases_span_at_least_three_language_families(self) -> None:
        # Validation requirement: at least Java/Kotlin, JavaScript/TypeScript,
        # and one of C#/Python/Go.
        java_kotlin = {JAVA_UNGUARDED, JAVA_GUARDED_CLEAN, KOTLIN_JAVA_PLATFORM_TYPE}
        js_ts = {TS_OPTIONAL_PROPERTY}
        other = {GO_UNCHECKED_LOOKUP}
        self.assertTrue(java_kotlin & set(self.by_id))
        self.assertTrue(js_ts & set(self.by_id))
        self.assertTrue(other & set(self.by_id))

    def test_at_least_one_case_is_changes_required_and_one_is_clean(self) -> None:
        decisions = {case.decision for case in self.by_id.values()}
        self.assertIn("changes-required", decisions)
        self.assertIn("clean", decisions)

    def test_no_finding_carries_a_severity_outside_p0_p1_p2(self) -> None:
        # No-new-severity acceptance criterion: every expected finding in
        # this sub-corpus uses the existing closed severity set.
        for case in self.by_id.values():
            for finding in case.findings:
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    for severity in spec.severities:
                        self.assertIn(severity, {"P0", "P1", "P2"})


class SubCorpusReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_links_every_fixture(self) -> None:
        for path in _corpus_files():
            self.assertIn(f"]({path.name})", self.raw, f"README omits {path.name}")

    def test_readme_states_the_selection_principle_and_scope(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("Selection principle", text)
        self.assertIn("#121", text)
        self.assertIn("not** packaged", text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../tests/reference/benchmark/benchmark_fixture.py)", self.raw
        )
        self.assertIn("never defines a second", self.raw)


if __name__ == "__main__":
    unittest.main()
