#!/usr/bin/env python3
"""Test-only decision tables for Jira context resolution.

Mirrors shared/policies/review-context.md, "Jira context resolution".
Not runtime logic, not packaged.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Optional


class JiraResolutionStatus(Enum):
    NOT_SUPPLIED = "not_supplied"
    RESOLVED = "resolved"
    UNRESOLVED_NO_INTEGRATION = "unresolved_no_integration"
    UNRESOLVED_AUTHENTICATION = "unresolved_authentication_failure"
    UNRESOLVED_AUTHORIZATION = "unresolved_authorization_failure"
    UNRESOLVED_NOT_FOUND = "unresolved_issue_not_found"
    UNRESOLVED_MALFORMED_REFERENCE = "unresolved_malformed_reference"
    UNRESOLVED_CONNECTOR_ERROR = "unresolved_connector_or_mcp_error_or_timeout"


UNRESOLVED_STATUSES: FrozenSet[JiraResolutionStatus] = frozenset(
    s for s in JiraResolutionStatus if s.name.startswith("UNRESOLVED_")
)

# Contract: shared/policies/review-context.md, "Jira context resolution" →
# "Resolution procedure". The runbooks must instruct these steps, in order.
RESOLUTION_PROCEDURE_STEPS: tuple[str, ...] = (
    "identify_available_jira_integration",
    "invoke_read_only_fetch_issue",
    "fetch_relevant_comments_and_linked_context",
    "normalize_into_review_context",
    "continue_only_on_success",
)


def procedure_completed(steps_done: FrozenSet[str]) -> bool:
    """Jira context is usable only when every step ran."""
    return set(RESOLUTION_PROCEDURE_STEPS) <= set(steps_done)


def comment_retrieval_is_part_of_the_procedure() -> bool:
    """Comment/linked-context retrieval is an explicit step, not optional."""
    return "fetch_relevant_comments_and_linked_context" in RESOLUTION_PROCEDURE_STEPS


class JiraScopeOutcome(Enum):
    NORMAL_REVIEW_NO_JIRA = "normal_review_no_jira"
    REVIEW_WITH_JIRA_CONTEXT = "review_with_jira_context"
    JIRA_CONTEXT_UNRESOLVED_STOP = "jira_context_unresolved_stop"


def resolve_jira_scope_outcome(status: JiraResolutionStatus) -> JiraScopeOutcome:
    """Map a resolution status to the review path. An unresolvable supplied
    reference stops the Jira-scoped path — never "review anyway"."""
    if status is JiraResolutionStatus.NOT_SUPPLIED:
        return JiraScopeOutcome.NORMAL_REVIEW_NO_JIRA
    if status is JiraResolutionStatus.RESOLVED:
        return JiraScopeOutcome.REVIEW_WITH_JIRA_CONTEXT
    return JiraScopeOutcome.JIRA_CONTEXT_UNRESOLVED_STOP


# Sources ticket contents must never be inferred from when resolution fails.
NON_INFERABLE_SOURCES: FrozenSet[str] = frozenset(
    {
        "ticket_key",
        "ticket_url",
        "branch_name",
        "pr_title",
        "commit_message",
        "surrounding_text",
        "copied_metadata_without_contents",
    }
)


def may_infer_ticket_from(source: str) -> bool:
    """Always False — a reference is a pointer, never inferred contents."""
    del source
    return False


def jira_reference_is_context_pointer_not_contents() -> bool:
    """Structural restatement of the policy invariant, for tests."""
    return True


def jira_context_can_widen_review_target() -> bool:
    """Never. Jira context informs scope; the review target is unchanged."""
    return False


#: Fields carried into review context. The connector returns more; only
#: these inform intended behavior, boundaries, requirements, and decisions.
NORMALIZED_JIRA_FIELDS: FrozenSet[str] = frozenset(
    {
        "issue_key",
        "summary",
        "description",
        "issue_type",
        "status",
        "acceptance_criteria",
        "components",
        "labels",
        "priority",
        "parent_or_epic",
        "linked_issues",
        "relevant_comments",
        "linked_design_info",
        "explicit_non_goals",
        "constraints",
        "clarifications",
        "settled_decisions",
    }
)


def normalize_field(name: str) -> Optional[str]:
    """Return the field name if it is carried into review context, else None
    (the raw Jira payload is never injected wholesale)."""
    return name if name in NORMALIZED_JIRA_FIELDS else None


class JiraCommentClass(Enum):
    SETTLED_CLARIFICATION = "settled_clarification"
    ACCEPTED_DECISION = "accepted_decision"
    IMPLEMENTATION_NOTE = "implementation_note"
    UNRESOLVED_QUESTION = "unresolved_question"
    SPECULATIVE_SUGGESTION = "speculative_suggestion"
    REJECTED_APPROACH = "rejected_approach"
    SUPERSEDED_DISCUSSION = "superseded_discussion"


@dataclass(frozen=True)
class JiraComment:
    comment_class: JiraCommentClass
    states_pass_fail_condition: bool = False
    superseded_by_later_comment: bool = False


def promote_comment_to_acceptance_criterion(comment: JiraComment) -> bool:
    """A comment becomes an acceptance criterion only if it is a settled
    clarification or accepted decision stating a pass/fail condition, and is
    not superseded."""
    if comment.superseded_by_later_comment:
        return False
    if not comment.states_pass_fail_condition:
        return False
    return comment.comment_class in (
        JiraCommentClass.SETTLED_CLARIFICATION,
        JiraCommentClass.ACCEPTED_DECISION,
    )


def prefer_newer_maintainer_clarification(
    *, newer_is_explicit_maintainer_clarification: bool, older_is_speculative: bool
) -> str:
    """A newer explicit maintainer clarification wins over stale speculation;
    otherwise the conflict is reported, not resolved."""
    if newer_is_explicit_maintainer_clarification and older_is_speculative:
        return "newer"
    return "unresolved_report_the_conflict"


#: Name fragments a Jira-mutating capability would use. This layer is
#: read-only; test_jira_context.py fails if any public name matches one.
PROHIBITED_MUTATION_NAME_FRAGMENTS: FrozenSet[str] = frozenset(
    {
        "create_issue",
        "create_ticket",
        "edit_issue",
        "update_issue",
        "update_field",
        "set_field",
        "transition",
        "add_comment",
        "post_comment",
        "comment_on_issue",
        "assign",
        "delete_issue",
        "close_issue",
        "resolve_issue",
        "link_issue",
    }
)
