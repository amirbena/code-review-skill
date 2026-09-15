"""Contracts for concise PR policy, template, and Actions enforcement."""

from __future__ import annotations

import re
import unittest

import yaml

from scripts.validation import pr_description_length as pr_length
from scripts.validation.pr_description_length import PR_BODY_HARD_LIMIT
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


class CanonicalTemplateAuthoringContractTests(unittest.TestCase):
    """Pins the #278 authoring contract: agent-authored PRs must start from
    .github/PULL_REQUEST_TEMPLATE.md, not an "equivalent prose" substitute."""

    def test_agents_states_the_canonical_template_invariant(self) -> None:
        agents = AGENTS.read_text(encoding="utf-8")
        self.assertIn("Agent-authored PRs use the canonical PR template.", agents)
        self.assertIn("`.github/PULL_REQUEST_TEMPLATE.md`", agents)
        self.assertIn("](policies/github-issue-pr-authoring.md)", agents)

    def test_policy_requires_starting_from_the_template(self) -> None:
        policy = re.sub(r"\s+", " ", POLICY.read_text(encoding="utf-8"))
        self.assertIn("### Start from the canonical PR template", policy)
        self.assertIn(
            "fills its intended fields and sections with real content, and removes or "
            "replaces every placeholder and HTML-comment guidance block",
            policy,
        )
        self.assertIn("never invents an independent PR-body structure", policy)

    def test_byte_for_byte_loophole_wording_is_gone(self) -> None:
        policy = POLICY.read_text(encoding="utf-8")
        self.assertNotIn("byte for byte", policy)
        self.assertNotIn("equivalent concise prose", policy)


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


class TemplateStructureDriftTests(unittest.TestCase):
    """Pins Issue #135: required structure must stay derived from, and in
    sync with, the canonical .github/PULL_REQUEST_TEMPLATE.md — not a
    second, hand-maintained schema."""

    def test_derived_contract_matches_the_live_template_headings(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        headings = re.findall(r"^## (.+)$", template, flags=re.MULTILINE)
        contract = pr_length.load_template_contract()
        self.assertEqual(set(contract.required_headings) | set(contract.optional_headings), set(headings))

    def test_review_stays_the_only_template_declared_optional_heading(self) -> None:
        # If the template's optionality wording moves, this drifts loudly
        # rather than silently under- or over-enforcing.
        contract = pr_length.load_template_contract()
        self.assertEqual(contract.optional_headings, ("Review",))

    def test_release_fields_stay_owned_by_release_intent_not_this_validator(self) -> None:
        template = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("**Release category:** none", template)
        self.assertIn("**Release entry:**", template)
        contract = pr_length.load_template_contract()
        required_labels = {label for _, label in contract.required_blank_fields}
        self.assertNotIn("Release category", required_labels)
        self.assertNotIn("Release entry", required_labels)

    def test_compliant_sample_pr_body_passes_derived_structure_validation(self) -> None:
        from tests.support.pr_body_fixtures import COMPLIANT_BODY

        result = pr_length.validate_structure(COMPLIANT_BODY)
        self.assertTrue(result.passes, result.issues)


class WorkflowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = _load_workflow()
        self.raw = WORKFLOW.read_text(encoding="utf-8")

    def test_runs_for_open_edit_and_new_head(self) -> None:
        pull_request = _on(self.workflow)["pull_request"]
        self.assertEqual(set(pull_request["types"]), {"opened", "edited", "synchronize"})

    def test_uses_minimal_permissions(self) -> None:
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        steps = self.workflow["jobs"]["validate"]["steps"]
        checkouts = [step for step in steps if str(step.get("uses", "")).startswith("actions/checkout")]
        self.assertEqual(len(checkouts), 2)
        self.assertEqual(checkouts[0]["with"]["ref"], "${{ github.event.pull_request.base.sha }}")
        self.assertEqual(checkouts[1]["with"]["ref"], "${{ github.event.pull_request.head.sha }}")
        self.assertIn("hashFiles('scripts/validation/pr_description_length.py') == ''", checkouts[1]["if"])
        for checkout in checkouts:
            self.assertIs(checkout["with"]["persist-credentials"], False)

    def test_delegates_event_payload_to_canonical_validator(self) -> None:
        run = self.workflow["jobs"]["validate"]["steps"][-1]["run"]
        self.assertIn("scripts/validation/pr_description_length.py", run)
        self.assertIn("$GITHUB_EVENT_PATH", run)
        self.assertNotIn("github.event.pull_request.body", self.raw)
        self.assertNotRegex(self.raw, r"\b6_?000\b")

    def test_workflow_does_not_duplicate_structure_or_counting_logic(self) -> None:
        self.assertNotIn("PULL_REQUEST_TEMPLATE", self.raw)
        self.assertNotIn("wc -", self.raw)
        self.assertNotIn("length(", self.raw)


if __name__ == "__main__":
    unittest.main()
