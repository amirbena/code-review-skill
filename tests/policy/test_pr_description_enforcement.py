"""Contracts for concise PR policy, template, and Actions enforcement."""

from __future__ import annotations

import re
import unittest

import yaml

from scripts.pr_description_length import PR_BODY_HARD_LIMIT
from tests.support.paths import REPO_ROOT

AGENTS = REPO_ROOT / "AGENTS.md"
POLICY = REPO_ROOT / "policies" / "github-issue-pr-authoring.md"
TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-description-length.yml"


def _load_workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def _on(workflow: dict) -> dict:
    return workflow.get("on", workflow.get(True))


class PolicyLayeringTests(unittest.TestCase):
    def test_agents_routes_thin_invariant_to_canonical_policy(self) -> None:
        agents = AGENTS.read_text(encoding="utf-8")
        self.assertIn("Concise, layered PR descriptions.", agents)
        self.assertIn("](policies/github-issue-pr-authoring.md)", agents)
        self.assertNotIn(str(PR_BODY_HARD_LIMIT), agents)
        self.assertNotIn("pull_request.body", agents)

    def test_policy_owns_concision_and_layering_semantics(self) -> None:
        policy = re.sub(r"\s+", " ", POLICY.read_text(encoding="utf-8"))
        for concept in (
            "concise change summary and navigation surface",
            "do not reproduce Issue acceptance criteria",
            "Detailed findings belong in the review artifact",
            "Detailed design belongs in Issues, docs, policies, or runbooks",
        ):
            self.assertIn(concept, policy)

    def test_policy_evidence_tracks_canonical_limit(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        self.assertIn(f"{PR_BODY_HARD_LIMIT:,}-code-point limit", policy)
        self.assertIn("#148", policy)
        self.assertIn("PR_BODY_HARD_LIMIT", policy)

    def test_structure_and_length_ownership_remain_separate(self) -> None:
        policy = re.sub(r"\s+", " ", POLICY.read_text(encoding="utf-8"))
        self.assertIn(
            "Template structure/completeness and useful-content length are separate contracts",
            policy,
        )
        self.assertIn(
            "must not introduce a second body-measurement implementation",
            policy,
        )


class TemplateTests(unittest.TestCase):
    def test_template_is_lean_and_keeps_traceability(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        headings = re.findall(r"^## (.+)$", template, flags=re.MULTILINE)
        self.assertEqual(headings, ["What", "Validation", "Review"])
        self.assertIn("Fixes #", template)
        self.assertIn("Optional when no review occurred", template)

    def test_template_guidance_uses_excluded_html_comments(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        without_comments = re.sub(r"<!--.*?-->", "", template, flags=re.DOTALL)
        self.assertNotIn("Concisely summarize", without_comments)
        self.assertNotIn("Prefer two to five", without_comments)


class WorkflowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = _load_workflow()
        self.raw = WORKFLOW.read_text(encoding="utf-8")

    def test_runs_for_open_edit_and_new_head(self) -> None:
        pull_request = _on(self.workflow)["pull_request"]
        self.assertEqual(set(pull_request["types"]), {"opened", "edited", "synchronize"})

    def test_uses_minimal_permissions(self) -> None:
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        checkout = self.workflow["jobs"]["validate"]["steps"][0]
        self.assertIs(checkout["with"]["persist-credentials"], False)
        self.assertEqual(checkout["with"]["ref"], "${{ github.event.pull_request.base.sha }}")

    def test_delegates_event_payload_to_canonical_validator(self) -> None:
        run = self.workflow["jobs"]["validate"]["steps"][-1]["run"]
        self.assertIn("scripts/pr_description_length.py", run)
        self.assertIn("$GITHUB_EVENT_PATH", run)
        self.assertNotIn("github.event.pull_request.body", self.raw)
        self.assertNotRegex(self.raw, r"\b6_?000\b")

    def test_workflow_does_not_duplicate_structure_or_counting_logic(self) -> None:
        self.assertNotIn("PULL_REQUEST_TEMPLATE", self.raw)
        self.assertNotIn("wc -", self.raw)
        self.assertNotIn("length(", self.raw)


if __name__ == "__main__":
    unittest.main()
