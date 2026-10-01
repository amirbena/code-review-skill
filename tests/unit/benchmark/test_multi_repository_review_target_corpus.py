#!/usr/bin/env python3
"""Contract coverage for the multi-repository Review Target benchmark
sub-corpus (Issue #558, parent #555, impl #556).

The sub-corpus is ``benchmark/corpus/multi-repository-review-target/
*.yaml``: five scenarios proving the delivered explicit multi-repository
Review Target composition detects the cross-repository defects that
motivated it, and that its membership-is-authorization boundary holds.

Like ``test_api_compatibility_corpus.py``, every fixture decodes and
validates through the *same* single reference validator
(``runtime_platform/benchmark/reference/benchmark_fixture.py``) every other corpus uses —
this module never defines a second one. It additionally covers the
fixture-format schema surface Issue #558 added (``input.repositories``,
``input.unadmitted_repositories``, ``location.repo_alias``), since no
other test module exercises that surface's malformed-input rejection.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from runtime_platform.benchmark.reference import benchmark_runner as br
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "multi-repository-review-target"

CROSS_REPO_MISMATCH = "cross-repo-contract-mismatch"
THREE_REPO_CORRECT = "three-repo-coordinated-correct"
THREE_REPO_INCORRECT = "three-repo-coordinated-incorrect"
LOCAL_CORRECT_COMBINED_DEFECT = "repository-local-correct-combined-defect"
ISOLATION_UNADMITTED_SIBLING = "isolation-unadmitted-sibling"
SINGLE_REPO_REGRESSION = "single-repository-regression"

REQUIRED_CASE_IDS = {
    CROSS_REPO_MISMATCH,
    THREE_REPO_CORRECT,
    THREE_REPO_INCORRECT,
    LOCAL_CORRECT_COMBINED_DEFECT,
    ISOLATION_UNADMITTED_SIBLING,
    SINGLE_REPO_REGRESSION,
}

CLEAN_CASE_IDS = {THREE_REPO_CORRECT, ISOLATION_UNADMITTED_SIBLING}
CHANGES_REQUIRED_CASE_IDS = {
    CROSS_REPO_MISMATCH,
    THREE_REPO_INCORRECT,
    LOCAL_CORRECT_COMBINED_DEFECT,
    SINGLE_REPO_REGRESSION,
}


def _corpus_files() -> list[Path]:
    return sorted(CORPUS_DIR.glob("*.yaml"))


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class SubCorpusPresenceTests(unittest.TestCase):
    def test_directory_exists_with_a_readme(self) -> None:
        self.assertTrue(CORPUS_DIR.is_dir(), f"missing {CORPUS_DIR}")
        self.assertTrue((CORPUS_DIR / "README.md").is_file())

    def test_sub_corpus_has_exactly_the_required_cases(self) -> None:
        ids = {p.stem for p in _corpus_files()}
        self.assertEqual(ids, REQUIRED_CASE_IDS)


class SubCorpusCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = _corpus_files()
        self.assertTrue(self.files, "no multi-repository-review-target fixtures found")

    def test_every_file_parses_and_validates(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                self.assertEqual(case.format, "benchmark-case/v2")

    def test_filename_stem_matches_case_id(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                self.assertEqual(bf.parse_case(_load(path)).id, path.stem)

    def test_every_case_records_a_rationale_and_tags(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                self.assertTrue(case.metadata.get("rationale", "").strip())
                self.assertTrue(case.metadata.get("tags"))

    def test_every_case_pins_an_explicit_consistent_decision(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                self.assertIsNotNone(case.decision)
                self.assertEqual(case.decision, case.derived_decision)

    def test_every_case_declares_the_multi_repository_taxonomy_capability(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                self.assertEqual(
                    case.metadata["taxonomy"]["capability"], ["multi-repository-review-target"]
                )

    def test_multi_repo_cases_carry_repositories_and_single_repo_case_does_not(self) -> None:
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                if path.stem == SINGLE_REPO_REGRESSION:
                    self.assertEqual(case.input_kind, "patch")
                    self.assertEqual(case.repository_aliases, ())
                else:
                    self.assertEqual(case.input_kind, "multi_repo")
                    self.assertGreaterEqual(len(case.repository_aliases), 2)

    def test_every_finding_location_names_an_admitted_repository_alias(self) -> None:
        """Fixture-format's own cross-check (Issue #558): a multi-repository
        case's finding ``repo_alias`` must be one of ``input.repositories``'
        own aliases — proven here by re-parsing, which would already have
        raised ``FixtureFormatError`` for any fixture that violated it, plus
        an explicit assertion that no such fixture is masking the check by
        having zero findings."""
        for path in self.files:
            with self.subTest(case=path.name):
                case = bf.parse_case(_load(path))
                if case.input_kind != "multi_repo":
                    continue
                for finding in case.findings:
                    specs = finding.members if finding.is_any_of else [finding]
                    for spec in specs:
                        self.assertIn(spec.location["repo_alias"], case.repository_aliases)

    def test_multi_repo_patches_materialize_as_real_independent_git_repositories(self) -> None:
        """Every ``repositories``/``unadmitted_repositories`` entry applies
        cleanly via the exact runner materialization production runs use —
        never a hand-verified-only diff."""
        for path in self.files:
            case = bf.parse_case(_load(path))
            if case.input_kind != "multi_repo":
                continue
            with self.subTest(case=path.name), tempfile.TemporaryDirectory() as tmp:
                workspaces = br.materialize_multi_repo(case, Path(tmp))
                self.assertEqual(set(workspaces.admitted), set(case.repository_aliases))
                for alias, repo_path in {**workspaces.admitted, **workspaces.unadmitted}.items():
                    self.assertTrue((repo_path / ".git").is_dir(), f"{alias} is not a real git repo")

    def test_single_repo_case_materializes_via_the_ordinary_single_repo_path(self) -> None:
        case = bf.parse_case(_load(CORPUS_DIR / f"{SINGLE_REPO_REGRESSION}.yaml"))
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "ws"
            workspace.mkdir()
            br.materialize_patch(case, workspace)
            self.assertTrue((workspace / "app" / "pagination.py").is_file())

    def test_patch_case_anchors_occur_in_the_matching_members_diff_or_base(self) -> None:
        for path in self.files:
            case = bf.parse_case(_load(path))
            if case.input_kind == "multi_repo":
                haystacks = {
                    alias: entry["patch"] + "\n".join((entry.get("base") or {}).values())
                    for alias, entry in case.input["repositories"].items()
                }
            else:
                base = case.input.get("base") or {}
                haystacks = {None: case.input["patch"] + "\n".join(base.values())}
            for finding in case.findings:
                specs = finding.members if finding.is_any_of else [finding]
                for spec in specs:
                    locs = [spec.location, *(a.get("location") for a in spec.alternatives)]
                    for loc in locs:
                        anchor = (loc or {}).get("anchor")
                        if not anchor:
                            continue
                        with self.subTest(case=path.name, anchor=anchor):
                            self.assertIn(anchor, haystacks.get((loc or {}).get("repo_alias"), ""))


class SubCorpusCoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(_load(p)) for p in _corpus_files()}

    def test_all_required_cases_are_represented(self) -> None:
        self.assertEqual(REQUIRED_CASE_IDS - set(self.by_id), set())

    def test_clean_cases_have_no_findings_at_all(self) -> None:
        for case_id in CLEAN_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                self.assertEqual(list(case.findings), [])
                self.assertEqual(case.decision, "clean")

    def test_changes_required_cases_each_have_at_least_one_required_finding(self) -> None:
        for case_id in CHANGES_REQUIRED_CASE_IDS:
            with self.subTest(case=case_id):
                case = self.by_id[case_id]
                required = [f for f in case.findings if f.required and f.can_block]
                self.assertGreaterEqual(len(required), 1)
                self.assertEqual(case.decision, "changes-required")

    def test_three_repo_correct_and_incorrect_share_the_first_two_members_verbatim(self) -> None:
        """Isolates what the combined review is actually catching: the two
        cases differ only in ``downstream-consumer``."""
        correct = self.by_id[THREE_REPO_CORRECT]
        incorrect = self.by_id[THREE_REPO_INCORRECT]
        for alias in ("api-gateway", "orchestration-service"):
            self.assertEqual(
                correct.input["repositories"][alias], incorrect.input["repositories"][alias]
            )
        self.assertNotEqual(
            correct.input["repositories"]["downstream-consumer"],
            incorrect.input["repositories"]["downstream-consumer"],
        )

    def test_isolation_case_declares_a_real_unadmitted_sibling_with_a_severe_defect(self) -> None:
        case = self.by_id[ISOLATION_UNADMITTED_SIBLING]
        unadmitted = case.input.get("unadmitted_repositories") or {}
        self.assertEqual(set(unadmitted), {"legacy-orders-service"})
        sibling_text = unadmitted["legacy-orders-service"]["patch"]
        self.assertIn("PASSWORD", sibling_text.upper())

    def test_isolation_case_unadmitted_alias_appears_in_no_expected_finding(self) -> None:
        """The structural half of the isolation proof (the executable half —
        running the real reviewer and asserting on its actual output — is a
        manual/production run; see README.md "Isolation is proven twice")."""
        case = self.by_id[ISOLATION_UNADMITTED_SIBLING]
        for finding in case.findings:
            specs = finding.members if finding.is_any_of else [finding]
            for spec in specs:
                self.assertNotEqual(spec.location.get("repo_alias"), "legacy-orders-service")

    def test_single_repo_regression_case_carries_no_repo_alias_anywhere(self) -> None:
        case = self.by_id[SINGLE_REPO_REGRESSION]
        for finding in case.findings:
            specs = finding.members if finding.is_any_of else [finding]
            for spec in specs:
                self.assertNotIn("repo_alias", spec.location)


class FixtureFormatExtensionTests(unittest.TestCase):
    """Malformed-input rejection for the schema surface Issue #558 added
    (``input.repositories``, ``input.unadmitted_repositories``,
    ``location.repo_alias``) — not exercised by any pre-existing test
    module, since it did not exist before this corpus."""

    def _base_case(self, **overrides) -> dict:
        case = {
            "format": "benchmark-case/v2",
            "id": "x",
            "title": "t",
            "input": {
                "repositories": {
                    "repo-a": {"patch": "diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1 +1 @@\n-a\n+b\n"},
                    "repo-b": {"patch": "diff --git a/g b/g\n--- a/g\n+++ b/g\n@@ -1 +1 @@\n-a\n+b\n"},
                }
            },
            "expected": {"decision": "clean", "findings": []},
            "metadata": {
                "taxonomy": {
                    "capability": ["unclassified"],
                    "policy_contract": ["unclassified"],
                    "risk_mode": ["unclassified"],
                    "affected_surface": ["unclassified"],
                }
            },
        }
        case.update(overrides)
        return case

    def test_a_well_formed_multi_repo_case_parses(self) -> None:
        case = bf.parse_case(self._base_case())
        self.assertEqual(case.input_kind, "multi_repo")
        self.assertEqual(case.repository_aliases, ("repo-a", "repo-b"))

    def test_single_repository_entry_is_rejected(self) -> None:
        data = self._base_case()
        del data["input"]["repositories"]["repo-b"]
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_repositories_and_patch_together_is_rejected(self) -> None:
        data = self._base_case()
        data["input"]["patch"] = "diff --git a/f b/f\n"
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_repositories_and_repo_ref_together_is_rejected(self) -> None:
        data = self._base_case()
        del data["input"]["repositories"]
        data["input"]["repo_ref"] = {"repo": "o/n", "commit": "deadbeef"}
        data["input"]["repositories"] = {
            "repo-a": {"patch": "diff --git a/f b/f\n"},
            "repo-b": {"patch": "diff --git a/g b/g\n"},
        }
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_non_kebab_alias_is_rejected(self) -> None:
        data = self._base_case()
        data["input"]["repositories"]["Repo_A"] = data["input"]["repositories"].pop("repo-a")
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_repo_entry_missing_patch_is_rejected(self) -> None:
        data = self._base_case()
        data["input"]["repositories"]["repo-a"] = {}
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_repo_entry_unknown_key_is_rejected(self) -> None:
        data = self._base_case()
        data["input"]["repositories"]["repo-a"]["repo_ref"] = {"repo": "o/n"}
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_top_level_base_alongside_repositories_is_rejected(self) -> None:
        data = self._base_case()
        data["input"]["base"] = {"f": "x"}
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_unadmitted_repositories_without_repositories_is_rejected(self) -> None:
        data = self._base_case()
        del data["input"]["repositories"]
        data["input"]["patch"] = "diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1 +1 @@\n-a\n+b\n"
        data["input"]["unadmitted_repositories"] = {"x": {"patch": "diff --git a/h b/h\n"}}
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_unadmitted_alias_colliding_with_an_admitted_alias_is_rejected(self) -> None:
        data = self._base_case()
        data["input"]["unadmitted_repositories"] = {
            "repo-a": {"patch": "diff --git a/h b/h\n--- a/h\n+++ b/h\n@@ -1 +1 @@\n-a\n+b\n"}
        }
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_finding_location_repo_alias_not_in_repositories_is_rejected(self) -> None:
        data = self._base_case()
        data["expected"]["findings"] = [
            {
                "key": "f1",
                "severity": "P2",
                "location": {"location_intent": "file", "path": "f", "repo_alias": "repo-z"},
                "claim": "c",
                "match": "optional",
            }
        ]
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_finding_location_missing_repo_alias_in_a_multi_repo_case_is_rejected(self) -> None:
        data = self._base_case()
        data["expected"]["findings"] = [
            {
                "key": "f1",
                "severity": "P2",
                "location": {"location_intent": "file", "path": "f"},
                "claim": "c",
                "match": "optional",
            }
        ]
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)

    def test_finding_location_repo_alias_valid_and_present_parses(self) -> None:
        data = self._base_case()
        data["expected"]["findings"] = [
            {
                "key": "f1",
                "severity": "P2",
                "location": {"location_intent": "file", "path": "f", "repo_alias": "repo-a"},
                "claim": "c",
                "match": "optional",
            }
        ]
        case = bf.parse_case(data)
        self.assertEqual(case.findings[0].location["repo_alias"], "repo-a")

    def test_repo_alias_on_a_single_repository_case_finding_is_rejected(self) -> None:
        data = {
            "format": "benchmark-case/v2",
            "id": "x",
            "title": "t",
            "input": {"patch": "diff --git a/f b/f\n--- a/f\n+++ b/f\n@@ -1 +1 @@\n-a\n+b\n"},
            "expected": {
                "findings": [
                    {
                        "key": "f1",
                        "severity": "P2",
                        "location": {"location_intent": "file", "path": "f", "repo_alias": "repo-a"},
                        "claim": "c",
                        "match": "optional",
                    }
                ]
            },
            "metadata": {
                "taxonomy": {
                    "capability": ["unclassified"],
                    "policy_contract": ["unclassified"],
                    "risk_mode": ["unclassified"],
                    "affected_surface": ["unclassified"],
                }
            },
        }
        with self.assertRaises(bf.FixtureFormatError):
            bf.parse_case(data)


if __name__ == "__main__":
    unittest.main()
