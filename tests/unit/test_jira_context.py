#!/usr/bin/env python3
"""Jira context-resolution coverage: jira_context.py tables plus prose checks.

Contract: shared/policies/review-context.md, "Jira context resolution".
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.reference import jira_context as jc
from tests.support.paths import REPO_ROOT

SHARED_CONTEXT = REPO_ROOT / "shared/policies/review-context.md"
LOCAL = REPO_ROOT / "skills/local-code-review"
GITHUB = REPO_ROOT / "skills/github-pr-review"


def _text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class NoJiraUnchangedTests(unittest.TestCase):
    def test_not_supplied_is_a_normal_review(self) -> None:
        self.assertEqual(
            jc.resolve_jira_scope_outcome(jc.JiraResolutionStatus.NOT_SUPPLIED),
            jc.JiraScopeOutcome.NORMAL_REVIEW_NO_JIRA,
        )

    def test_policy_states_jira_is_never_mandatory(self) -> None:
        t = _text(SHARED_CONTEXT)
        self.assertIn("It never makes Jira required for reviews that do not supply one", t)
        self.assertIn("This does not make Jira mandatory for ordinary reviews", t)


RUNBOOKS = (
    LOCAL / "runbooks/local-review.md",
    GITHUB / "runbooks/active-pr-review.md",
    GITHUB / "runbooks/passive-pr-review.md",
)

#: A phrase that only appears once the review reasoning proper begins, per
#: runbook. Jira resolution wording must appear strictly before it.
REVIEW_STEP_MARKER = {
    LOCAL / "runbooks/local-review.md": "Review the complete delta against",
    GITHUB / "runbooks/active-pr-review.md": "Review per",
    GITHUB / "runbooks/passive-pr-review.md": "Review the diff against",
}


class ResolutionRequiredTests(unittest.TestCase):
    def test_reference_must_be_resolved_before_use(self) -> None:
        t = _text(SHARED_CONTEXT)
        self.assertIn("Before it can inform review reasoning it must be resolved", t)
        self.assertIn("A reference is never treated as if the identifier itself carried", t)

    def test_resolved_status_yields_jira_scoped_review(self) -> None:
        self.assertEqual(
            jc.resolve_jira_scope_outcome(jc.JiraResolutionStatus.RESOLVED),
            jc.JiraScopeOutcome.REVIEW_WITH_JIRA_CONTEXT,
        )


class OperationalProcedureTests(unittest.TestCase):
    """The Skills must tell the Agent *how* to act, not just that resolution
    is required."""

    def test_module_defines_the_five_ordered_steps(self) -> None:
        self.assertEqual(
            jc.RESOLUTION_PROCEDURE_STEPS,
            (
                "identify_available_jira_integration",
                "invoke_read_only_fetch_issue",
                "fetch_relevant_comments_and_linked_context",
                "normalize_into_review_context",
                "continue_only_on_success",
            ),
        )

    def test_procedure_is_usable_only_when_every_step_ran(self) -> None:
        self.assertTrue(jc.procedure_completed(frozenset(jc.RESOLUTION_PROCEDURE_STEPS)))
        self.assertFalse(
            jc.procedure_completed(
                frozenset(jc.RESOLUTION_PROCEDURE_STEPS) - {"invoke_read_only_fetch_issue"}
            )
        )

    def test_comment_retrieval_is_an_explicit_step(self) -> None:
        self.assertTrue(jc.comment_retrieval_is_part_of_the_procedure())

    def test_shared_policy_has_a_numbered_resolution_procedure(self) -> None:
        raw = SHARED_CONTEXT.read_text(encoding="utf-8")
        self.assertIn("### Resolution procedure", raw)
        t = _text(SHARED_CONTEXT)
        # each operational step is present as an ordered instruction
        self.assertIn("1. Identify an available Jira-capable integration", t)
        self.assertIn("2. Invoke it in read-only mode", t)
        self.assertIn("3. Retrieve relevant comments and linked requirement context", t)
        self.assertIn("4. Normalize", t)
        self.assertIn("5. Continue only after successful resolution", t)

    def test_every_runbook_names_the_operational_steps(self) -> None:
        for rb in RUNBOOKS:
            t = _text(rb)
            with self.subTest(runbook=rb.name):
                self.assertIn("Resolution procedure", t)
                self.assertIn("identify an available Jira MCP / connector", t)
                self.assertIn("invoke it", t.lower())
                self.assertIn("read-only", t)
                self.assertIn("fetch the referenced issue's contents", t)
                self.assertIn(
                    "fetch relevant issue comments and linked requirement context", t
                )
                self.assertIn("continue only after successful resolution", t)

    def test_jira_resolution_precedes_the_review_step_in_every_runbook(self) -> None:
        for rb in RUNBOOKS:
            raw = rb.read_text(encoding="utf-8")
            jira_at = raw.find("Jira MCP")
            review_at = raw.find(REVIEW_STEP_MARKER[rb])
            with self.subTest(runbook=rb.name):
                self.assertGreater(jira_at, -1)
                self.assertGreater(review_at, -1)
                self.assertLess(
                    jira_at, review_at,
                    f"{rb.name}: Jira resolution wording appears after the review step",
                )


class NormalizedFieldsTests(unittest.TestCase):
    def test_acceptance_criteria_constraints_non_goals_are_normalized(self) -> None:
        for field in ("acceptance_criteria", "constraints", "explicit_non_goals",
                      "settled_decisions", "relevant_comments"):
            self.assertIsNotNone(jc.normalize_field(field))

    def test_unknown_field_is_not_carried_into_review_context(self) -> None:
        self.assertIsNone(jc.normalize_field("reporter_avatar_url"))
        self.assertIsNone(jc.normalize_field("raw_payload"))

    def test_policy_lists_the_retrieval_fields_and_forbids_raw_payload(self) -> None:
        t = _text(SHARED_CONTEXT)
        for field in ("issue key", "summary", "description", "issue type",
                      "acceptance criteria", "components", "labels",
                      "parent/epic", "linked issues", "explicit non-goals",
                      "constraints", "settled decisions"):
            self.assertIn(field, t)
        self.assertIn("Do not inject the entire raw Jira payload into review reasoning", t)


class JiraCommentClassificationTests(unittest.TestCase):
    def test_settled_clarification_with_pass_fail_becomes_criterion(self) -> None:
        c = jc.JiraComment(jc.JiraCommentClass.SETTLED_CLARIFICATION,
                           states_pass_fail_condition=True)
        self.assertTrue(jc.promote_comment_to_acceptance_criterion(c))

    def test_speculative_suggestion_is_never_promoted(self) -> None:
        c = jc.JiraComment(jc.JiraCommentClass.SPECULATIVE_SUGGESTION,
                           states_pass_fail_condition=True)
        self.assertFalse(jc.promote_comment_to_acceptance_criterion(c))

    def test_rejected_and_open_and_superseded_are_never_promoted(self) -> None:
        for kind in (jc.JiraCommentClass.REJECTED_APPROACH,
                     jc.JiraCommentClass.UNRESOLVED_QUESTION,
                     jc.JiraCommentClass.IMPLEMENTATION_NOTE):
            c = jc.JiraComment(kind, states_pass_fail_condition=True)
            self.assertFalse(jc.promote_comment_to_acceptance_criterion(c))
        superseded = jc.JiraComment(jc.JiraCommentClass.ACCEPTED_DECISION,
                                    states_pass_fail_condition=True,
                                    superseded_by_later_comment=True)
        self.assertFalse(jc.promote_comment_to_acceptance_criterion(superseded))

    def test_newer_maintainer_clarification_beats_stale_speculation(self) -> None:
        self.assertEqual(
            jc.prefer_newer_maintainer_clarification(
                newer_is_explicit_maintainer_clarification=True,
                older_is_speculative=True,
            ),
            "newer",
        )

    def test_policy_classifies_comments_and_warns_against_over_promotion(self) -> None:
        t = _text(SHARED_CONTEXT)
        for cls in ("settled clarification", "accepted decision", "implementation note",
                    "unresolved question", "speculative suggestion", "rejected approach",
                    "superseded discussion"):
            self.assertIn(cls, t)
        self.assertIn("Do not promote every comment into an acceptance criterion", t)
        self.assertIn("a comment is evidence, not automatically an authoritative requirement", t)


class ResolutionFailureTests(unittest.TestCase):
    def test_every_unresolved_status_stops_the_jira_scoped_path(self) -> None:
        for status in jc.UNRESOLVED_STATUSES:
            with self.subTest(status=status):
                self.assertEqual(
                    jc.resolve_jira_scope_outcome(status),
                    jc.JiraScopeOutcome.JIRA_CONTEXT_UNRESOLVED_STOP,
                )

    def test_unresolved_statuses_cover_the_six_documented_failure_modes(self) -> None:
        names = {s.name for s in jc.UNRESOLVED_STATUSES}
        self.assertEqual(
            names,
            {
                "UNRESOLVED_NO_INTEGRATION",
                "UNRESOLVED_AUTHENTICATION",
                "UNRESOLVED_AUTHORIZATION",
                "UNRESOLVED_NOT_FOUND",
                "UNRESOLVED_MALFORMED_REFERENCE",
                "UNRESOLVED_CONNECTOR_ERROR",
            },
        )

    def test_policy_enumerates_all_failure_modes_and_the_outcome_label(self) -> None:
        t = _text(SHARED_CONTEXT)
        self.assertIn("no Jira integration is available", t)
        self.assertIn("authentication fails", t)
        self.assertIn("authorization fails", t)
        self.assertIn("the issue does not exist", t)
        self.assertIn("the reference is malformed", t)
        self.assertIn("the integration/connector errors or times out", t)
        self.assertIn("JIRA CONTEXT UNRESOLVED", t)

    def test_runbooks_enumerate_the_connector_error_failure_mode(self) -> None:
        for rb in RUNBOOKS:
            self.assertIn("connector/MCP error or timeout", _text(rb))

    def test_github_review_output_declares_the_reasoning_result(self) -> None:
        t = (GITHUB / "policies/review-output.md").read_text(encoding="utf-8")
        self.assertIn("JIRA CONTEXT UNRESOLVED", t)


class NoInferenceFallbackTests(unittest.TestCase):
    def test_no_source_may_be_used_to_infer_ticket_contents(self) -> None:
        for source in jc.NON_INFERABLE_SOURCES:
            self.assertFalse(jc.may_infer_ticket_from(source))
        self.assertEqual(
            jc.NON_INFERABLE_SOURCES,
            {
                "ticket_key",
                "ticket_url",
                "branch_name",
                "pr_title",
                "commit_message",
                "surrounding_text",
                "copied_metadata_without_contents",
            },
        )

    def test_reference_is_a_pointer_not_contents(self) -> None:
        self.assertTrue(jc.jira_reference_is_context_pointer_not_contents())

    def test_policy_forbids_inference_from_key_branch_pr_title_and_copied_metadata(self) -> None:
        t = _text(SHARED_CONTEXT)
        self.assertIn(
            "do not infer ticket contents from the ticket key, the branch name, the "
            "PR title, a commit message, surrounding text, or copied issue metadata "
            "without the ticket's actual contents",
            t,
        )

    def test_runbooks_forbid_the_copied_metadata_fake_resolution(self) -> None:
        for rb in RUNBOOKS:
            self.assertIn("copied metadata", _text(rb))


class TargetNotWidenedTests(unittest.TestCase):
    def test_jira_context_cannot_widen_the_review_target(self) -> None:
        self.assertFalse(jc.jira_context_can_widen_review_target())

    def test_shared_policy_states_target_unchanged(self) -> None:
        self.assertIn(
            "Jira context informs scope but never expands the Review Target",
            _text(SHARED_CONTEXT),
        )

    def test_local_target_stays_local_delta(self) -> None:
        self.assertIn(
            "the review target is the local implementation delta",
            _text(LOCAL / "policies/review-context.md"),
        )

    def test_github_target_stays_the_pr(self) -> None:
        self.assertIn(
            "The review target stays the PR delta",
            _text(GITHUB / "policies/review-context.md"),
        )


class SharedSemanticsAcrossBothSkillsTests(unittest.TestCase):
    def test_both_skills_point_at_the_shared_jira_resolution_contract(self) -> None:
        for p in (
            LOCAL / "SKILL.md",
            GITHUB / "SKILL.md",
            LOCAL / "policies/review-context.md",
            GITHUB / "policies/review-context.md",
        ):
            t = _text(p)
            self.assertIn("Jira context resolution", t)
            self.assertIn("review-context.md", t)

    def test_shared_policy_says_it_applies_to_both_skills(self) -> None:
        self.assertIn(
            "Applies identically to local-code-review and github-pr-review",
            _text(SHARED_CONTEXT),
        )


class ReadOnlyGovernanceTests(unittest.TestCase):
    def test_module_defines_no_jira_mutating_capability(self) -> None:
        public = {n for n in dir(jc) if not n.startswith("_")}
        offending = {
            n for n in public
            if any(frag in n.lower() for frag in jc.PROHIBITED_MUTATION_NAME_FRAGMENTS)
        }
        self.assertEqual(offending, set())

    def test_policy_and_metadata_declare_jira_access_read_only(self) -> None:
        self.assertIn("Jira access is context retrieval only", _text(SHARED_CONTEXT))
        self.assertIn(
            "never edits an issue, transitions it, adds a comment, changes a "
            "field, creates a ticket, or assigns a user",
            _text(SHARED_CONTEXT),
        )
        for meta in (LOCAL / "metadata/skill.yaml", GITHUB / "metadata/skill.yaml"):
            self.assertIn("read-only", meta.read_text(encoding="utf-8"))

    def test_capability_is_transport_agnostic(self) -> None:
        t = _text(SHARED_CONTEXT)
        self.assertIn("Resolution depends on the capability", t)
        self.assertIn("Do not hard-code review semantics to one transport", t)
        self.assertIn("never a raw connector payload", t)


if __name__ == "__main__":
    unittest.main()
