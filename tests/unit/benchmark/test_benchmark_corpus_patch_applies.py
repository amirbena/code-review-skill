#!/usr/bin/env python3
"""Every patch-bearing comprehensive fixture applies to its own base (Issue #541).

The runner fails closed with ``patch-did-not-apply`` when a fixture's
``input.patch`` does not apply to the tree built from its ``input.base``.
This sweep materializes each fixture exactly as the runner does, so hunk-header
or context drift fails in CI rather than in a scheduled Comprehensive run.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from runtime_platform.benchmark.reference import benchmark_runner as runner
from runtime_platform.benchmark.scripts import benchmark_corpus_membership as membership
from tests.support.paths import REPO_ROOT

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus"


def _patch_fixtures() -> list[Path]:
    paths = []
    for fixture in membership.discover_comprehensive_fixtures(CORPUS_DIR):
        data = yaml.safe_load(fixture.fixture_path.read_text(encoding="utf-8"))
        if "patch" in (data.get("input") or {}):
            paths.append(fixture.fixture_path)
    return sorted(paths)


class CorpusPatchAppliesTest(unittest.TestCase):
    def test_patch_bearing_fixtures_exist(self) -> None:
        self.assertTrue(_patch_fixtures())

    def test_every_patch_applies_to_its_own_base(self) -> None:
        failures = []
        for path in _patch_fixtures():
            case = bf.parse_case(yaml.safe_load(path.read_text(encoding="utf-8")))
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    runner.materialize_patch(case, Path(tmp))
                except runner.PatchDidNotApply as exc:
                    failures.append(f"{path.relative_to(CORPUS_DIR)}: {exc}")
        self.assertEqual([], failures, "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
