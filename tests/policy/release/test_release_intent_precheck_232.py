"""Local, pre-mutation release-intent validation before PR creation/update (#232).

Pins that `policies/github-issue-pr-authoring.md` instructs running the
existing, deterministic `release_worthiness.py assess --require-release-intent`
check locally before `gh pr create` / `gh pr edit`, that the example PR body
includes the release-intent lines, and that AGENTS.md's routing-table row
for the policy still names this step.
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT

AGENTS = REPO_ROOT / "AGENTS.md"
POLICY = REPO_ROOT / "policies" / "github-issue-pr-authoring.md"


class ReleaseIntentPrecheckTests(unittest.TestCase):
    def test_policy_documents_local_preflight_command(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        self.assertIn("scripts/release_worthiness.py assess", policy)
        self.assertIn("--require-release-intent", policy)
        self.assertIn("--pr-body-env", policy)
        self.assertIn("gh pr create", policy)
        self.assertIn("gh pr edit", policy)

    def test_policy_treats_precheck_as_pre_mutation_gate(self) -> None:
        policy = re.sub(r"\s+", " ", POLICY.read_text(encoding="utf-8"))
        self.assertIn(
            "do not open or update the PR on a failing check", policy
        )

    def test_policy_does_not_duplicate_release_intent_validation(self) -> None:
        policy = re.sub(r"\s+", " ", POLICY.read_text(encoding="utf-8"))
        self.assertIn(
            "do not reimplement category validation elsewhere", policy
        )

    def test_example_pr_body_includes_release_intent_lines(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        example = policy.split("### Enforced useful-content limit")[0]
        self.assertIn("Release category: Fixed", example)
        self.assertIn("Release entry:", example)

    def test_agents_routing_row_names_the_precheck(self) -> None:
        agents = AGENTS.read_text(encoding="utf-8")
        self.assertIn(
            "the local release-intent pre-flight check before `gh pr create` / `gh pr edit`",
            agents,
        )
        self.assertIn("](policies/github-issue-pr-authoring.md)", agents)


if __name__ == "__main__":
    unittest.main()
