"""The frozen v2 corpus epoch stays separate from the active v3 corpus (Issue #848).

Historical experiments pin the v2 bytes, so the epoch must stay parseable only on an explicit
opt-in and must never leak into the active corpus.
"""

from __future__ import annotations

import unittest

import yaml

from runtime_platform.benchmark.reference import benchmark_fixture as bf
from tests.support.paths import REPO_ROOT, V2_EPOCH_CORPUS_DIR

ACTIVE = REPO_ROOT / "benchmark" / "corpus"
REMOVED_IN_V3 = ("policy-loading", "risk-depth", "reasoning-checkpoint", "delegation-spawn", "reviewer-brief")


def _load(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class FrozenEpochTests(unittest.TestCase):
    def test_every_frozen_fixture_is_v2_and_needs_the_legacy_opt_in(self) -> None:
        paths = sorted(V2_EPOCH_CORPUS_DIR.rglob("*.yaml"))
        self.assertGreater(len(paths), 100)
        for path in paths:
            if path.name == "pre-registration.json":
                continue
            with self.subTest(path=str(path.relative_to(V2_EPOCH_CORPUS_DIR))):
                data = _load(path)
                self.assertEqual(data["format"], "benchmark-case/v2")
                with self.assertRaisesRegex(bf.FixtureFormatError, "unsupported or missing 'format'"):
                    bf.parse_case(data)
                self.assertEqual(bf.parse_case(data, legacy=True).id, data["id"])

    def test_the_legacy_reader_does_not_demand_a_skill_set(self) -> None:
        data = _load(next(iter(sorted(V2_EPOCH_CORPUS_DIR.glob("*.yaml")))))
        self.assertNotIn("skill_set", data["metadata"])
        bf.parse_case(data, legacy=True)

    def test_a_v3_fixture_still_requires_a_skill_set_under_the_legacy_reader(self) -> None:
        data = _load(next(iter(sorted(ACTIVE.glob("*.yaml")))))
        del data["metadata"]["skill_set"]
        with self.assertRaisesRegex(bf.FixtureFormatError, "skill_set"):
            bf.parse_case(data, legacy=True)


class ActiveCorpusTests(unittest.TestCase):
    def test_no_v2_fixture_is_left_in_the_active_corpus(self) -> None:
        stale = [str(p.relative_to(ACTIVE)) for p in ACTIVE.rglob("*.yaml") if _load(p)["format"] != "benchmark-case/v3"]
        self.assertEqual(stale, [])

    def test_every_active_fixture_declares_a_skill_set_that_validates(self) -> None:
        for path in sorted(ACTIVE.rglob("*.yaml")):
            with self.subTest(path=str(path.relative_to(ACTIVE))):
                skills = bf.parse_case(_load(path)).metadata["skill_set"]
                self.assertEqual(skills[0], "review-core")

    def test_removed_sub_corpora_are_gone_from_active_but_kept_frozen(self) -> None:
        for name in REMOVED_IN_V3:
            with self.subTest(sub_corpus=name):
                self.assertFalse((ACTIVE / name).exists())
                self.assertTrue((V2_EPOCH_CORPUS_DIR / name).is_dir())


if __name__ == "__main__":
    unittest.main()
