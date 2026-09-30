#!/usr/bin/env python3
"""Contract: shared/policies/reasoning-checkpoint.md as the single canonical
home of the human reasoning checkpoint (Issue #566, Epic #564).

Prose checks only. Asserts that the semantics live once in the shared policy,
that the shared review-summary template owns only position and shape, that both
delivery templates render the section without restating or forking the
semantics, and that the shared policy stays packaging-independent (it names,
never links, the repository-development design record and never links into a
Skill directory or repository-development policies).
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import LOCAL_RUNBOOK
from tests.support.policy_docs import load_normalized_text as _text


def _plain(phrase: str) -> str:
    """Match ``load_normalized_text``: emphasis and code markup are collapsed."""
    return phrase.replace("**", "").replace("`", "")

POLICY = REPO_ROOT / "shared/policies/reasoning-checkpoint.md"
REVIEW_SUMMARY = REPO_ROOT / "shared/templates/review-summary.md"
REVIEW_CONTEXT = REPO_ROOT / "shared/policies/review-context.md"
REVIEW_SCOPE = REPO_ROOT / "shared/policies/review-scope.md"
LOCAL_TEMPLATE = REPO_ROOT / "skills/local-code-review/templates/local-review-report.md"
GITHUB_TEMPLATE = REPO_ROOT / "skills/github-pr-review/templates/external-review-summary.md"
GITHUB_OUTPUT = REPO_ROOT / "skills/github-pr-review/policies/review-output.md"
GITHUB_BRIEF = REPO_ROOT / "skills/github-pr-review/policies/reviewer-brief.md"
GITHUB_ACTIVE = REPO_ROOT / "skills/github-pr-review/runbooks/active-pr-review.md"
GITHUB_PASSIVE = REPO_ROOT / "skills/github-pr-review/runbooks/passive-pr-review.md"
STRUCTURED_OUTPUT = REPO_ROOT / "shared/policies/structured-output.md"
CAPABILITY = REPO_ROOT / "capabilities/reasoning-checkpoint/capability.yaml"

# Semantics that must be stated in the shared policy and nowhere else.
OWNED_PHRASES = (
    "The reviewer initiates no live-system observability access",
    "Condition R (runtime-dependent)",
    "Prevented by construction",
    "reviewer-inspected",
    "engineer-reported",
    "possible but unavailable",
)


class SharedPolicyOwnsTheContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY)

    def test_activation_facets_and_inert_cases(self) -> None:
        for phrase in (
            "Investigation facet",
            "Design facet",
            "Always inert",
            "There is no invocation option",
            "A bare `fix:` commit prefix",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_bounds_and_fail_closed(self) -> None:
        self.assertIn(_plain("**1–4 numbered questions**"), self.text)
        self.assertIn(_plain("no section"), self.text)
        self.assertIn(_plain('no "insufficient context" placeholder'), self.text)

    def test_access_and_provenance_boundary(self) -> None:
        for phrase in OWNED_PHRASES:
            self.assertIn(_plain(phrase), self.text)
        self.assertIn(_plain("never assumes a permission, invents"), self.text)

    def test_readiness_language(self) -> None:
        for phrase in ("ready to push", "fully verified", "safe to deploy"):
            self.assertIn(_plain(phrase), self.text)
        self.assertIn(_plain("consistent with the evidence reviewed"), self.text)
        self.assertIn(_plain("not a second decision"), self.text)

    def test_explicit_non_effects(self) -> None:
        for phrase in (
            "no severity, finding ID",
            "never an inline comment",
            "does not appear in `structured_review_result`",
            "no question state is persisted",
            "`REVIEW INCOMPLETE`",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_inert_under_incomplete_and_unresolved_jira(self) -> None:
        self.assertIn(_plain("coverage `incomplete`"), self.text)
        self.assertIn(_plain("unresolved supplied Jira reference"), self.text)


class SemanticsAreNotForkedTests(unittest.TestCase):
    def test_owned_phrases_appear_only_in_the_shared_policy(self) -> None:
        for path in (
            REVIEW_SUMMARY,
            LOCAL_TEMPLATE,
            GITHUB_TEMPLATE,
            GITHUB_OUTPUT,
            GITHUB_BRIEF,
            REVIEW_SCOPE,
        ):
            text = _text(path)
            for phrase in OWNED_PHRASES:
                with self.subTest(path=path.name, phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_every_consumer_links_the_shared_policy(self) -> None:
        for path in (
            REVIEW_SUMMARY,
            LOCAL_TEMPLATE,
            GITHUB_TEMPLATE,
            GITHUB_OUTPUT,
            GITHUB_BRIEF,
            REVIEW_SCOPE,
            REVIEW_CONTEXT,
            LOCAL_RUNBOOK,
            GITHUB_ACTIVE,
            GITHUB_PASSIVE,
        ):
            with self.subTest(path=path.name):
                self.assertIn("reasoning-checkpoint.md", _text(path))


class SharedTemplateOwnsPositionAndShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(REVIEW_SUMMARY)

    def test_section_follows_decision_in_the_canonical_shape(self) -> None:
        raw = REVIEW_SUMMARY.read_text(encoding="utf-8")
        decision = raw.index("### Decision\n**<decision label>**")
        checkpoint = raw.index("### Reasoning check", decision)
        self.assertLess(decision, checkpoint)

    def test_placement_before_subordinate_metadata_and_inert_rule(self) -> None:
        self.assertIn(_plain("Immediately after Decision"), self.text)
        self.assertIn(_plain("before the subordinate machine metadata"), self.text)
        self.assertIn(_plain("omitted completely"), self.text)
        self.assertIn(_plain("no placeholder"), self.text)
        self.assertIn(_plain("No consumer may assume Decision is the final element"), self.text)

    def test_opening_assessment_is_scoped_not_replaced(self) -> None:
        self.assertIn(_plain("safe to merge/proceed"), self.text)
        self.assertIn(_plain("Readiness language"), self.text)
        self.assertIn(_plain("no second grade"), self.text)

    def test_human_review_output_renders_the_same_questions(self) -> None:
        self.assertIn(_plain("**reasoning check**"), self.text)
        self.assertIn(_plain("identical to the structured form"), self.text)

    def test_heading_override_invariant_unchanged(self) -> None:
        self.assertIn(_plain("This is the **only** override point"), self.text)


class DeliveryTemplatesRenderTheSectionTests(unittest.TestCase):
    def test_local_template_renders_after_decision_before_metadata(self) -> None:
        raw = LOCAL_TEMPLATE.read_text(encoding="utf-8")
        decision = raw.index("### Decision\n**CHANGES REQUIRED**")
        checkpoint = raw.index("### Reasoning check", decision)
        metadata = raw.index("### Review Metadata", decision)
        self.assertLess(decision, checkpoint)
        self.assertLess(checkpoint, metadata)

    def test_local_template_states_no_delivery_difference(self) -> None:
        text = _text(LOCAL_TEMPLATE)
        self.assertIn(_plain("adds no delivery difference"), text)
        self.assertIn(_plain("not part of the opt-in `structured_review_result`"), text)

    def test_github_template_body_only_never_inline(self) -> None:
        text = _text(GITHUB_TEMPLATE)
        self.assertIn(_plain("always in the review body, never an inline comment"), text)
        self.assertIn(_plain("Reasoning check (conditional)"), text)
        self.assertIn(_plain("The `## Review Summary` heading is unchanged"), text)

    def test_github_template_covers_every_body_form_and_mode(self) -> None:
        section = _text(GITHUB_TEMPLATE)
        start = section.index("## Reasoning check (conditional)")
        block = section[start : section.index("## Stacked-PR context", start)]
        for phrase in (
            "clean",
            "findings",
            "fallback",
            "self-review",
            "`human_review_output`",
            "passive",
            "semi",
            "active",
            "withheld approval",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(_plain(phrase), block)
        self.assertIn("published exactly once", block.lower())

    def test_github_self_review_disclosure_stays_with_decision(self) -> None:
        text = _text(GITHUB_TEMPLATE)
        self.assertIn(_plain("after the closing disclosure line"), text)

    def test_github_review_output_keeps_last_publication_event_invariant(self) -> None:
        text = _text(GITHUB_OUTPUT)
        self.assertIn(_plain("final review comment == last publication event"), text)
        self.assertIn(_plain("never an inline comment"), text)

    def test_reviewer_brief_never_repeats_a_question(self) -> None:
        text = _text(GITHUB_BRIEF)
        self.assertIn(_plain("is never repeated in this brief"), text)


class StructuredResultIsUnchangedTests(unittest.TestCase):
    def test_structured_output_policy_does_not_carry_the_section(self) -> None:
        self.assertNotIn("Reasoning check", _text(STRUCTURED_OUTPUT))
        self.assertNotIn("reasoning-checkpoint", _text(STRUCTURED_OUTPUT))


class ProblemContextLivesInReviewContextTests(unittest.TestCase):
    def test_five_epistemic_classes(self) -> None:
        text = _text(REVIEW_CONTEXT)
        self.assertIn(_plain("Problem context and epistemic classes"), text)
        for tag in ("(reported)", "(hypothesis)", "(reviewed)", "(not available)"):
            self.assertIn(tag, text)
        self.assertIn(_plain("never promotes a class silently"), text)
        self.assertIn(_plain("not a schema, template, or gate"), text)


class PackagingIndependenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = POLICY.read_text(encoding="utf-8")

    def test_only_links_to_other_shared_files(self) -> None:
        targets = re.findall(r"\]\(([^)#]+)", self.raw)
        self.assertTrue(targets)
        for target in targets:
            with self.subTest(target=target):
                resolved = (POLICY.parent / target).resolve()
                self.assertTrue(resolved.is_file(), target)
                self.assertTrue(
                    resolved.is_relative_to(REPO_ROOT / "shared"),
                    f"shared policy links outside shared/: {target}",
                )

    def test_names_but_never_links_the_design_record(self) -> None:
        self.assertIn("Human Reasoning Checkpoint", self.raw)
        self.assertNotIn("docs/", self.raw)
        self.assertNotIn("AGENTS.md", self.raw)

    def test_shared_template_and_context_do_not_link_into_skills_or_docs(self) -> None:
        for path in (REVIEW_SUMMARY, REVIEW_CONTEXT):
            raw = path.read_text(encoding="utf-8")
            self.assertNotRegex(raw, r"\]\([^)]*(skills/|docs/)")

    def test_capability_manifest_is_on_activation_and_covers_both_adapters(self) -> None:
        text = CAPABILITY.read_text(encoding="utf-8")
        self.assertIn(_plain("loads: on-activation"), text)
        self.assertIn(_plain("adapters: [local, github]"), text)
        self.assertIn(_plain("shared/policies/reasoning-checkpoint.md"), text)


if __name__ == "__main__":
    unittest.main()
