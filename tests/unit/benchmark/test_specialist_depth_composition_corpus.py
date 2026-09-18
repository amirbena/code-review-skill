#!/usr/bin/env python3
"""Benchmark-case/v1 fixtures for the Specialist-Depth Composition
sub-corpus (Issue #85, parent #47, grandparent #82).
"""

from __future__ import annotations

import unittest

import yaml

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = (
    REPO_ROOT / "docs" / "benchmark" / "corpus" / "specialist-depth-composition"
)

REQUIRED_CASES = 7

CASE_A = "specialist-depth-composition-case-a-zero-capabilities-base-reasoning-complete"
CASE_B = "specialist-depth-composition-case-b-one-capability-security-confused-deputy"
CASE_C = "specialist-depth-composition-case-c-multiple-capabilities-database-and-performance"
CASE_D = "specialist-depth-composition-case-d-superficial-signal-suppressed-clean"
CASE_E = "specialist-depth-composition-case-e-semantic-evidence-without-expected-file-type"
CASE_F = "specialist-depth-composition-case-f-cascading-activation-bounded"
CASE_G = "specialist-depth-composition-case-g-remediation-scope-unaffected-by-depth"

REQUIRED_CASE_IDS = {CASE_A, CASE_B, CASE_C, CASE_D, CASE_E, CASE_F, CASE_G}
CLEAN_CASE_IDS = {CASE_D}
FLAGGED_CASE_IDS = REQUIRED_CASE_IDS - CLEAN_CASE_IDS

# defect_kinds that are domain-specific-deepening-flavored, i.e. proof a
# capability beyond base reasoning contributed the finding.
DOMAIN_DEFECT_KINDS = {
    CASE_B: {"confused-deputy-unchecked-delegation"},
    CASE_C: {"nullable-to-non-null-missing-backfill", "n-plus-one-remote-call"},
    CASE_E: {"cache-entry-shape-change-missing-coexistence"},
    CASE_F: {
        "index-removal-without-usage-verification",
        "index-removal-induces-table-scan",
    },
    CASE_G: {"blocking-lock-large-table-online-migration"},
}

# Case A's required finding must carry an ordinary base-reasoning defect
# kind, never one that reads as domain-specific-deepening output.
CASE_A_REQUIRED_DEFECT_KIND = "validation-guard-boolean-operator-inverted"


def _corpus_files() -> list:
    return sorted(CORPUS_DIR.glob("*.yaml"))


