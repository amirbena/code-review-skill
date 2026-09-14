#!/usr/bin/env python3
"""Test-only reference model for the private Reviewer Brief (Issue #304).

Not runtime logic, not packaged. The canonical behavior lives in
``skills/github-pr-review/policies/reviewer-brief.md`` and
``skills/github-pr-review/templates/reviewer-brief.md``; this module makes
that policy's synthesis rules, mode-composition rules, and — most
importantly — the structural publication boundary executable so the unit
tests can pin them.

Two things are modeled:

1. ``compose_reviewer_brief`` — synthesizes a ``ReviewerBrief`` from an
   already-finalized ``FinalizedReview`` plus context. It is a pure
   function over already-finished analysis: it has no way to mutate the
   ``FinalizedReview`` it is given (the dataclass is frozen), which is the
   executable form of "reads the finalized analysis result; it never
   influences it."
2. ``build_publication_payload`` — constructs the GitHub-bound
   ``PublicationPayload`` (review body + inline comments + event) from a
   ``FinalizedReview`` alone. Its signature has no parameter through which
   a ``ReviewerBrief`` (or arbitrary caller-supplied text) could reach the
   payload — the structural boundary the policy describes. The negative
   tests in ``tests/unit/review/test_reviewer_brief_publication_boundary.py``
   attempt to smuggle brief content through every available surface and
   confirm none of them land in the payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence


class Severity(Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class Verdict(Enum):
    CLEAN = "REVIEW CLEAN"
    CHANGES_REQUIRED = "CHANGES REQUIRED"
    INCOMPLETE = "REVIEW INCOMPLETE"


@dataclass(frozen=True)
class Finding:
    finding_id: str
    severity: Severity
    title: str
    location: str


@dataclass(frozen=True)
class FinalizedReview:
    """The output of analysis, after review-output.md's "Analysis phase vs.
    publication phase" boundary — findings, severity, coverage, and verdict
    are already fixed. Frozen: nothing downstream (brief composition or
    publication construction) can mutate it.
    """

    findings: tuple[Finding, ...]
    verdict: Verdict
    coverage_complete: bool
    reviewed_sha: str
    # Mode context, all optional / inert by default.
    is_delta_review: bool = False
    delta_summary: Optional[str] = None
    is_stacked: bool = False
    stack_layer_summary: Optional[str] = None
    is_partitioned: bool = False
    partition_count: int = 0


@dataclass(frozen=True)
class ReviewerBrief:
    """The private, caller-facing brief. Deliberately a *separate* type
    from anything ``build_publication_payload`` accepts — see module
    docstring.
    """

    what_changed: str
    user_provided_focus: str  # "none provided" when the caller supplied none
    manual_review_focus: tuple[str, ...]
    open_questions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not (2 <= len(self.manual_review_focus) <= 4):
            raise ValueError(
                "manual_review_focus must carry 2-4 bullets per "
                "reviewer-brief.md, 'Required fields'"
            )

    def render(self) -> str:
        lines = [
            "## Reviewer Brief",
            "",
            f"- **What changed:** {self.what_changed}",
            f"- **User-provided focus:** {self.user_provided_focus}",
            "- **Manual review focus:**",
        ]
        lines.extend(f"  - {item}" for item in self.manual_review_focus)
        if self.open_questions:
            lines.append(
                "- **Open questions / assumptions:** "
                + "; ".join(self.open_questions)
            )
        return "\n".join(lines)


NONE_PROVIDED = "none provided"


def compose_reviewer_brief(
    finalized: FinalizedReview,
    *,
    what_changed: str,
    user_provided_focus: Optional[str],
    reviewer_derived_focus: Sequence[str],
    user_focus_bullets: Sequence[str] = (),
    open_questions: Sequence[str] = (),
) -> ReviewerBrief:
    """Synthesize the brief from the finalized result plus context.

    ``finalized`` is read-only input: this function never returns a
    modified ``FinalizedReview`` and has no mechanism to feed anything
    back into severity/coverage/verdict — those were already fixed before
    this is ever called (reviewer-brief.md, "Presentation over
    already-completed analysis").

    Trusted ``user_provided_focus`` (free text) and any focus bullets
    derived from it are attention/wording signals only — they are woven
    into the rendered text, never into ``finalized``'s fields, and this
    function accepts no parameter that could alter severity, coverage, or
    verdict. ``reviewer_derived_focus`` supplies focus areas the reviewer
    independently identified from the diff/repository, and must contain at
    least one item that is not present in ``user_focus_bullets`` for the
    brief to add value beyond the caller's own request (enforced by
    callers/tests, not this function, since a caller may legitimately
    supply none).
    """
    bullets = list(user_focus_bullets) + [
        item for item in reviewer_derived_focus if item not in user_focus_bullets
    ]
    if len(bullets) < 2:
        raise ValueError(
            "not enough manual review focus bullets synthesized "
            "(need >= 2 per reviewer-brief.md)"
        )
    bullets = bullets[:4]

    delta_note = ""
    if finalized.is_delta_review and finalized.delta_summary:
        delta_note = f" {finalized.delta_summary}"
    stack_note = ""
    if finalized.is_stacked and finalized.stack_layer_summary:
        stack_note = f" {finalized.stack_layer_summary}"

    return ReviewerBrief(
        what_changed=f"{what_changed}{delta_note}{stack_note}".strip(),
        user_provided_focus=user_provided_focus or NONE_PROVIDED,
        manual_review_focus=tuple(bullets),
        open_questions=tuple(open_questions),
    )


# --- Publication payload: the structural boundary -----------------------


@dataclass(frozen=True)
class InlineComment:
    finding_id: str
    body: str


@dataclass(frozen=True)
class PublicationPayload:
    """Exactly what review-output.md, 'Batched review construction and
    submission,' submits to GitHub: one review body, an array of inline
    comments, and one event. There is no field here for a Reviewer Brief.
    """

    body: str
    inline_comments: tuple[InlineComment, ...]
    event: str  # "APPROVE" | "REQUEST_CHANGES" | "COMMENT" | "WITHHELD"


def render_review_body(finalized: FinalizedReview) -> str:
    """Renders exactly templates/external-review-summary.md's shape — no
    Reviewer Brief section, ever."""
    if not finalized.findings:
        header = "**Result: ✅ REVIEW CLEAN**"
        body_lines = [
            "## Review Summary",
            "",
            header,
            "",
            f"No blocking findings at `{finalized.reviewed_sha}`.",
        ]
    else:
        header = "**Result: ⚠️ CHANGES REQUIRED**"
        body_lines = [
            "## Review Summary",
            "",
            header,
            "",
            "### Findings",
            "",
        ]
        for f in finalized.findings:
            body_lines.append(f"- **{f.severity.value} — {f.title}** `{f.location}`")
    return "\n".join(body_lines)


def build_publication_payload(finalized: FinalizedReview, event: str) -> PublicationPayload:
    """Constructs the GitHub-bound payload from ``finalized`` alone.

    This function's signature is the executable form of reviewer-brief.md,
    "Never published to GitHub": there is no ``brief`` parameter, no
    ``**kwargs`` catch-all, and no global/shared mutable state it reads
    from. A caller cannot pass a ``ReviewerBrief`` in even if it wanted
    to — TypeError, not a runtime redaction step, is what stops it.
    """
    body = render_review_body(finalized)
    inline_comments = tuple(
        InlineComment(finding_id=f.finding_id, body=f"[{f.severity.value}] {f.title}")
        for f in finalized.findings
    )
    return PublicationPayload(body=body, inline_comments=inline_comments, event=event)
