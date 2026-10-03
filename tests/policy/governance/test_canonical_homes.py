#!/usr/bin/env python3
"""Blocking canonical-home registry guard (issue #80): each registered
anchor lives in its owner and nowhere else unless allowlisted with a
vocabulary reason, and no file is claimed by two capability manifests.
"""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from runtime_platform.benchmark.reference.reasoning_checkpoint_fixtures import SCOPED_OPENING_ASSESSMENT
from scripts.governance.canonical_homes import (
    GROUPS,
    anchors_in_group,
    capability_double_claims,
    load_registry,
    normalize,
    violations,
)
from tests.support.paths import REPO_ROOT

ANCHOR_TEXT = "Exactly one rule owns this sentence."


def _registry(**anchor_overrides) -> dict:
    anchor = {
        "id": "t:one",
        "group": "exact-string",
        "text": ANCHOR_TEXT,
        "owner": "owner.md",
        "scope": ["*"],
        "allow": [],
    }
    anchor.update(anchor_overrides)
    return {"reasons": {"design-record-mirror": "mirror"}, "anchors": [anchor]}


class RealTreeTests(unittest.TestCase):
    def test_registry_is_clean(self) -> None:
        self.assertEqual(violations(load_registry(), REPO_ROOT), [])

    def test_registry_covers_every_group(self) -> None:
        registry = load_registry()
        for group in GROUPS:
            self.assertTrue(anchors_in_group(registry, group), group)

    def test_no_file_is_claimed_by_two_capabilities(self) -> None:
        self.assertEqual(capability_double_claims(REPO_ROOT), {})

    def test_reasoning_checkpoint_fixture_matches_the_registered_wording(self) -> None:
        registered = {a["text"] for a in load_registry()["anchors"] if a["group"] == "exact-string"}
        self.assertIn(normalize(SCOPED_OPENING_ASSESSMENT), {normalize(t) for t in registered})


class SeededTreeTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.write("owner.md", f"# Owner\n\n> {ANCHOR_TEXT}\n")

    def write(self, rel: str, body: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def test_owner_only_passes(self) -> None:
        self.assertEqual(violations(_registry(), self.root), [])

    def test_restatement_outside_owner_fails(self) -> None:
        self.write("docs/copy.md", f"Intro\n\n**{ANCHOR_TEXT}**\n")
        self.assertTrue(any("restated outside its owner" in p for p in violations(_registry(), self.root)))

    def test_allowlisted_restatement_passes(self) -> None:
        self.write("docs/copy.md", ANCHOR_TEXT)
        allow = [{"path": "docs/copy.md", "reason": "design-record-mirror"}]
        self.assertEqual(violations(_registry(allow=allow), self.root), [])

    def test_unknown_reason_fails(self) -> None:
        self.write("docs/copy.md", ANCHOR_TEXT)
        allow = [{"path": "docs/copy.md", "reason": "because"}]
        self.assertTrue(any("unknown reason" in p for p in violations(_registry(allow=allow), self.root)))

    def test_stale_allowlist_entry_fails(self) -> None:
        self.write("docs/copy.md", "reworded")
        allow = [{"path": "docs/copy.md", "reason": "design-record-mirror"}]
        self.assertTrue(any("stale allowlist" in p for p in violations(_registry(allow=allow), self.root)))

    def test_owner_losing_the_anchor_fails(self) -> None:
        self.write("owner.md", "reworded")
        self.assertTrue(any("owner owner.md does not contain" in p for p in violations(_registry(), self.root)))

    def test_scope_limits_the_search(self) -> None:
        self.write("docs/copy.md", ANCHOR_TEXT)
        self.assertEqual(violations(_registry(scope=["AGENTS.md"]), self.root), [])

    def test_tests_directory_is_not_scanned(self) -> None:
        self.write("tests/fixture.md", ANCHOR_TEXT)
        self.assertEqual(violations(_registry(), self.root), [])

    def test_capability_double_claim_fails(self) -> None:
        for name in ("a", "b"):
            self.write(f"capabilities/{name}/capability.yaml", "files:\n  - shared/x.md\n")
        self.write("capabilities/c/capability.yaml", "files:\n  - shared/y.md\n")
        self.assertEqual(capability_double_claims(self.root), {"shared/x.md": ["a", "b"]})

    def test_registry_is_not_mutated(self) -> None:
        registry = _registry()
        before = copy.deepcopy(registry)
        violations(registry, self.root)
        self.assertEqual(registry, before)


if __name__ == "__main__":
    unittest.main()
