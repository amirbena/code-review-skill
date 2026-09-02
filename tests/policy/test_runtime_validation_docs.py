#!/usr/bin/env python3
"""Pins the shared runtime-validation contract and its wiring (#138)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT


POLICY = REPO_ROOT / "shared/policies/runtime-validation.md"
SUMMARY = REPO_ROOT / "shared/templates/review-summary.md"
LOCAL_SKILL = REPO_ROOT / "skills/local-code-review/SKILL.md"
GITHUB_SKILL = REPO_ROOT / "skills/github-pr-review/SKILL.md"
LOCAL_RUNBOOK = REPO_ROOT / "skills/local-code-review/runbooks/local-review.md"
ACTIVE_RUNBOOK = REPO_ROOT / "skills/github-pr-review/runbooks/active-pr-review.md"
PASSIVE_RUNBOOK = REPO_ROOT / "skills/github-pr-review/runbooks/passive-pr-review.md"
CHECKOUT = REPO_ROOT / "skills/github-pr-review/policies/repository-checkout.md"


def normalized(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").replace("**", "").replace("`", ""))


class CanonicalPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = normalized(POLICY)

    def test_policy_has_one_canonical_home_and_flow_boundary(self) -> None:
        for phrase in (
            "Applies identically to local-code-review and github-pr-review",
            "There is no new command-discovery mechanism here",
            "Reuse the target repository instruction hierarchy",
            "Use the blast-radius guidance in [review-scope.md](review-scope.md)",
            "This policy does not authorize autofixes",
            "After target-repository instruction discovery",
        ):
            self.assertIn(phrase, self.text)

    def test_command_source_and_selection_contract(self) -> None:
        for phrase in (
            "exact command, its source location",
            "no declared command",
            "narrowest declared command",
            "broader command only when",
            "Do not automatically add commands",
            "do not run a command merely to learn whether it is safe",
        ):
            self.assertIn(phrase, self.text)

    def test_safety_contract_covers_mutation_secrets_services_and_network(self) -> None:
        for phrase in (
            "must not edit source files",
            "create or alter Git state",
            "call GitHub write APIs",
            "secret, credential, approval, external service, network access",
            "network access",
            "destructive or side-effecting",
            "may write caches or artifacts in the target tree",
            "shell evaluation of untrusted text",
        ):
            self.assertIn(phrase, self.text)

    def test_outcome_and_decision_contract_is_explicit(self) -> None:
        for outcome in ("executed", "failed", "skipped", "unavailable"):
            self.assertIn(f"`{outcome}`", POLICY.read_text(encoding="utf-8"))
        for phrase in (
            "one visible outcome record",
            "non-execution outcome as passing",
            "never removes, suppresses, downgrades",
            "classify its severity from impact",
            "derive the existing review decision exactly once",
            "cannot create a second decision path",
        ):
            self.assertIn(phrase, self.text)


class WiringTests(unittest.TestCase):
    def test_both_entrypoints_reference_shared_policy(self) -> None:
        for path in (LOCAL_SKILL, GITHUB_SKILL):
            self.assertIn("shared/policies/runtime-validation.md", normalized(path))

    def test_all_runbooks_reference_shared_policy(self) -> None:
        for path in (LOCAL_RUNBOOK, ACTIVE_RUNBOOK, PASSIVE_RUNBOOK):
            self.assertIn("runtime-validation.md", normalized(path))

    def test_checkout_carve_out_is_narrow_and_policy_bound(self) -> None:
        text = normalized(CHECKOUT)
        self.assertIn("runtime-validation.md", text)
        self.assertIn("exact declared command", text)
        self.assertNotIn("tests/builds/linters — those remain future work", text)

    def test_summary_validation_contract_uses_the_four_outcomes(self) -> None:
        text = normalized(SUMMARY)
        for outcome in ("executed", "skipped", "failed", "unavailable"):
            self.assertIn(outcome, text)
        self.assertIn("non-execution is never a pass", text)
        self.assertIn("runtime-validation.md", text)

    def test_runbooks_only_orchestrate_and_do_not_define_a_second_outcome_set(self) -> None:
        for path in (LOCAL_RUNBOOK, ACTIVE_RUNBOOK, PASSIVE_RUNBOOK):
            text = normalized(path)
            self.assertIn("carry", text)
            self.assertNotIn("exit code 0 means", text)
            self.assertNotIn("retry the validation", text.lower())


if __name__ == "__main__":
    unittest.main()
