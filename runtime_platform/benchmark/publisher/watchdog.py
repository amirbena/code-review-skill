"""`watchdog`: missed-run issues by gap arithmetic, then the health-status comment.

Contract: `runtime_platform/benchmark/publication-cli.md` §7 and
`scheduled-operations/drift-issue-lifecycle-and-recovery.md` §5. The only rule is elapsed time against
the manifest's `max_gap_hours`; no wall-clock slot, weekday, or zone is consulted (#431).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Mapping

from runtime_platform.benchmark.publisher import health, markers, render
from runtime_platform.benchmark.publisher.layout import record_path, run_sort_key
from runtime_platform.benchmark.publisher.model import Ports, WatchdogConfig, WatchdogReport, format_instant, parse_instant
from runtime_platform.benchmark.publisher.ports import FatalPublicationError, HistoryStore, Issue, IssueTracker, PublicationFailure
from runtime_platform.benchmark.publisher.sweep import manifest_labels, preflight
from runtime_platform.benchmark.scripts.benchmark_result import content_sha256, parse_run_id

MAX_RECORDS_SCANNED = 30
_RUNBOOK = "runtime_platform/benchmark/scheduled-operations/drift-issue-lifecycle-and-recovery.md"


@dataclass(frozen=True)
class LaneStatus:
    lane: str
    max_gap_hours: int
    record: Mapping[str, Any] | None
    finished: datetime | None
    expected_from: datetime | None
    overdue: bool

    @property
    def reference(self) -> datetime | None:
        """The later of the last verified scheduled `finished_at` and the manifest's `expected_from`."""
        return max((t for t in (self.finished, self.expected_from) if t is not None), default=None)

    @property
    def from_record(self) -> bool:
        """The gap is measured from a published record, not from the activation anchor."""
        return self.finished is not None and (self.expected_from is None or self.finished >= self.expected_from)


def _published_run_ids(store: HistoryStore, lane: str) -> list[str]:
    """The lane's receipted run ids, newest first, bounded."""
    run_ids: list[str] = []
    for year in sorted((n for n in store.list_dir(f"receipts/{lane}") if n.isdigit()), reverse=True):
        names = (n[:-5] for n in store.list_dir(f"receipts/{lane}/{year}") if n.endswith(".json"))
        run_ids += sorted((n for n in names if (parse_run_id(n) or ("",))[0] == lane), key=run_sort_key, reverse=True)
        if len(run_ids) >= MAX_RECORDS_SCANNED:
            break
    return run_ids[:MAX_RECORDS_SCANNED]


def _verified_scheduled(store: HistoryStore, run_id: str, lane: str) -> tuple[dict[str, Any], datetime] | None:
    """The stored record when it is intact, verified, scheduled, and carries a readable `finished_at`."""
    data = store.read_file(record_path(run_id))
    try:
        record = json.loads(data.decode("utf-8")) if data is not None else None
        intact = isinstance(record, dict) and record.get("content_sha256") == content_sha256(record)
        qualifies = intact and record["run_id"] == run_id and record["lane"] == lane
        qualifies = qualifies and record["trigger"] == "scheduled" and record["verification"]["overall_verified"] is True
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, KeyError, TypeError):
        return None
    finished = parse_instant(record["finished_at"]) if qualifies else None
    return (record, finished) if finished is not None else None


def expected_from(lane: str, value: object) -> datetime | None:
    """`null` is "not activated"; anything else that is not a UTC instant stops the pass instead of reading as unset."""
    if value is None:
        return None
    instant = parse_instant(value)
    if instant is None:
        raise FatalPublicationError(f"lanes.{lane}.expected_from {value!r} is not a UTC instant; refusing to treat the lane as not activated")
    return instant


def lane_status(store: HistoryStore, lane: str, max_gap_hours: int, expected_from: datetime | None, now: datetime) -> LaneStatus:
    """Latest verified scheduled record of the lane; a manual run never satisfies the gap (case 7).

    Before any record exists the manifest's `expected_from` is the reference, so a lane broken since its
    first expected run cannot stay silent; while it is unset the lane is not activated and nothing is judged.
    """
    found = (_verified_scheduled(store, run_id, lane) for run_id in _published_run_ids(store, lane))
    record, finished = next(filter(None, found), (None, None))
    reference = max((t for t in (finished, expected_from) if t is not None), default=None)
    overdue = reference is not None and now - reference > timedelta(hours=max_gap_hours)
    return LaneStatus(lane, max_gap_hours, record, finished, expected_from, overdue)


