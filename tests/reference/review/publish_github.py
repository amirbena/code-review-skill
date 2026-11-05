"""Test-only reference model of review-publish-github (ADR S7).

Mirrors skills/review-publish-github: authority and event selection, HEAD
revalidation, reconciliation with existing comments, placement, and one
batched submission. Never imported at Skill runtime.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol, Sequence

CLEAN = "REVIEW CLEAN"
CHANGES = "CHANGES REQUIRED"
INCOMPLETE = "REVIEW INCOMPLETE"


class Event(Enum):
    COMMENT = "COMMENT"
    APPROVE = "APPROVE"
    REQUEST_CHANGES = "REQUEST_CHANGES"


class Status(Enum):
    SUBMITTED = "submitted"
    NOT_REQUESTED = "not_requested"
    STALE_HEAD = "stale_head"
    PERMISSION_DENIED = "permission_denied"


@dataclass(frozen=True)
class Finding:
    id: str
    severity: str
    title: str
    path: str
    line: Optional[int]
    evidence: str = "e"
    impact: str = "i"
    fix: str = "f"


@dataclass(frozen=True)
class CoreResult:
    decision: str
    findings: tuple[Finding, ...]
    reviewed_head: str


@dataclass(frozen=True)
class PrFacts:
    author: str
    viewer: str
    head_sha: str
    draft: bool = False
    fork: bool = False
    fork_upstream_confirmed: bool = False
    shared_authority: bool = False
    can_review: Optional[bool] = True  # None = cannot be determined


@dataclass(frozen=True)
class InlineComment:
    path: str
    line: int
    body: str


@dataclass(frozen=True)
class Submission:
    event: Event
    body: str
    comments: tuple[InlineComment, ...]


@dataclass(frozen=True)
class ExistingComment:
    path: str
    title: str
    resolved: bool = False
    defect_present_at_head: bool = False


class InlineRejected(Exception):
    def __init__(self, bad: Sequence[InlineComment]):
        super().__init__("inline location rejected")
        self.bad = tuple(bad)


class ReviewRefused(Exception):
    pass


class GitHub(Protocol):
    def facts(self) -> PrFacts: ...
    def head_sha(self) -> str: ...
    def existing(self) -> tuple[Sequence[ExistingComment], bool]: ...
    def changed_lines(self) -> dict[str, set[int]]: ...
    def submit(self, submission: Submission) -> str: ...


@dataclass(frozen=True)
class Outcome:
    status: Status
    event: Optional[Event] = None
    submission: Optional[Submission] = None
    skipped_existing: int = 0
    reason: str = ""


def is_self_review(facts: PrFacts) -> bool:
    return facts.viewer == facts.author or facts.shared_authority or not facts.viewer or not facts.author


def select_event(facts: PrFacts, decision: str) -> Event:
    if is_self_review(facts) or facts.draft or decision == INCOMPLETE:
        return Event.COMMENT
    if facts.fork and not facts.fork_upstream_confirmed:
        return Event.COMMENT
    return Event.APPROVE if decision == CLEAN else Event.REQUEST_CHANGES


def _key(title: str) -> str:
    return re.sub(r"\W+", " ", title).strip().lower()


def already_raised(finding: Finding, existing: Sequence[ExistingComment]) -> bool:
    for c in existing:
        if c.path == finding.path and _key(c.title) == _key(finding.title):
            if not c.resolved or not c.defect_present_at_head:
                return True
    return False


def _inline_body(f: Finding) -> str:
    return f"[{f.severity}] {f.title}\n\nEvidence: {f.evidence}\n\nImpact: {f.impact}\n\nFix: {f.fix}"


def _summary(core: CoreResult, event: Event, inline: Sequence[Finding], body: Sequence[Finding], skipped: int) -> str:
    lines = [f"## Review: {core.decision}", "", f"Event: {event.value}", f"Reviewed commit: {core.reviewed_head[:7]}", ""]
    if inline or body:
        lines.append("### Findings")
        lines += [f"- [{f.severity}] {f.title} ({f.path}:{f.line}), inline" for f in inline]
        lines += [f"- [{f.severity}] {f.title} ({_loc(f)})" for f in body]
    for f in body:
        lines += ["", f"**{f.id} [{f.severity}] {f.title}** ({_loc(f)})", f"Evidence: {f.evidence}"]
    lines += ["", f"Skipped as already raised: {skipped}"]
    return "\n".join(lines)


def _loc(f: Finding) -> str:
    return f"{f.path}:{f.line}" if f.line else f.path


def publish(gh: GitHub, core: CoreResult, *, user_asked_to_publish: bool, mode_is_auto: bool = False) -> Outcome:
    # `auto` mode never selects publication; only the user's request does.
    if not user_asked_to_publish:
        return Outcome(Status.NOT_REQUESTED)
    facts = gh.facts()
    if facts.can_review is not True:
        return Outcome(Status.PERMISSION_DENIED, reason="cannot submit a review")
    event = select_event(facts, core.decision)
    existing, _complete = gh.existing()
    fresh = [f for f in core.findings if not already_raised(f, existing)]
    skipped = len(core.findings) - len(fresh)
    changed = gh.changed_lines()
    inline = [f for f in fresh if f.line and f.line in changed.get(f.path, ())]
    body = [f for f in fresh if f not in inline]
    for _ in range(2):
        comments = tuple(InlineComment(f.path, f.line, _inline_body(f)) for f in inline)
        submission = Submission(event, _summary(core, event, inline, body, skipped), comments)
        if gh.head_sha() != core.reviewed_head:
            return Outcome(Status.STALE_HEAD, reason="HEAD moved since the review")
        try:
            gh.submit(submission)
            return Outcome(Status.SUBMITTED, event, submission, skipped)
        except InlineRejected as rejected:
            bad = {(c.path, c.line) for c in rejected.bad}
            moved = [f for f in inline if (f.path, f.line) in bad]
            inline = [f for f in inline if f not in moved]
            body += moved
        except ReviewRefused:
            return Outcome(Status.PERMISSION_DENIED, reason="review event refused")
    return Outcome(Status.PERMISSION_DENIED, reason="submission failed after retry")


@dataclass
class FakeGitHub:
    """In-memory PR for publication tests; records every write."""

    pr: PrFacts
    changed: dict[str, set[int]] = field(default_factory=dict)
    comments: tuple[ExistingComment, ...] = ()
    head_reads: list[str] = field(default_factory=list)
    refuse_events: frozenset = frozenset()
    reject_inline: frozenset = frozenset()  # (path, line) GitHub refuses to anchor
    writes: list[Submission] = field(default_factory=list)

    def facts(self) -> PrFacts:
        return self.pr

    def head_sha(self) -> str:
        return self.head_reads.pop(0) if self.head_reads else self.pr.head_sha

    def existing(self):
        return self.comments, True

    def changed_lines(self):
        return self.changed

    def submit(self, submission: Submission) -> str:
        if submission.event in self.refuse_events:
            raise ReviewRefused(submission.event.value)
        bad = [c for c in submission.comments if c.line not in self.changed.get(c.path, ()) or (c.path, c.line) in self.reject_inline]
        if bad:
            raise InlineRejected(bad)
        self.writes.append(submission)
        return "https://example.test/review/1"
