#!/usr/bin/env python3
"""Contract: shared/policies/workspace-sibling-context.md as
the canonical shared contract for workspace sibling context (Issues #662, #663).

Prose and wiring checks only; behavior lives in
tests/unit/review/test_workspace_sibling_context.py.
"""

from __future__ import annotations

import json
import unittest

import yaml

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import (
    GITHUB_PASSIVE_RUNBOOK,
    GITHUB_SKILL_MD,
    LOCAL_RUNBOOK,
    LOCAL_SKILL_DIR,
    LOCAL_SKILL_MD,
)
from tests.support.policy_docs import load_normalized_text as _text

POLICY = REPO_ROOT / "shared/policies/workspace-sibling-context.md"
MULTI_REPO = LOCAL_SKILL_DIR / "policies/multi-repository-review-target.md"
EXTERNAL = LOCAL_SKILL_DIR / "policies/external-contract-context.md"
LOCAL_POLICY = LOCAL_SKILL_DIR / "policies/workspace-sibling-context.md"
GITHUB_POLICY = REPO_ROOT / "skills/github-pr-review/policies/workspace-sibling-context.md"
CAPABILITY = REPO_ROOT / "capabilities/workspace-sibling-context/capability.yaml"
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
            "Adapter applicability",
            "local filesystem access to the granted root",
            "PR's own repository identity",
            "reference-only provenance",
            "conclusion plus a reference",
            "never\n  sibling file content or excerpts".replace("\n  ", " "),
        ):
            self.assertIn(phrase, self.text)

    def test_is_active_and_conditionally_loaded(self) -> None:
        self.assertIn("Status: active, conditionally loaded", self.text)
        self.assertIn("Activation and resolution order", self.text)
        self.assertIn("before recording a Context gap", self.text)
        cap = yaml.safe_load(CAPABILITY.read_text(encoding="utf-8"))
        self.assertEqual(cap["adapters"], ["local", "github"])
        self.assertEqual(cap["loads"], "on-activation")
        self.assertEqual(
            sorted(cap["files"]),
            sorted([
                "shared/policies/workspace-sibling-context.md",
                "skills/local-code-review/policies/workspace-sibling-context.md",
                "skills/github-pr-review/policies/workspace-sibling-context.md",
            ]),
        )

    def test_both_adapters_wire_thin_policies_and_inputs(self) -> None:
        for skill_md, policy in ((LOCAL_SKILL_MD, LOCAL_POLICY), (GITHUB_SKILL_MD, GITHUB_POLICY)):
            self.assertIn("policies/workspace-sibling-context.md", _text(skill_md))
            self.assertIn("workspace root", _text(skill_md))
            self.assertIn("shared/policies/workspace-sibling-context.md", _text(policy))
            self.assertLess(len(_text(policy).split()), 450)
        self.assertIn("workspace-sibling-context.md", _text(LOCAL_RUNBOOK))
        self.assertIn("workspace-sibling-context.md", _text(GITHUB_PASSIVE_RUNBOOK))

    def test_github_adapter_rules(self) -> None:
        text = _text(GITHUB_POLICY).replace("**", "").replace("`", "")
        for phrase in (
            "local filesystem access to the granted root",
            "API-only mode",
            "PR's own repository by identity",
            "no grant",
            "reference-only provenance",
            "never sibling file content or excerpts",
        ):
            self.assertIn(phrase, text)

    def test_provenance_is_wired_into_the_finding_template(self) -> None:
        text = _text(REPO_ROOT / "shared/templates/finding.md")
        for phrase in ("Workspace sibling provenance", "workspace-resolved", "workspace-granted-read-only"):
            self.assertIn(phrase, text)

    def test_packaged_in_both_archives_with_no_core_entry(self) -> None:
        manifest = json.loads((REPO_ROOT / "scripts/packaging/package-manifest.json").read_text(encoding="utf-8"))
        shared = {f["source"] for f in manifest["shared_files"]}
        self.assertIn("shared/policies/workspace-sibling-context.md", shared)
        local = {f["source"] for f in manifest["skills"]["local"]["files"]}
        github = {f["source"] for f in manifest["skills"]["github"]["files"]}
        self.assertIn("skills/local-code-review/policies/workspace-sibling-context.md", local)
        self.assertIn("skills/github-pr-review/policies/workspace-sibling-context.md", github)

    def test_multi_repo_wording_scopes_to_membership(self) -> None:
        text = _text(MULTI_REPO).replace("**", "")
        self.assertIn("concern membership only", text)
        self.assertIn("workspace-sibling-context.md", text)

    def test_explicit_channel_precedence_is_recorded(self) -> None:
        self.assertIn("workspace-sibling-context.md", _text(EXTERNAL))
        self.assertIn("takes precedence for any repository it names", _text(EXTERNAL))

    def test_github_adapter_has_no_remote_access_dependency(self) -> None:
        self.assertIn("not a dependency on #645", self.text)
        self.assertNotIn("until a separate GitHub-mode contract", self.text)
        self.assertNotIn("cannot perform this read", self.text)

    def test_design_record_exists(self) -> None:
        self.assertTrue(DESIGN.exists())


if __name__ == "__main__":
    unittest.main()
