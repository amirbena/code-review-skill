#!/usr/bin/env python3
"""Benchmark-case/v2 fixture for the Scale Progressive-Loading Proof
sub-corpus (Issue #447, parent #403)."""

from __future__ import annotations

import unittest

import yaml

from tests.reference.benchmark import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_DIR = (
    REPO_ROOT / "docs" / "benchmark" / "corpus" / "scale-progressive-loading-proof"
)

REQUIRED_CASES = 1

CASE_AMBIGUOUS = (
    "scale-progressive-loading-proof-ambiguous-public-export-forces-"
    "fail-closed-expansion"
)


def _corpus_files() -> list:
    return sorted(CORPUS_DIR.glob("*.yaml"))


def _load(path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class SubCorpusPresenceTests(unittest.TestCase):
    def test_directory_exists_with_a_readme(self) -> None:
        self.assertTrue(CORPUS_DIR.is_dir(), f"missing {CORPUS_DIR}")
        self.assertTrue((CORPUS_DIR / "README.md").is_file())

    def test_sub_corpus_has_exactly_the_one_required_case(self) -> None:
        n = len(_corpus_files())
        self.assertEqual(
            n, REQUIRED_CASES, "one net-new case; the other two roles are reused by id"
        )


class SubCorpusCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = _corpus_files()
        self.assertTrue(self.files, "no progressive-loading-proof fixtures found")

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

    def test_patch_case_applies_cleanly_against_its_base(self) -> None:
        import subprocess
        import tempfile
        from pathlib import Path

        for path in self.files:
            case = bf.parse_case(_load(path))
            if case.input_kind != "patch":
                continue
            with self.subTest(case=path.name):
                with tempfile.TemporaryDirectory() as tmp:
                    tmp_path = Path(tmp)
                    subprocess.run(
                        ["git", "init", "-q"], cwd=tmp_path, check=True
                    )
                    for rel, content in (case.input.get("base") or {}).items():
                        full = tmp_path / rel
                        full.parent.mkdir(parents=True, exist_ok=True)
                        full.write_text(content, encoding="utf-8")
                    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
                    patch_path = tmp_path / "case.diff"
                    patch_path.write_text(case.input["patch"], encoding="utf-8")
                    result = subprocess.run(
                        ["git", "apply", "--check", "case.diff"],
                        cwd=tmp_path,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(
                        result.returncode,
                        0,
                        f"{path.name}: patch does not apply cleanly: {result.stderr}",
                    )

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


class AmbiguousCaseShapeTests(unittest.TestCase):
    """The distinguishing assertions this corpus exists to pin: a hedged,
    non-blocking required finding -- proof that fail-closed loading
    happened (a finding is produced) without `scale` manufacturing
    confidence the ambiguous trigger evidence does not support."""

    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(_load(p)) for p in _corpus_files()}
        self.assertIn(CASE_AMBIGUOUS, self.by_id)

    def test_decision_is_clean(self) -> None:
        # A P2-inclusive required finding derives `clean` mechanically
        # (severity.md, "Decision derivation") -- the same mechanical
        # outcome as confident non-activation, reached for a different
        # reason (see README).
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
        # escalation the ambiguous trigger evidence does not support) --
        # and, since not every permitted severity blocks, the finding must
        # not force `changes-required` on its own (README).
        self.assertEqual(set(finding.severities), {"P1", "P2"})
        self.assertFalse(finding.can_block)

    def test_finding_is_not_manufactured_from_the_ambiguity_alone(self) -> None:
        # The finding's evidence is the caller-side invariant break
        # (app/checkout/cart.py's minimum-charge assertion), resolved
        # only by expansion -- never the ambiguity of the trigger itself.
        case = self.by_id[CASE_AMBIGUOUS]
        finding = [f for f in case.findings if f.required][0]
        self.assertIn("app/checkout/cart.py", finding.claim)

    def test_taxonomy_reuses_an_existing_capability_value(self) -> None:
        # `scale` has no dedicated taxonomy capability value (#447 is not
        # a taxonomy-widening change); this reuses the closest existing
        # value the two reused repository-intelligence cases already use.
        case = self.by_id[CASE_AMBIGUOUS]
        self.assertEqual(
            case.metadata["taxonomy"]["capability"], ["repository-intelligence"]
        )
        self.assertEqual(
            case.metadata["taxonomy"]["policy_contract"], ["repository-expansion"]
        )


class SubCorpusReadmeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = (CORPUS_DIR / "README.md").read_text(encoding="utf-8")

    def test_readme_links_the_fixture(self) -> None:
        for path in _corpus_files():
            self.assertIn(f"]({path.name})", self.raw, f"README omits {path.name}")

    def test_readme_states_the_selection_principle_and_scope(self) -> None:
        text = " ".join(self.raw.split())
        self.assertIn("Selection principle", text)
        self.assertIn("#447", text)
        self.assertIn("not** packaged", text)

    def test_readme_uses_the_single_reference_validator(self) -> None:
        self.assertIn(
            "](../../../../tests/reference/benchmark/benchmark_fixture.py)", self.raw
        )


if __name__ == "__main__":
    unittest.main()