@dataclass(frozen=True)
class MissedRunContext:
    tracker: IssueTracker
    identity: str
    label: str
    interval: timedelta
    now: datetime
    health_issue: int


def _describe(status: LaneStatus, now: datetime) -> str:
    hours = int((now - status.reference).total_seconds() // 3600)
    if status.from_record:
        since = f"its latest verified scheduled record (`{status.record['run_id']}`) finished {status.record['finished_at']}"
    else:
        since = f"it has published no verified scheduled record since its expected start {format_instant(status.expected_from)}"
    return f"{since}, {hours} h ago; the limit is {status.max_gap_hours} h"


def _issue_body(ctx: MissedRunContext, status: LaneStatus) -> str:
    stamp = format_instant(ctx.now)
    return (
        f"{markers.missed_run_marker(status.lane)}\n{markers.missed_run_notice(status.lane, stamp)}\n\n"
        f"The `{status.lane}` lane is overdue: {_describe(status, ctx.now)}.\n\n"
        f"Check the Routine (enabled, GitHub connection alive), the publication workflow and the sealed-but-unpublished "
        f"handoffs on the health status (#{ctx.health_issue}). A manual run does not count. This issue closes when a "
        f"new verified scheduled record for the lane is published; see `{_RUNBOOK}` §5 and §7."
    )


def _open_by_lane(ctx: MissedRunContext) -> dict[str, list[Issue]]:
    """Publisher-authored open missed-run issues by lane, lowest number first (A14)."""
    by_lane: dict[str, list[Issue]] = {}
    for issue in ctx.tracker.list_issues(ctx.label, state="open"):
        lane = markers.lane_of_missed_run_issue(issue.body)
        if lane and issue.author == ctx.identity:
            by_lane.setdefault(lane, []).append(issue)
    return {lane: sorted(issues, key=lambda i: i.number) for lane, issues in by_lane.items()}


def _post(ctx: MissedRunContext, issue: int, body: str) -> None:
    markers.require_publisher("comment", ctx.tracker.create_comment(issue, body).author, ctx.identity)


def _close_extras(ctx: MissedRunContext, issues: list[Issue], kept: int) -> None:
    marker = markers.missed_run_duplicate(kept)
    for extra in (i for i in issues if i.number != kept):
        if markers.find_marked_comment(ctx.tracker.list_comments(extra.number), marker, ctx.identity) is None:
            _post(ctx, extra.number, f"{marker}\n\nDuplicate of #{kept} (one open missed-run issue per lane). Closing.")
        ctx.tracker.close_issue(extra.number)


def _notice_due(ctx: MissedRunContext, issue: Issue, lane: str) -> bool:
    """At most one comment per interval, measured from the last stamp the publisher itself wrote."""
    texts = [issue.body, *(c.body for c in ctx.tracker.list_comments(issue.number) if c.author == ctx.identity)]
    stamps = [parse_instant(s) for text in texts for s in markers.notice_stamps(text, lane)]
    last = max((s for s in stamps if s is not None), default=None)
    return last is None or ctx.now - last >= ctx.interval


def _resolve(ctx: MissedRunContext, status: LaneStatus, issue: Issue) -> None:
    record = status.record
    marker = markers.missed_run_resolved(status.lane, record["run_id"])
    if markers.find_marked_comment(ctx.tracker.list_comments(issue.number), marker, ctx.identity) is None:
        _post(
            ctx, issue.number,
            f"{marker}\n\nA verified scheduled record was published: run `{record['run_id']}` finished "
            f"{record['finished_at']}. The `{status.lane}` lane is within its {status.max_gap_hours} h gap again. Closing.",
        )
    ctx.tracker.close_issue(issue.number)


def _open_or_comment(ctx: MissedRunContext, status: LaneStatus, issues: list[Issue]) -> tuple[int, str]:
    if not issues:
        created = ctx.tracker.create_issue(
            title=f"Benchmark missed run: {status.lane} lane overdue", body=_issue_body(ctx, status), labels=[ctx.label]
        )
        markers.require_publisher("issue", created.author, ctx.identity)
        listed = _open_by_lane(ctx).get(status.lane) or [created]
        kept = listed[0].number
        _close_extras(ctx, listed, kept)
        return kept, "opened" if kept == created.number else "duplicate-closed"
    kept = issues[0]
    _close_extras(ctx, issues, kept.number)
    if not _notice_due(ctx, kept, status.lane):
        return kept.number, "overdue"
    stamp = markers.missed_run_notice(status.lane, format_instant(ctx.now))
    _post(ctx, kept.number, f"{stamp}\n\nStill overdue (`{status.lane}`): {_describe(status, ctx.now)}.")
    return kept.number, "commented"


def reconcile_missed_runs(ctx: MissedRunContext, statuses: list[LaneStatus]) -> dict[str, tuple[int | None, str]]:
    """Per lane: the open missed-run issue number after this pass, and what the pass did."""
    open_issues = _open_by_lane(ctx)
    result: dict[str, tuple[int | None, str]] = {}
    for status in statuses:
        issues = open_issues.get(status.lane, [])
        if status.reference is None:
            result[status.lane] = (issues[0].number if issues else None, "not-activated")
        elif status.overdue:
            result[status.lane] = _open_or_comment(ctx, status, issues)
        elif status.from_record:
            for issue in issues:
                _resolve(ctx, status, issue)
            result[status.lane] = (None, "closed" if issues else "on-schedule")
        else:
            result[status.lane] = (issues[0].number if issues else None, "awaiting-first-run")
    return result


def _state(status: LaneStatus) -> str:
    if status.overdue:
        return "OVERDUE"
    if status.reference is None:
        return health.NOT_ACTIVATED
    if status.from_record:
        return "on schedule"
    return f"awaiting first scheduled run (expected from {format_instant(status.expected_from)})"


def _row(status: LaneStatus, issue: int | None) -> health.LaneRow:
    record = status.record
    if record is None:
        return health.LaneRow(status.lane, _state(status), status.max_gap_hours, missed_run_issue=issue)
    return health.LaneRow(
        status.lane, _state(status), status.max_gap_hours, record["run_id"],
        record["finished_at"], markers.neutralize(record["runtime"]["model_id"], 80), render.drift_summary(record), issue,
    )


def run_watchdog(ports: Ports, config: WatchdogConfig) -> WatchdogReport:
    """Reconcile the missed-run issues, then refresh the health-status comment. Fails closed before any write."""
    report = WatchdogReport(identity=config.identity)
    manifest = config.manifest
    try:
        preflight(manifest, ports.tracker)
        now, labels = config.clock(), manifest_labels(manifest)
        statuses = [
            lane_status(ports.store, lane, spec["max_gap_hours"], expected_from(lane, spec["expected_from"]), now)
            for lane, spec in manifest["lanes"].items()
        ]
        ctx = MissedRunContext(
            ports.tracker, config.identity, labels["missed-run"],
            timedelta(hours=manifest["watchdog"]["missed_run_comment_interval_hours"]), now, manifest["health_issue"],
        )
        missed = reconcile_missed_runs(ctx, statuses)
        report.lanes = [
            {
                "lane": s.lane, "action": missed[s.lane][1], "overdue": s.overdue, "missed_run_issue": missed[s.lane][0],
                "expected_from": format_instant(s.expected_from) if s.expected_from else None,
                "latest_run_id": s.record["run_id"] if s.record else None,
                "finished_at": s.record["finished_at"] if s.record else None,
            }
            for s in statuses
        ]
        report.health = _refresh_health(ports, config, statuses, missed, now)
    except PublicationFailure as exc:
        report.aborted = str(exc)
    return report


def _refresh_health(
    ports: Ports, config: WatchdogConfig, statuses: list[LaneStatus], missed: Mapping[str, tuple[int | None, str]], now: datetime
) -> dict[str, Any]:
    manifest, tracker = config.manifest, ports.tracker
    open_drift = sum(
        1 for i in tracker.list_issues(manifest_labels(manifest)["drift"], state="open")
        if i.author == config.identity and markers.fingerprint_of_issue_body(i.body)
    )
    pending = health.pending_handoffs(ports.reader, ports.store, manifest["publication"]["staging_ref_pattern"].rstrip("*"))
    issue = manifest["health_issue"]
    existing = health.find_status(tracker.list_comments(issue), config.identity)
    last_sweep = format_instant(now) if config.sweep_succeeded else health.previous_sweep(existing)
    open_missed = sum(1 for number, _ in missed.values() if number is not None)
    body = health.render_status(
        [_row(s, missed[s.lane][0]) for s in statuses], open_drift, open_missed, pending, last_sweep, now
    )
    return {
        "action": health.publish(tracker, issue, config.identity, existing, body),
        "open_drift_issues": open_drift, "open_missed_run_issues": open_missed,
        "pending_handoffs": pending.count, "last_successful_sweep": last_sweep,
    }
