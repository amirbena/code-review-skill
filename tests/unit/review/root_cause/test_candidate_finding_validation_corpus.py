#!/usr/bin/env python3
"""Contract coverage for the candidate-finding-validation precision
sub-corpus (Issue #383, parent #382/#381).

The sub-corpus is ``docs/benchmark/corpus/candidate-finding-validation/*.yaml``:
a small, focused set of ``benchmark-case/v1`` fixtures that pin the
outcomes ``docs/candidate-finding-validation/candidate-finding-validation-model.md``
names — semantic-role no-inference (§4), unproven-regression
non-assertion (§7), a disconfirmed candidate dropped (§8 ``DROPPED``), a
no-Jira technically-grounded blocking finding (§5 level 4), a valid
defect surviving disconfirmation at a downgraded severity (§8
``DOWNGRADED``), requirement ambiguity never invented as an unsupported
P0/P1 (§5/§9), a candidate re-evaluated under disconfirming precedent
(§8 ``RECLASSIFIED``), a structural inconsistency staying non-blocking
(§9), a concrete invariant violation staying a valid finding with no
requirement behind it (§9 worked example 6), a blast radius narrowed by
bounded evidence (§10), and a real-world-derived scenario proving the
corpus catches a semantic-consistency trap that internally-consistent
docs/tests/implementation can mask (PR #390).

What is proven here:

1. every fixture decodes and validates through the *same* single
   reference validator (``tests/reference/benchmark/benchmark_fixture.py``)
   used for the worked example and every other corpus — this module
   never defines a second one;
2. the sub-corpus stays small and documented — bounded size, filename ==
   case ``id``, a non-empty rationale, tag set, and ``defect_kind`` per
   case, an explicit ``decision`` matching the mechanical derivation,
   and patch anchors that occur in the diff under review;
3. all ten synthetic outcomes plus the real-world scenario are
   represented.

Matching a reviewer's output to these expectations, scoring, and the
runner are out of scope (Issues #41 / #52 / #54).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.reference.benchmark import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus" / "candidate-finding-validation"

# #383 asks for "the smallest representative fixture set" — ten named
# synthetic outcome shapes plus one required real-world scenario. This
# band lets it grow deliberately without becoming a bulk library.
MIN_CASES = 11
MAX_CASES = 16

SEMANTIC_ROLE_NO_INFERENCE = "cfv-semantic-role-no-inference"
UNPROVEN_REGRESSION_NOT_ASSERTED = "cfv-unproven-regression-not-asserted"
DISCONFIRMED_CANDIDATE_DROPPED = "cfv-disconfirmed-severe-candidate-dropped"
NO_JIRA_TOCTOU_BLOCKING = "cfv-no-jira-toctou-still-blocking"
VALID_DEFECT_SEVERITY_DOWNGRADE = "cfv-valid-defect-severity-downgrade"
REQUIREMENT_AMBIGUITY_NOT_INVENTED = "cfv-requirement-ambiguity-not-invented"
DISCONFIRMING_PRECEDENT_REEVALUATED = "cfv-disconfirming-precedent-reevaluated"
STRUCTURAL_INCONSISTENCY_NON_BLOCKING = "cfv-structural-inconsistency-non-blocking"
INVARIANT_VIOLATION_NO_REQUIREMENT_STILL_VALID = "cfv-invariant-violation-no-requirement-still-valid"
NARROWED_BLAST_RADIUS = "cfv-narrowed-blast-radius-bounded-evidence"
REAL_WORLD_PR_390 = "real-world-semantic-consistency-trap-pr-390"

REQUIRED_CASE_IDS = {
    SEMANTIC_ROLE_NO_INFERENCE,
    UNPROVEN_REGRESSION_NOT_ASSERTED,
    DISCONFIRMED_CANDIDATE_DROPPED,
    NO_JIRA_TOCTOU_BLOCKING,
    VALID_DEFECT_SEVERITY_DOWNGRADE,
    REQUIREMENT_AMBIGUITY_NOT_INVENTED,
    DISCONFIRMING_PRECEDENT_REEVALUATED,
    STRUCTURAL_INCONSISTENCY_NON_BLOCKING,
    INVARIANT_VIOLATION_NO_REQUIREMENT_STILL_VALID,
    NARROWED_BLAST_RADIUS,
    REAL_WORLD_PR_390,
}

# Cases whose expected outcome is "no finding at all".
CLEAN_NO_FINDING_CASE_IDS = {
    SEMANTIC_ROLE_NO_INFERENCE,
    UNPROVEN_REGRESSION_NOT_ASSERTED,
    DISCONFIRMED_CANDIDATE_DROPPED,
}

# Cases that must be blocking (>= 1 required P0/P1 finding).
BLOCKING_CASE_IDS = {
    NO_JIRA_TOCTOU_BLOCKING,
    NARROWED_BLAST_RADIUS,
    REAL_WORLD_PR_390,
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
            n, MAX_CASES, "sub-corpus is growing into a bulk library (#383 non-goal)"
        )


class SubCorpusCaseTests(unittest.TestCase):
    """Per-file checks, reported with the file name so a failure points at
    the offending fixture."""

    def setUp(self) -> None:
        self.files = _corpus_files()
        self.assertTrue(self.files, "no candidate-finding-validation fixtures found")

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

    def test_every_required_finding_carries_a_defect_kind(self) -> None:
        for path in self.files:
            case = bf.parse_case(_load(path))
            for finding in case.findings:
                if finding.is_any_of or not finding.required:
                    continue
                with self.subTest(case=path.name, finding=finding.key):
                    self.assertTrue(
                        finding.defect_kind,
                        "each required finding pins a defect_kind so the "
                        "outcome shape it exercises is unambiguous",
                    )

    def test_every_case_pins_an_explicit_consistent_decision(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                self.assertIsNotNone(
                    case.decision, "cases state `decision` as a cross-check"
                )
                self.assertEqual(case.decision, case.derived_decision)

    def test_patch_case_is_a_well_formed_git_apply_compatible_diff(self) -> None:
        """fixture-format.md §6.1: `patch` must be a self-contained unified
        diff, ``git apply``-compatible. A hunk header whose line counts
        don't match its own context/added/removed lines is a corrupt diff
        that ``git apply`` rejects even though it still parses as a plain
        string — this check catches that class of defect, which schema
        validation alone cannot."""
        if shutil.which("git") is None:
            self.skipTest("git not available")
        for path in self.files:
            case = bf.parse_case(_load(path))
            if case.input_kind != "patch":
                continue
            with self.subTest(case=path.name):
                tmp = Path(tempfile.mkdtemp())
                try:
                    for rel, content in case.input.get("base", {}).items():
                        dest = tmp / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_text(content, encoding="utf-8")
                    subprocess.run(["git", "init", "-q"], cwd=tmp, check=True)
                    subprocess.run(["git", "add", "-A"], cwd=tmp, check=True)
                    patch_file = tmp / "___case.patch"
                    patch_file.write_text(case.input["patch"], encoding="utf-8")
                    result = subprocess.run(
                        ["git", "apply", "--check", patch_file.name],
                        cwd=tmp,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(
                        result.returncode,
                        0,
                        f"{path.name}: patch does not apply cleanly onto its "
                        f"own base ({result.stderr.strip()})",
                    )
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)

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

    def test_all_named_outcomes_are_represented(self) -> None:
        missing = REQUIRED_CASE_IDS - set(self.by_id)
        self.assertEqual(missing, set(), f"missing outcome fixtures: {missing}")

    def test_clean_no_finding_cases_expect_zero_findings(self) -> None:
        for case_id in CLEAN_NO_FINDING_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(
                    len(case.findings), 0, f"{case_id} must expect no findings at all"
                )

    def test_blocking_cases_expect_a_required_p0_or_p1_finding(self) -> None:
        for case_id in BLOCKING_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(case.derived_decision, "changes-required")
                blocking = [
                    f
                    for f in case.findings
                    if not f.is_any_of and f.required and f.can_block
                ]
                self.assertGreaterEqual(len(blocking), 1)

    def test_no_jira_toctou_case_carries_no_source_ticket_reference(self) -> None:
        case = self.by_id[NO_JIRA_TOCTOU_BLOCKING]
        source = case.metadata.get("source", "")
        self.assertEqual(
            source,
            "crafted",
            "the no-Jira case must not smuggle in a ticket reference via metadata.source",
        )

    def test_invariant_violation_case_stays_correctness_not_demoted(self) -> None:
        case = self.by_id[INVARIANT_VIOLATION_NO_REQUIREMENT_STILL_VALID]
        required = [f for f in case.findings if not f.is_any_of and f.required]
        self.assertEqual(len(required), 1)
        self.assertEqual(required[0].defect_kind, "toctou-race")
        self.assertFalse(
            required[0].can_block,
            "impact-insufficient defect must be non-blocking, not P0/P1",
        )

    def test_real_world_case_records_pr_390_provenance(self) -> None:
        case = self.by_id[REAL_WORLD_PR_390]
        source = case.metadata.get("source", "")
        self.assertIn("pull/390", source)
        self.assertIn("382", source)

    def test_real_world_case_is_self_contained_patch_input(self) -> None:
        case = self.by_id[REAL_WORLD_PR_390]
        self.assertEqual(
            case.input_kind,
            "patch",
            "the real-world scenario must be a self-contained patch, "
            "never a repo_ref requiring network access",
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
        self.assertIn("#383", text)
        self.assertIn("#382", text)
        self.assertIn("not** packaged", text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../tests/reference/benchmark/benchmark_fixture.py)", self.raw
        )
        text = " ".join(self.raw.split())
        self.assertIn("never defines a second", text)

    def test_readme_records_pr_390_provenance(self) -> None:
        self.assertIn("PR #390", self.raw)
        self.assertIn("3d08fcb", self.raw)


if __name__ == "__main__":
    unittest.main()
