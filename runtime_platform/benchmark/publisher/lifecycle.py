"""Drift-issue lifecycle over a sealed record's `drift.confirmed[]`: never recomputes drift.

Contract: `scheduled-operations/drift-issue-lifecycle-and-recovery.md` §1, §3, §4.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from runtime_platform.benchmark.publisher import markers, render
from runtime_platform.benchmark.publisher.ports import FatalPublicationError, Issue, IssueTracker

CLOSED_SCAN_LIMIT = 200
_JSON_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


@dataclass(frozen=True)
class IssueAction:
    fingerprint: str
    issue: int
    action: str

    def as_dict(self) -> dict[str, Any]:
        return {"fingerprint": self.fingerprint, "issue": self.issue, "action": self.action}


@dataclass
class Reconciliation:
    actions: list[IssueAction] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)
    skipped: str | None = None


@dataclass(frozen=True)
class LifecycleContext:
    tracker: IssueTracker
    identity: str
    regression_label: str
    keep_open_label: str
    max_new_issues: int
    now: str


def covers(record: Mapping[str, Any], case_id: str) -> bool:
    """A lane covers a case when its latest record evaluated it against a comparable baseline."""
    return (
        record["baseline"]["state"] == "compared"
        and case_id in record["drift"]["evaluated_scope"]
        and case_id in record["baseline"]["comparable_case_ids"]
    )


def _verified(ctx: LifecycleContext, kind: str, author: str) -> None:
    if author != ctx.identity:
        raise FatalPublicationError(f"{kind} was authored by {author!r}, not the publisher identity {ctx.identity!r}")


def _publisher_issues(ctx: LifecycleContext, state: str, limit: int | None) -> dict[str, list[Issue]]:
    """Fingerprint -> its publisher-authored issues, lowest number first."""
    by_fingerprint: dict[str, list[Issue]] = {}
    for issue in ctx.tracker.list_issues(ctx.regression_label, state=state, limit=limit):
        fingerprint = markers.fingerprint_of_issue_body(issue.body)
        if fingerprint and issue.author == ctx.identity:
            by_fingerprint.setdefault(fingerprint, []).append(issue)
    return {fp: sorted(issues, key=lambda i: i.number) for fp, issues in by_fingerprint.items()}


def _case_id_of(issue: Issue) -> str | None:
    match = _JSON_BLOCK_RE.search(issue.body)
    try:
        case_id = json.loads(match.group(1)).get("case_id") if match else None
    except (json.JSONDecodeError, AttributeError):
        return None
    return case_id if isinstance(case_id, str) else None


def _touch_open_issue(
    ctx: LifecycleContext, record: Mapping[str, Any], drift: Mapping[str, Any], issue: Issue, evidence: render.Evidence
) -> IssueAction:
    fingerprint = drift["fingerprint"]
    marker = markers.applied_marker(record["run_id"], fingerprint)
    if marker in issue.body:
        return IssueAction(fingerprint, issue.number, "opened")
    if markers.find_marked_comment(ctx.tracker.list_comments(issue.number), marker, ctx.identity) is None:
        posted = ctx.tracker.create_comment(issue.number, render.recurrence_comment(record, drift, evidence, ctx.now))
        _verified(ctx, "comment", posted.author)
    return IssueAction(fingerprint, issue.number, "commented")


def _close_duplicates(
    ctx: LifecycleContext, record: Mapping[str, Any], drift: Mapping[str, Any], created: Issue, evidence: render.Evidence
) -> IssueAction:
    """One open issue per fingerprint: keep the lowest number and close the other with a pointer."""
    fingerprint = drift["fingerprint"]
    open_issues = _publisher_issues(ctx, "open", None).get(fingerprint, [created])
    kept = open_issues[0]
    for extra in open_issues[1:]:
        if extra.number == created.number or kept.number == created.number:
            posted = ctx.tracker.create_comment(extra.number, render.duplicate_pointer_comment(kept.number))
            _verified(ctx, "comment", posted.author)
            ctx.tracker.close_issue(extra.number)
    if kept.number == created.number:
        return IssueAction(fingerprint, created.number, "opened")
    return _touch_open_issue(ctx, record, drift, kept, evidence)


def _open_issue(
    ctx: LifecycleContext,
    record: Mapping[str, Any],
    drift: Mapping[str, Any],
    evidence: render.Evidence,
    closed: dict[str, list[Issue]] | None,
) -> IssueAction:
    fingerprint = drift["fingerprint"]
    previous = (closed or {}).get(fingerprint)
    created = ctx.tracker.create_issue(
        title=render.issue_title(drift),
        body=render.issue_body(record, drift, evidence, ctx.now, previous[-1].number if previous else None),
        labels=[ctx.regression_label],
    )
    _verified(ctx, "issue", created.author)
    return _close_duplicates(ctx, record, drift, created, evidence)


def _resolve(
    ctx: LifecycleContext,
    record: Mapping[str, Any],
    fingerprint: str,
    issue: Issue,
    lane_views: Mapping[str, Mapping[str, Any] | None],
    evidence: render.Evidence,
) -> IssueAction | None:
    """Close only when every lane whose latest record covers the case has stopped confirming it (A9)."""
    case_id = _case_id_of(issue)
    if case_id is None:
        return None
    covering = {lane: rec for lane, rec in lane_views.items() if rec is not None and covers(rec, case_id)}
    if not covering:
        return None
    if any(fingerprint in {d["fingerprint"] for d in rec["drift"]["confirmed"]} for rec in covering.values()):
        return None
    fresh = ctx.tracker.get_issue(issue.number)
    if fresh is None or fresh.state != "open":
        return None
    if ctx.keep_open_label in fresh.labels:
        return IssueAction(fingerprint, issue.number, "kept-open")
    marker = markers.applied_marker(record["run_id"], fingerprint)
    if markers.find_marked_comment(ctx.tracker.list_comments(issue.number), marker, ctx.identity) is None:
        body = render.resolution_comment(record, fingerprint, evidence, ctx.now, sorted(covering))
        _verified(ctx, "comment", ctx.tracker.create_comment(issue.number, body).author)
    ctx.tracker.close_issue(issue.number)
    return IssueAction(fingerprint, issue.number, "closed")


def reconcile(
    ctx: LifecycleContext,
    record: Mapping[str, Any],
    lane_views: Mapping[str, Mapping[str, Any] | None] | None,
    evidence: render.Evidence,
) -> Reconciliation:
    """Open, comment on, or close drift issues for one published record.

    `lane_views` maps each scheduled lane to its latest published record (None when it has none),
    or is None when a lane's record could not be loaded, which disables closing.
    """
    result = Reconciliation()
    if record["baseline"]["state"] != "compared":
        result.skipped = f"baseline {record['baseline']['state']}: no drift issue is opened, commented on, or closed"
        return result

    confirmed = {d["fingerprint"]: d for d in record["drift"]["confirmed"]}
    open_by_fingerprint = _publisher_issues(ctx, "open", None)
    closed: dict[str, list[Issue]] | None = None
    opened = 0

    for fingerprint, drift in confirmed.items():
        existing = open_by_fingerprint.get(fingerprint)
        if existing:
            result.actions.append(_touch_open_issue(ctx, record, drift, existing[0], evidence))
        elif opened >= ctx.max_new_issues:
            result.deferred.append(fingerprint)
        else:
            if closed is None:
                closed = _publisher_issues(ctx, "closed", CLOSED_SCAN_LIMIT)
            result.actions.append(_open_issue(ctx, record, drift, evidence, closed))
            opened += 1

    if lane_views is None:
        return result
    for fingerprint, issues in open_by_fingerprint.items():
        if fingerprint not in confirmed:
            action = _resolve(ctx, record, fingerprint, issues[0], lane_views, evidence)
            if action is not None:
                result.actions.append(action)
    return result
