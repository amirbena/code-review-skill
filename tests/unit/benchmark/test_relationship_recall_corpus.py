#!/usr/bin/env python3
"""Relationship-recall sub-corpus and class map (Issue #602, parent #600)."""

from __future__ import annotations

import json
import unittest

import yaml

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT

CORPUS_ROOT = REPO_ROOT / "benchmark" / "corpus"
CORPUS_DIR = CORPUS_ROOT / "relationship-recall"
README = CORPUS_DIR / "README.md"

MIN_CASES = 6
MAX_CASES = 8

# class -> (positive, control, unresolvable), each a (directory, case id).
CLASS_MAP = {
    "consumer": (
        ("repository-intelligence", "repo-intel-python-call-site-caller-null-deref"),
        ("repository-intelligence", "repo-intel-python-control-compatible-caller-no-finding"),
        ("repository-intelligence", "repo-intel-python-dynamic-dispatch-safe-failure"),
    ),
    "affected-test": (
        ("relationship-recall", "relrecall-affected-test-stale-assertion-unlinked-name"),
        ("relationship-recall", "relrecall-affected-test-still-holds-control"),
        ("relationship-recall", "relrecall-affected-test-external-cases-unresolvable"),
    ),
    "interface": (
        ("repository-intelligence", "repo-intel-typescript-interface-contract-implementer-break"),
        ("relationship-recall", "relrecall-interface-optional-member-implementers-compatible-control"),
        ("relationship-recall", "relrecall-interface-config-registered-implementers-unresolvable"),
    ),
    "analogue": (
        ("analogue-placement-pattern", "analogue-placement-status-label-duplication-missing-key"),
        ("analogue-placement-pattern", "analogue-placement-test-file-split-clean"),
        ("relationship-recall", "relrecall-analogue-pattern-source-outside-repository-unresolvable"),
    ),
}


def _load(directory: str, case_id: str) -> bf.BenchmarkCase:
    path = CORPUS_ROOT / directory / f"{case_id}.yaml"
    return bf.parse_case(yaml.safe_load(path.read_text(encoding="utf-8")))


def _required(case: bf.BenchmarkCase) -> list:
    return [f for f in case.findings if f.required]


class SubCorpusTests(unittest.TestCase):
    def test_directory_has_readme_and_bounded_size(self) -> None:
        self.assertTrue(README.is_file())
        n = len(list(CORPUS_DIR.glob("*.yaml")))
        self.assertGreaterEqual(n, MIN_CASES)
        self.assertLessEqual(n, MAX_CASES)

    def test_every_fixture_validates_and_stem_matches_id(self) -> None:
        for path in sorted(CORPUS_DIR.glob("*.yaml")):
            with self.subTest(case=path.name):
                case = bf.parse_case(yaml.safe_load(path.read_text(encoding="utf-8")))
                self.assertEqual(case.id, path.stem)
                self.assertTrue(case.id.startswith("relrecall-"))

    def test_taxonomy_capability_is_relationship_recall(self) -> None:
        for path in sorted(CORPUS_DIR.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(
                data["metadata"]["taxonomy"]["capability"], ["relationship-recall"], path.name
            )


class ClassMapTests(unittest.TestCase):
    def test_positive_requires_a_finding(self) -> None:
        for name, (positive, _, _) in CLASS_MAP.items():
            with self.subTest(cls=name):
                self.assertTrue(_required(_load(*positive)))

    def test_control_and_unresolvable_require_no_finding(self) -> None:
        for name, (_, control, unresolvable) in CLASS_MAP.items():
            for role, ref in (("control", control), ("unresolvable", unresolvable)):
                with self.subTest(cls=name, role=role):
                    case = _load(*ref)
                    self.assertEqual(_required(case), [])
                    self.assertEqual(case.decision, "clean")

    def test_every_mapped_case_is_named_in_the_readme(self) -> None:
        text = README.read_text(encoding="utf-8")
        for refs in CLASS_MAP.values():
            for _, case_id in refs:
                self.assertIn(f"`{case_id}`", text)

    def test_cross_partition_class_records_its_reason(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("Cross-partition: not measurable", text)
        self.assertIn("1200", text)

    def test_readme_scopes_baseline_to_the_pre_601_reviewer(self) -> None:
        text = " ".join(README.read_text(encoding="utf-8").split())
        self.assertIn("**before**", text)
        self.assertIn("#601", text)
        self.assertIn("66ad316", text)


class BaselineRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = json.loads((CORPUS_DIR / "baseline-observations.json").read_text(encoding="utf-8"))
        self.baseline_md = (CORPUS_DIR / "baseline.md").read_text(encoding="utf-8")

    def test_record_covers_exactly_the_six_cases(self) -> None:
        ids = {p.stem for p in CORPUS_DIR.glob("*.yaml")}
        self.assertEqual(set(self.record["cases"]), ids)

    def test_unobserved_case_is_explicit_and_unscored(self) -> None:
        entry = self.record["cases"]["relrecall-analogue-pattern-source-outside-repository-unresolvable"]
        self.assertEqual(entry["observation_status"], "not-observed")
        self.assertIsNone(entry["scoring"])
        self.assertEqual(entry["produced_findings"], [])

    def test_every_other_case_is_observed_and_scored(self) -> None:
        for cid, entry in self.record["cases"].items():
            if entry["observation_status"] == "observed":
                self.assertIsNotNone(entry["scoring"], cid)

    def test_every_case_is_named_in_baseline_md(self) -> None:
        for cid in self.record["cases"]:
            self.assertIn(f"`{cid}`", self.baseline_md)

    def test_baseline_disclaims_statistical_claims(self) -> None:
        self.assertIn("not a statistical sample", " ".join(self.baseline_md.split()))

    def test_recorded_fixture_hashes_cover_every_case(self) -> None:
        hashes = self.record["fixture_sha256"]
        self.assertEqual(set(hashes), set(self.record["cases"]))
        for cid, digest in hashes.items():
            self.assertRegex(digest, r"^[0-9a-f]{64}$", cid)


if __name__ == "__main__":
    unittest.main()
