"""The health-status comment: gathering the sealed-but-unpublished handoffs, rendering, and edit-in-place.

Contract: `runtime_platform/benchmark/publication-cli.md` §7.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from runtime_platform.benchmark.publisher import markers
from runtime_platform.benchmark.publisher.layout import receipt_path, run_id_from_ref
from runtime_platform.benchmark.publisher.model import format_instant, parse_instant
from runtime_platform.benchmark.publisher.ports import Comment, HandoffReader, HistoryStore, IssueTracker
from runtime_platform.benchmark.publisher.validation import parse_handoff

_LAST_SWEEP_RE = re.compile(r"^- Last successful publication sweep: (\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)$", re.MULTILINE)
NO_SCHEDULED_RUN = "no verified scheduled run published yet"
_NOT_REPORTED = "not reported"


@dataclass(frozen=True)
class LaneRow:
    lane: str
    state: str
    max_gap_hours: int
    run_id: str | None = None
    finished_at: str | None = None
    model: str | None = None
    drift: str | None = None
    missed_run_issue: int | None = None


@dataclass(frozen=True)
class Pending:
    """Staging refs whose run has no receipt; the age is the oldest readable `sealed_at`."""

    count: int
    oldest_sealed: datetime | None
    unknown_age: int


def pending_handoffs(reader: HandoffReader, store: HistoryStore, prefix: str) -> Pending:
    count, unknown, oldest = 0, 0, None
    for ref in reader.list_staging_refs(prefix):
        run_id = run_id_from_ref(ref.name)
        if run_id is not None and store.read_file(receipt_path(run_id)) is not None:
            continue
        count += 1
        data = reader.read_handoff(ref)
        record = parse_handoff(data)[0] if data is not None else None
        sealed = parse_instant((record or {}).get("sealed_at"))
        if sealed is None:
            unknown += 1
        elif oldest is None or sealed < oldest:
            oldest = sealed
    return Pending(count, oldest, unknown)


def _cell(text: object) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def _pending_line(pending: Pending, now: datetime) -> str:
    if pending.count == 0:
        return "none"
    parts = [str(pending.count)]
    if pending.oldest_sealed is not None:
        hours = max(0, int((now - pending.oldest_sealed).total_seconds() // 3600))
        parts.append(f"oldest sealed {format_instant(pending.oldest_sealed)} ({hours} h ago)")
    if pending.unknown_age:
        parts.append(f"{pending.unknown_age} with no readable seal time")
    return " — ".join(parts)


def _row(row: LaneRow) -> str:
    issue = f"#{row.missed_run_issue}" if row.missed_run_issue else "—"
    if row.run_id is None:
        return f"| `{row.lane}` | {row.state} | — | — | — | — | {row.max_gap_hours} h | {issue} |"
    cells = [f"`{row.lane}`", row.state, f"`{row.run_id}`", row.finished_at, f"`{_cell(row.model)}`", _cell(row.drift), f"{row.max_gap_hours} h", issue]
    return "| " + " | ".join(str(c) for c in cells) + " |"


def render_status(
    rows: Sequence[LaneRow], open_drift: int, open_missed_run: int, pending: Pending, last_sweep: str | None, now: datetime
) -> str:
    """Only facts appear, never "as of": the comment is edited when a fact changes, not on every pass."""
    table = [
        "| Lane | State | Latest verified scheduled run | Finished (UTC) | Model | Drift outcome | Max gap | Missed-run issue |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        *[_row(row) for row in rows],
    ]
    lines = [
        f"{markers.HEALTH_MARKER}\n",
        "**Scheduled benchmark health**\n",
        *table,
        "",
        f"- Open drift issues: {open_drift}",
        f"- Open missed-run issues: {open_missed_run}",
        f"- Sealed but unpublished handoffs: {_pending_line(pending, now)}",
        f"- Last successful publication sweep: {last_sweep or _NOT_REPORTED}",
        "",
        "Edited in place by the publisher identity, and only when a fact above changes.",
    ]
    return "\n".join(lines)


def find_status(comments: Sequence[Comment], identity: str) -> Comment | None:
    """The oldest status comment the publisher identity authored; a foreign copy is data, never edited."""
    mine = [c for c in comments if c.author == identity and c.body.lstrip().split("\n", 1)[0].strip() == markers.HEALTH_MARKER]
    return min(mine, key=lambda c: c.id, default=None)


def previous_sweep(existing: Comment | None) -> str | None:
    match = _LAST_SWEEP_RE.search(existing.body) if existing is not None else None
    return match.group(1) if match else None


def _normalized(body: str) -> str:
    return body.replace("\r\n", "\n").strip()


def publish(tracker: IssueTracker, issue: int, identity: str, existing: Comment | None, body: str) -> str:
    """Create the status comment, edit it in place, or leave it: `created`, `edited`, or `unchanged`."""
    if existing is None:
        markers.require_publisher("health-status comment", tracker.create_comment(issue, body).author, identity)
        return "created"
    if _normalized(existing.body) == _normalized(body):
        return "unchanged"
    markers.require_publisher("health-status comment", tracker.update_comment(existing.id, body).author, identity)
    return "edited"
