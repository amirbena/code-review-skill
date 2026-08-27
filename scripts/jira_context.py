#!/usr/bin/env python3
"""Reference/test decision tables for Jira context resolution.

Mirrors shared/policies/review-context.md, "Jira context resolution", and its
thin Skill applications. Pure decision-table logic — no Jira/MCP/HTTP calls,
no code understanding. NOT production/runtime logic: both packaged Skills
implement this behavior through the policy text (packaged with each Skill),
and neither packaged Skill file imports, invokes, or otherwise depends on
this module at runtime. It is not part of either packaged Skill archive.

This module never resolves a real ticket, judges whether described behavior
exists, or grades a review. It encodes only: what a resolution status means
for the review path, that no inference fallback is ever permitted, which
fields are normalized, how a Jira comment is classified, and the read-only
governance guard.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet, Optional


class JiraResolutionStatus(Enum):
    NOT_SUPPLIED = "not_supplied"
    RESOLVED = "resolved"
    UNRESOLVED_NO_INTEGRATION = "unresolved_no_integration"
    UNRESOLVED_AUTH = "unresolved_authentication_or_authorization"
    UNRESOLVED_NOT_FOUND = "unresolved_ticket_not_found"
    UNRESOLVED_MALFORMED_REFERENCE = "unresolved_malformed_reference"


UNRESOLVED_STATUSES: FrozenSet[JiraResolutionStatus] = frozenset(
    s for s in JiraResolutionStatus if s.name.startswith("UNRESOLVED_")
)


class JiraScopeOutcome(Enum):
    NORMAL_REVIEW_NO_JIRA = "normal_review_no_jira"
    REVIEW_WITH_JIRA_CONTEXT = "review_with_jira_context"
    JIRA_CONTEXT_UNRESOLVED_STOP = "jira_context_unresolved_stop"


def resolve_jira_scope_outcome(status: JiraResolutionStatus) -> JiraScopeOutcome:
    """Map a resolution status to what the review invocation does.

    Precondition semantics per policy: a supplied-but-unresolvable Jira
    reference stops the Jira-scoped path; it is never downgraded to "review
    anyway without the ticket".
    """
    if status is JiraResolutionStatus.NOT_SUPPLIED:
        return JiraScopeOutcome.NORMAL_REVIEW_NO_JIRA
    if status is JiraResolutionStatus.RESOLVED:
        return JiraScopeOutcome.REVIEW_WITH_JIRA_CONTEXT
    return JiraScopeOutcome.JIRA_CONTEXT_UNRESOLVED_STOP


#: Sources the policy forbids inferring ticket contents from when resolution
#: fails. Every entry maps to False in may_infer_ticket_from() — there is no
#: parameter that flips it on.
NON_INFERABLE_SOURCES: FrozenSet[str] = frozenset(
    {
        "ticket_key",
        "branch_name",
        "pr_title",
        "commit_message",
        "surrounding_text",
    }
)


def may_infer_ticket_from(source: str) -> bool:
    """Always False. A Jira reference is a pointer, not its contents; an
    unresolved reference is reported, never guessed at."""
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
    """Only a settled clarification or an accepted decision that actually
    states a pass/fail condition, and is not superseded, becomes an
    acceptance criterion. Speculative / rejected / open comments never do."""
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
    """Which of two conflicting comments governs. Policy: prefer a newer
    explicit maintainer/product clarification over stale speculative
    discussion when repository evidence supports it."""
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