def _load(path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _required_defect_kinds(case) -> set:
    kinds = set()
    for finding in case.findings:
        if not finding.required:
            continue
        specs = finding.members if finding.is_any_of else [finding]
        for spec in specs:
            if spec.defect_kind:
                kinds.add(spec.defect_kind)
    return kinds


def _optional_defect_kinds(case) -> set:
    kinds = set()
    for finding in case.findings:
        if finding.required:
            continue
        specs = finding.members if finding.is_any_of else [finding]
        for spec in specs:
            if spec.defect_kind:
                kinds.add(spec.defect_kind)
    return kinds


class SubCorpusPresenceTests(unittest.TestCase):
    def test_directory_exists_with_a_readme(self) -> None:
        self.assertTrue(CORPUS_DIR.is_dir(), f"missing {CORPUS_DIR}")
        self.assertTrue((CORPUS_DIR / "README.md").is_file())

    def test_sub_corpus_has_exactly_the_seven_required_cases(self) -> None:
        n = len(_corpus_files())
        self.assertEqual(n, REQUIRED_CASES, "one case per Case A-G composition shape")


class SubCorpusCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = _corpus_files()
        self.assertTrue(self.files, "no specialist-depth-composition fixtures found")

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

    def test_case_d_has_no_findings_at_all(self) -> None:
        case = self.by_id[CASE_D]
        self.assertEqual(list(case.findings), [])
        self.assertEqual(case.decision, "clean")

    def test_flagged_cases_are_all_changes_required(self) -> None:
        for case_id in FLAGGED_CASE_IDS:
            with self.subTest(case=case_id):
                self.assertEqual(self.by_id[case_id].decision, "changes-required")

    def test_case_a_required_finding_carries_no_domain_specific_defect_kind(self) -> None:
        # Case A: zero specialist-depth capabilities engage. The one
        # required finding must be an ordinary base-reasoning defect, not
        # something that reads as a capability's contribution.
        case = self.by_id[CASE_A]
        required_kinds = _required_defect_kinds(case)
        self.assertEqual(required_kinds, {CASE_A_REQUIRED_DEFECT_KIND})
        all_domain_kinds = set().union(*DOMAIN_DEFECT_KINDS.values())
        self.assertEqual(required_kinds & all_domain_kinds, set())

    def test_case_b_engages_exactly_one_capabilitys_defect_kind(self) -> None:
        case = self.by_id[CASE_B]
        self.assertEqual(_required_defect_kinds(case), DOMAIN_DEFECT_KINDS[CASE_B])

    def test_case_c_composes_two_independent_capabilities(self) -> None:
        case = self.by_id[CASE_C]
        required_kinds = _required_defect_kinds(case)
        self.assertEqual(required_kinds, DOMAIN_DEFECT_KINDS[CASE_C])
        self.assertEqual(len(required_kinds), 2)
        required = [f for f in case.findings if f.required]
        self.assertEqual(len(required), 2)

    def test_case_e_engages_with_no_qualifying_file_type_in_patch(self) -> None:
        case = self.by_id[CASE_E]
        self.assertEqual(_required_defect_kinds(case), DOMAIN_DEFECT_KINDS[CASE_E])
        patch = case.input["patch"]
        for qualifying in (".sql", "migrations/", "migration"):
            self.assertNotIn(qualifying, patch)

    def test_case_f_engages_two_findings_via_cascade(self) -> None:
        case = self.by_id[CASE_F]
        required_kinds = _required_defect_kinds(case)
        self.assertEqual(required_kinds, DOMAIN_DEFECT_KINDS[CASE_F])
        # The cascaded finding is expressed cross-file: it is surfaced by
        # tracing usage from the migration, not by an independent change
        # to the file it lands on.
        cross_file_findings = [
            f
            for f in case.findings
            if f.required and f.location.get("location_intent") == "cross-file"
        ]
        self.assertEqual(len(cross_file_findings), 1)

    def test_case_g_required_finding_stays_narrow_broader_observation_optional(self) -> None:
        case = self.by_id[CASE_G]
        required_kinds = _required_defect_kinds(case)
        self.assertEqual(required_kinds, DOMAIN_DEFECT_KINDS[CASE_G])
        required = [f for f in case.findings if f.required]
        self.assertEqual(len(required), 1)
        optional_kinds = _optional_defect_kinds(case)
        self.assertIn("missing-repowide-concurrent-index-lint", optional_kinds)

    def test_no_finding_carries_a_severity_outside_p0_p1_p2(self) -> None:
        for case in self.by_id.values():
            for finding in case.findings:
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    for severity in spec.severities:
                        self.assertIn(severity, {"P0", "P1", "P2"})

    def test_reused_cases_document_their_domain_corpus_provenance(self) -> None:
        # Cases B, D, and G reuse an existing single-domain fixture's
        # scenario verbatim; the rationale must say so rather than
        # silently re-deriving it as if it were new.
        for case_id, issue_ref in (
            (CASE_B, "#271"),
            (CASE_D, "#186"),
            (CASE_G, "#186"),
        ):
            with self.subTest(case=case_id):
                rationale = self.by_id[case_id].metadata.get("rationale", "")
                self.assertIn(issue_ref, rationale)


class SubCorpusReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_links_every_fixture(self) -> None:
        for path in _corpus_files():
            self.assertIn(f"]({path.name})", self.raw, f"README omits {path.name}")

    def test_readme_states_the_selection_principle_and_scope(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("Selection principle", text)
        self.assertIn("#85", text)
        self.assertIn("not** packaged", text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../runtime_platform/benchmark/reference/benchmark_fixture.py)", self.raw
        )
        self.assertIn("never a second one", self.raw)

    def test_readme_names_all_seven_cases(self) -> None:
        for case_id in REQUIRED_CASE_IDS:
            self.assertIn(case_id, self.raw)


if __name__ == "__main__":
    unittest.main()
