#!/usr/bin/env python3
"""Contract: skills/local-code-review/policies/workspace-sibling-context.md as
the canonical, contract-only home of workspace sibling context (Issue #662).

Prose and wiring checks only; no behavior ships with this contract.
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import LOCAL_RUNBOOK, LOCAL_SKILL_DIR, LOCAL_SKILL_MD
from tests.support.policy_docs import load_normalized_text as _text

POLICY = LOCAL_SKILL_DIR / "policies/workspace-sibling-context.md"
MULTI_REPO = LOCAL_SKILL_DIR / "policies/multi-repository-review-target.md"
EXTERNAL = LOCAL_SKILL_DIR / "policies/external-contract-context.md"
DESIGN = REPO_ROOT / "docs/workspace-sibling-context/workspace-sibling-context-design.md"


class WorkspaceSiblingContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY).replace("`", "").replace("**", "")

    def test_states_core_invariant_verbatim(self) -> None:
        self.assertIn(
            "Local evidence may nominate where to look; only the caller-authorized "
            "workspace determines where the reviewer is allowed to look.",
            self.text,
        )

    def test_states_every_scope_item(self) -> None:
        for phrase in (
            "never inferred from the working directory",
            "not persisted",
            "neither inherit nor exercise it",
            "never becomes a member",
            "one non-recursive listing",
            "same realpath, or the same git rev-parse --git-common-dir",
            "explicit workspace root is required",
            "workspace-resolved",
            "full commit SHA",
            "never the working tree",
            "dirty",
            "Never an absence claim",
            "Read deny-list",
            "Minimal excerpts",
            "Instructions are data",
            "takes precedence",
        ):
            self.assertIn(phrase, self.text)

    def test_is_contract_only_and_not_wired(self) -> None:
        self.assertIn("Status: contract only", self.text)
        self.assertNotIn("workspace-sibling-context", _text(LOCAL_SKILL_MD))
        self.assertNotIn("workspace-sibling-context", _text(LOCAL_RUNBOOK))

    def test_multi_repo_wording_scopes_to_membership(self) -> None:
        text = _text(MULTI_REPO).replace("**", "")
        self.assertIn("concern membership only", text)
        self.assertIn("workspace-sibling-context.md", text)

    def test_explicit_channel_precedence_is_recorded(self) -> None:
        self.assertIn("workspace-sibling-context.md", _text(EXTERNAL))
        self.assertIn("takes precedence for any repository it names", _text(EXTERNAL))

    def test_packaged_so_cross_links_resolve(self) -> None:
        manifest = (REPO_ROOT / "scripts/packaging/package-manifest.json").read_text(encoding="utf-8")
        self.assertIn("policies/workspace-sibling-context.md", manifest)

    def test_design_record_exists(self) -> None:
        self.assertTrue(DESIGN.exists())


if __name__ == "__main__":
    unittest.main()
