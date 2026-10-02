#!/usr/bin/env python3
"""Benchmark-case/v2 fixture for the Scale Progressive-Loading Proof
sub-corpus (Issue #447, parent #403)."""

from __future__ import annotations

import unittest

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from tests.support.corpus_hygiene import (
    CorpusHygieneMixin,
    corpus_files,
    load_fixture,
)
from tests.support.paths import REPO_ROOT

CORPUS_DIR = (
    REPO_ROOT / "benchmark" / "corpus" / "scale-progressive-loading-proof"
)

REQUIRED_CASES = 1

CASE_AMBIGUOUS = (
    "scale-progressive-loading-proof-ambiguous-public-export-forces-"
    "fail-closed-expansion"
)


class SubCorpusCaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.files = corpus_files(CORPUS_DIR)
        self.assertTrue(self.files, "no progressive-loading-proof fixtures found")

    def test_patch_case_applies_cleanly_against_its_base(self) -> None:
        import subprocess
        import tempfile
        from pathlib import Path

        for path in self.files:
            case = bf.parse_case(load_fixture(path))
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


class AmbiguousCaseShapeTests(unittest.TestCase):
    """The distinguishing assertions this corpus exists to pin: a hedged,
    non-blocking required finding -- proof that fail-closed loading
    happened (a finding is produced) without `scale` manufacturing
    confidence the ambiguous trigger evidence does not support."""

    def setUp(self) -> None:
        self.by_id = {p.stem: bf.parse_case(load_fixture(p)) for p in corpus_files(CORPUS_DIR)}
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


class ScaleProgressiveLoadingProofCorpusHygieneTests(CorpusHygieneMixin, unittest.TestCase):
    corpus_dir = CORPUS_DIR
    min_cases = REQUIRED_CASES
    max_cases = REQUIRED_CASES
    readme_refs = ("#447",)
    validator_phrase = None


if __name__ == "__main__":
    unittest.main()
