"""Hidden idempotency markers and the publisher-authorship rule (A14)."""

from __future__ import annotations

import re
from typing import Iterable

from runtime_platform.benchmark.publisher.ports import Comment, FatalPublicationError

REGRESSION_MARKER_RE = re.compile(r"^<!-- benchmark-regression:([0-9a-f]{64}) -->$")
_MAX_TEXT = 600


def regression_marker(fingerprint: str) -> str:
    return f"<!-- benchmark-regression:{fingerprint} -->"


def run_marker(run_id: str) -> str:
    return f"<!-- benchmark-run:{run_id} -->"


def applied_marker(run_id: str, fingerprint: str) -> str:
    return f"<!-- benchmark-applied:{run_id}:{fingerprint} -->"


def fingerprint_of_issue_body(body: str) -> str | None:
    """The fingerprint carried by the issue body's first-line marker."""
    first_line = (body or "").lstrip().split("\n", 1)[0].strip()
    match = REGRESSION_MARKER_RE.match(first_line)
    return match.group(1) if match else None


HEALTH_MARKER = "<!-- benchmark-health-status -->"
_MISSED_RUN_RE = re.compile(r"^<!-- benchmark-missed-run:([a-z]+) -->$")
_NOTICE_RE = re.compile(r"<!-- benchmark-missed-run-notice:([a-z]+):(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ) -->")


def missed_run_marker(lane: str) -> str:
    return f"<!-- benchmark-missed-run:{lane} -->"


def missed_run_notice(lane: str, stamp: str) -> str:
    """Stamps each post so "at most once a day" is measured from what the publisher itself wrote."""
    return f"<!-- benchmark-missed-run-notice:{lane}:{stamp} -->"


def missed_run_resolved(lane: str, run_id: str) -> str:
    return f"<!-- benchmark-missed-run-resolved:{lane}:{run_id} -->"


def lane_of_missed_run_issue(body: str) -> str | None:
    first_line = (body or "").lstrip().split("\n", 1)[0].strip()
    match = _MISSED_RUN_RE.match(first_line)
    return match.group(1) if match else None


def notice_stamps(text: str, lane: str) -> list[str]:
    return [stamp for found_lane, stamp in _NOTICE_RE.findall(text or "") if found_lane == lane]


def require_publisher(kind: str, author: str, identity: str) -> None:
    if author != identity:
        raise FatalPublicationError(f"{kind} was authored by {author!r}, not the publisher identity {identity!r}")


def publisher_login(app_slug: str) -> str:
    return f"{app_slug}[bot]"


def find_marked_comment(comments: Iterable[Comment], marker: str, identity: str) -> Comment | None:
    """A comment counts only when the publisher identity authored it; any other author is data."""
    return next((c for c in comments if c.author == identity and marker in c.body), None)


def neutralize(text: str, limit: int = _MAX_TEXT) -> str:
    """Untrusted record text must never carry a marker, an HTML comment opener, or a code fence."""
    return text.replace("<!--", "&lt;!--").replace("```", "'" * 3)[:limit]
