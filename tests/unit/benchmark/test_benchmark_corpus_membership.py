#!/usr/bin/env python3
"""Coverage for comprehensive corpus membership derivation (Issue #431).

Proves membership is derived programmatically from `benchmark-case/v2`
fixtures anywhere under a corpus root (never a hard-coded count or list),
sub-corpus directories holding no v2 fixtures contribute nothing, a
duplicate case id across two fixtures is a hard error, and the
`full` -> `sentinel` mode-alias resolution is total and fixed.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.benchmark import benchmark_corpus_membership as membership


def _write(root: Path, relative: str, *, case_id: str | None, fmt: str | None = "benchmark-case/v2") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if fmt is not None:
        lines.append(f"format: {fmt}")
    if case_id is not None:
        lines.append(f"id: {case_id}")
    lines.append("title: x")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class CanonicalLaneTest(unittest.TestCase):
    def test_full_resolves_to_sentinel(self) -> None:
        self.assertEqual(membership.canonical_lane("full"), "sentinel")

    def test_sentinel_and_comprehensive_are_fixed_points(self) -> None:
        self.assertEqual(membership.canonical_lane("sentinel"), "sentinel")
        self.assertEqual(membership.canonical_lane("comprehensive"), "comprehensive")

    def test_unrelated_modes_pass_through_unchanged(self) -> None:
        for mode in ("smoke", "selected", "auth-check"):
            self.assertEqual(membership.canonical_lane(mode), mode)


class DiscoverComprehensiveFixturesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_derives_membership_from_top_level_and_sub_corpus_directories(self) -> None:
        _write(self.root, "top.yaml", case_id="top-1")
        _write(self.root, "sub-a/case-1.yaml", case_id="sub-a-1")
        _write(self.root, "sub-a/case-2.yaml", case_id="sub-a-2")
        _write(self.root, "sub-b/case-1.yaml", case_id="sub-b-1")

        ids = membership.comprehensive_case_ids(self.root)

        self.assertEqual(ids, ["sub-a-1", "sub-a-2", "sub-b-1", "top-1"])

    def test_a_readme_only_test_only_suite_directory_contributes_nothing(self) -> None:
        # Mirrors real sub-corpus directories that hold only a README.md
        # and no benchmark-case/v2 fixtures (e.g. mutation-boundary,
        # reviewer-brief) — excluded by construction, never a denylist.
        (self.root / "test-only-suite").mkdir()
        (self.root / "test-only-suite" / "README.md").write_text("# not a fixture\n", encoding="utf-8")
        _write(self.root, "sentinel-case.yaml", case_id="sentinel-case")

        ids = membership.comprehensive_case_ids(self.root)

        self.assertEqual(ids, ["sentinel-case"])

    def test_ignores_yaml_with_a_different_format(self) -> None:
        _write(self.root, "other.yaml", case_id="other-1", fmt="something-else/v1")
        _write(self.root, "v2.yaml", case_id="v2-1")

        ids = membership.comprehensive_case_ids(self.root)

        self.assertEqual(ids, ["v2-1"])

    def test_ignores_a_fixture_missing_an_id(self) -> None:
        _write(self.root, "no-id.yaml", case_id=None)
        _write(self.root, "has-id.yaml", case_id="has-id")

        ids = membership.comprehensive_case_ids(self.root)

        self.assertEqual(ids, ["has-id"])

    def test_duplicate_case_id_across_fixtures_is_a_hard_error(self) -> None:
        _write(self.root, "a/dup.yaml", case_id="same-id")
        _write(self.root, "b/dup.yaml", case_id="same-id")

        with self.assertRaises(ValueError):
            membership.discover_comprehensive_fixtures(self.root)

    def test_fixture_corpus_dir_points_at_its_own_containing_directory(self) -> None:
        _write(self.root, "sub/nested/case.yaml", case_id="nested-1")

        fixtures = membership.discover_comprehensive_fixtures(self.root)

        self.assertEqual(len(fixtures), 1)
        self.assertEqual(fixtures[0].corpus_dir, self.root / "sub" / "nested")

    def test_real_corpus_tree_matches_the_issues_documented_approximate_count(self) -> None:
        # Sanity check against the real repository corpus tree (Issue #431
        # states "~89" fixtures) — proves this is a live scan, not a stub.
        repo_root = Path(__file__).resolve().parents[3]
        corpus_root = repo_root / "docs" / "benchmark" / "corpus"
        if not corpus_root.exists():
            self.skipTest("real corpus tree not present in this checkout")
        ids = membership.comprehensive_case_ids(corpus_root)
        self.assertGreater(len(ids), 50)
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
