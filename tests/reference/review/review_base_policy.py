#!/usr/bin/env python3
"""Test-only reference for review-base policy compliance (Issue #134).

Not runtime logic, not packaged — the packaged Skills are Markdown/YAML
only, matching tests/reference/review/stacked_pr_topology.py's own
framing. No packaged Skill resource depends on this module or on
docs/review-base-policy/review-base-policy-model.md.

Mirrors docs/review-base-policy/review-base-policy-model.md: the ranked
resolution signals for the repository-resolved review base (§3), the
fail-closed rule for an unresolved base (§4), and the per-Skill
application to the stack's resolved root rather than an intermediate
layer (§5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ReviewBaseResolution:
    """The outcome of resolving the repository-resolved review base from
    the ranked signals in §3. ``resolved`` is False exactly when neither
    signal reliably resolves — the fail-closed case (§4)."""

    resolved: bool
    branch: Optional[str] = None
    source: Optional[str] = None  # "explicit_statement" | "default_branch"


def resolve_repository_review_base(
    *,
    explicit_statement_branch: Optional[str] = None,
    default_branch: Optional[str] = None,
    default_branch_ambiguous: bool = False,
) -> ReviewBaseResolution:
    """§3: an explicit repository-stated policy is ranked above the bare
    default/target branch. Absent either reliable signal, the base is
    unresolved (§4) — never guessed, and never defaulted to some other
    value the caller might supply (e.g. HEAD)."""
    if explicit_statement_branch:
        return ReviewBaseResolution(
            resolved=True, branch=explicit_statement_branch, source="explicit_statement"
        )
    if default_branch and not default_branch_ambiguous:
        return ReviewBaseResolution(resolved=True, branch=default_branch, source="default_branch")
    return ReviewBaseResolution(resolved=False)


@dataclass(frozen=True)
class ReviewBaseFinding:
    """§6: exactly one P0 finding, naming both branches, when a violation
    is confirmed. ``None`` from `check_review_base_compliance` means no
    finding — either compliant or fail-closed."""

    severity: str
    base_under_review: str
    required_base: str


def check_review_base_compliance(
    *,
    base_under_review: Optional[str],
    repository_resolved_base: ReviewBaseResolution,
    is_legitimate_stack_parent: bool = False,
) -> Optional[ReviewBaseFinding]:
    """§4 (fail-closed) and §5 (per-Skill application).

    ``base_under_review`` being ``None`` models "the base under review
    itself could not be established reliably" (e.g. a stack whose
    topology fell back to a safe-failure tier) — this is exactly the
    fail-closed case, not a reason to compare against a substituted
    value such as HEAD.

    ``is_legitimate_stack_parent`` models the github-pr-review case where
    the declared base is a stack layer's own parent PR — stacked-pr-review.md
    already treats that as legitimate, so this check never fires for it;
    the check only ever applies to the resolved root.
    """
    if is_legitimate_stack_parent:
        return None
    if base_under_review is None or not repository_resolved_base.resolved:
        return None
    if base_under_review == repository_resolved_base.branch:
        return None
    return ReviewBaseFinding(
        severity="P0",
        base_under_review=base_under_review,
        required_base=repository_resolved_base.branch,
    )
