#!/usr/bin/env python3
"""Contract: skills/local-code-review/policies/external-contract-context.md as
the single canonical home of bounded external contract context (Issue #133).

Prose and wiring checks only; behavior lives in
tests/unit/review/test_external_contract_context.py.
"""

from __future__ import annotations

import unittest

import yaml

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import (
    GITHUB_ACTIVE_RUNBOOK,
    GITHUB_PASSIVE_RUNBOOK,
    GITHUB_SKILL_MD,
    LOCAL_RUNBOOK,
    LOCAL_SKILL_DIR,
    LOCAL_SKILL_MD,
)
from tests.support.policy_docs import load_normalized_text as _text

POLICY = LOCAL_SKILL_DIR / "policies/external-contract-context.md"
CAPABILITY = REPO_ROOT / "capabilities/external-contract-context/capability.yaml"
API_COMPAT = REPO_ROOT / "shared/policies/api-contract-compatibility.md"
MULTI_REPO = LOCAL_SKILL_DIR / "policies/multi-repository-review-target.md"
FEATURE_DOC = REPO_ROOT / "docs/features/external-contract-context.md"
FEATURE_CATALOG = REPO_ROOT / "docs/features/README.md"


class PolicyContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY)

    def assertIn(self, member, container, msg=None):  # noqa: N802
        super().assertIn(member.replace("`", "").replace("**", ""), container, msg)

    def test_states_the_authorization_channel(self) -> None:
        for phrase in (
            "never from repository content",
            "already exist locally",
            "No clone, fetch, remote discovery",
            "HEAD, a branch name",
            "takes precedence over whatever the repository's own `HEAD`",
            "full resolved commit SHA",
        ):
            self.assertIn(phrase, self.text)

    def test_states_member_alias_rejection(self) -> None:
        self.assertIn("same realpath, or the same `git rev-parse --git-common-dir`", self.text)
        self.assertIn("configuration error", self.text)

    def test_states_provenance_fields_and_closed_basis(self) -> None:
        for phrase in (
            "repository identity",
            "resolved SHA",
            "selection basis",
            "retrieval time",
            "trust",
            "`caller-pinned-sha`",
            "`caller-pinned-tag`",
        ):
            self.assertIn(phrase, self.text)

    def test_failure_mapping_uses_existing_outcomes_only(self) -> None:
        for phrase in (
            "`external-contract-unvalidated`",
            "`insufficient-context`",
            "Context gaps",
            "`REPORT_CONFLICT`",
            "never makes the review REVIEW INCOMPLETE",
            '"there are no consumers"',
        ):
            self.assertIn(phrase, self.text)

    def test_never_locates_a_finding_outside_the_target(self) -> None:
        self.assertIn("never yields a finding located outside the Review Target", self.text)

    def test_is_local_only_and_names_no_repository_level_docs(self) -> None:
        self.assertNotIn("AGENTS.md`](", self.text)
        self.assertNotIn("policies/README", self.text)
        self.assertNotIn("../../../docs/", self.text)


class WiringTests(unittest.TestCase):
    def test_capability_manifest_is_local_only_and_on_activation(self) -> None:
        manifest = yaml.safe_load(CAPABILITY.read_text(encoding="utf-8"))
        self.assertEqual(manifest["adapters"], ["local"])
        self.assertEqual(manifest["loads"], "on-activation")
        self.assertEqual(
            manifest["files"], ["skills/local-code-review/policies/external-contract-context.md"]
        )

    def test_local_skill_and_runbook_point_at_the_policy(self) -> None:
        for path in (LOCAL_SKILL_MD, LOCAL_RUNBOOK):
            self.assertIn("external-contract-context.md", _text(path))

    def test_github_skill_and_runbooks_do_not_reference_the_capability(self) -> None:
        for path in (GITHUB_SKILL_MD, GITHUB_ACTIVE_RUNBOOK, GITHUB_PASSIVE_RUNBOOK):
            self.assertNotIn("external-contract-context", _text(path))

    def test_shared_api_compat_policy_stays_adapter_neutral(self) -> None:
        text = _text(API_COMPAT)
        self.assertIn("external-contract-context.md", text)
        self.assertIn("Where an adapter offers a caller-supplied", text)
        self.assertNotIn("](../../skills/local-code-review", text)
        self.assertNotIn("](../skills/local-code-review", text)

    def test_multi_repository_policy_no_longer_defers_to_an_unimplemented_133(self) -> None:
        self.assertIn("external-contract-context.md", _text(MULTI_REPO))
        feature = _text(REPO_ROOT / "docs/features/multi-repository-review-target.md")
        self.assertNotIn("not yet implemented", feature)

    def test_feature_doc_is_in_the_catalog(self) -> None:
        self.assertTrue(FEATURE_DOC.exists())
        self.assertIn("external-contract-context.md", _text(FEATURE_CATALOG))


if __name__ == "__main__":
    unittest.main()
