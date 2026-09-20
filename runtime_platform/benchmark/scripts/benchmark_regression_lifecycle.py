#!/usr/bin/env python3
"""GitHub issue lifecycle for classified drift (Issue #339), split out of `benchmark_drift.py`.

Publication-side code: it holds the only `gh` mutation path, so execution-side
modules must never import it (enforced by a policy test). Superseded by the
publication CLI of Issue #471.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.scripts.benchmark_drift import (  # noqa: E402
    KEEP_OPEN_LABEL,
    REGRESSION_LABEL,
    DriftRecord,
    _load_case_metrics_and_severity,
    classify_drift,
)

MAX_ISSUE_LIST_LIMIT = 6400  # safety ceiling on list_labeled_issues's doubling retry

_MARKER_PREFIX = "<!-- benchmark-regression:"
_MARKER_SUFFIX = " -->"
_MARKER_RE = re.compile(re.escape(_MARKER_PREFIX) + r"([0-9a-f]{64})" + re.escape(_MARKER_SUFFIX))


def marker_for(fp: str) -> str:
    return f"{_MARKER_PREFIX}{fp}{_MARKER_SUFFIX}"


def extract_fingerprint(issue_body: str) -> str | None:
    """The §4.1 match key: a hidden HTML-comment marker, never free text."""
    match = _MARKER_RE.search(issue_body or "")
    return match.group(1) if match else None


@dataclass(frozen=True)
class RunIdentity:
    date: str
    repo_sha: str


@dataclass(frozen=True)
class IssueRecord:
    number: int
    body: str
    labels: tuple[str, ...]


class GitHubIssueClient(Protocol):
    """The thin, injectable GitHub-mutation boundary (contract §6)."""

    def list_labeled_issues(self, label: str, *, state: str = "open") -> list[IssueRecord]: ...

    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> IssueRecord: ...

    def comment(self, issue_number: int, body: str) -> None: ...

    def close(self, issue_number: int, body: str) -> None: ...


class GhCliIssueClient:
    """Real client: shells out to `gh`, mirroring
    `run_benchmark_routine.py::_post_evidence`'s temp-file-body pattern."""

    def _gh(self, *args: str) -> str:
        proc = subprocess.run(["gh", *args], capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"gh {' '.join(args)} failed: {proc.stderr.strip()}")
        return proc.stdout.strip()

    def _with_body_file(self, body: str, *args: str) -> str:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
            handle.write(body)
            path = handle.name
        try:
            return self._gh(*args, "--body-file", path)
        finally:
            Path(path).unlink(missing_ok=True)

    def list_labeled_issues(self, label: str, *, state: str = "open") -> list[IssueRecord]:
        # `--limit N` caps total results, not per page, so retry with a
        # doubling limit until a response is smaller than requested.
        limit = 200
        while True:
            raw = self._gh(
                "issue", "list", "--label", label, "--state", state,
                "--json", "number,body,labels", "--limit", str(limit),
            )
            items = json.loads(raw) if raw else []
            if len(items) < limit:
                break
            limit *= 2
            if limit > MAX_ISSUE_LIST_LIMIT:
                raise RuntimeError(
                    f"gh issue list --label {label} still returned a full page "
                    f"past --limit {MAX_ISSUE_LIST_LIMIT}; refusing to keep doubling."
                )
        return [
            IssueRecord(
                number=item["number"],
                body=item.get("body") or "",
                labels=tuple(entry["name"] for entry in item.get("labels", [])),
            )
            for item in items
        ]

    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> IssueRecord:
        args = ["issue", "create", "--title", title]
        for label in labels:
            args += ["--label", label]
        url = self._with_body_file(body, *args)
        number = int(url.rstrip("/").rsplit("/", 1)[-1])
        return IssueRecord(number=number, body=body, labels=tuple(labels))

    def comment(self, issue_number: int, body: str) -> None:
        self._with_body_file(body, "issue", "comment", str(issue_number))

    def close(self, issue_number: int, body: str) -> None:
        self.comment(issue_number, body)
        self._gh("issue", "close", str(issue_number))


@dataclass(frozen=True)
class SyncOutcome:
    opened: tuple[str, ...]
    commented: tuple[str, ...]
    closed: tuple[str, ...]
    kept_open: tuple[str, ...]

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "opened": list(self.opened),
            "commented": list(self.commented),
            "closed": list(self.closed),
            "kept_open": list(self.kept_open),
        }


def _metadata_block(record: DriftRecord, fp: str, baseline: RunIdentity, candidate: RunIdentity, now: str) -> str:
    payload = {
        "fingerprint": fp,
        "case_id": record.case_id,
        "drift_type": record.drift_type,
        "expected_finding_key": record.expected_finding_key,
        "baseline": {"date": baseline.date, "repo_sha": baseline.repo_sha},
        "candidate": {"date": candidate.date, "repo_sha": candidate.repo_sha},
        "detected_at": now,
    }
    return "```json\n" + json.dumps(payload, indent=2, sort_keys=True) + "\n```"


def sync_regressions(
    drift_records: Sequence[DriftRecord],
    client: GitHubIssueClient,
    *,
    baseline: RunIdentity,
    candidate: RunIdentity,
    now: str | None = None,
) -> SyncOutcome:
    """The §4 lifecycle: open once per new fingerprint, comment on
    recurrence, auto-comment-and-close on resolution unless `keep-open`
    overrides it (§4.4). Never touches an issue whose fingerprint does not
    come from `drift_records` — noise never reaches this function at all."""
    now = now or datetime.now(timezone.utc).isoformat()
    current_by_fp = {record.fingerprint: record for record in drift_records}

    tracked: dict[str, IssueRecord] = {}
    for issue in client.list_labeled_issues(REGRESSION_LABEL, state="open"):
        fp = extract_fingerprint(issue.body)
        if fp:
            tracked[fp] = issue

    opened: list[str] = []
    commented: list[str] = []
    closed: list[str] = []
    kept_open: list[str] = []

    for fp, record in current_by_fp.items():
        metadata = _metadata_block(record, fp, baseline, candidate, now)
        if fp in tracked:
            body = f"Regression still reproduces as of {now}.\n\n{record.detail}\n\n{metadata}"
            client.comment(tracked[fp].number, body)
            commented.append(fp)
        else:
            title = f"Benchmark drift: {record.case_id} — {record.drift_type}"
            body = f"{marker_for(fp)}\n\n{record.detail}\n\n{metadata}"
            client.create_issue(title=title, body=body, labels=[REGRESSION_LABEL])
            opened.append(fp)

    for fp, issue in tracked.items():
        if fp in current_by_fp:
            continue
        if KEEP_OPEN_LABEL in issue.labels:
            kept_open.append(fp)
            continue
        body = f"No longer reproduces as of {now} (baseline {baseline.date}/{baseline.repo_sha}, candidate {candidate.date}/{candidate.repo_sha}). Closing."
        client.close(issue.number, body)
        closed.append(fp)

    return SyncOutcome(tuple(opened), tuple(commented), tuple(closed), tuple(kept_open))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sync = sub.add_parser("sync", help="Run the GitHub issue lifecycle for the classified drift.")
    sync.add_argument("--baseline-file", required=True, type=Path)
    sync.add_argument("--candidate-file", required=True, type=Path)
    sync.add_argument("--baseline-date", required=True)
    sync.add_argument("--baseline-sha", required=True)
    sync.add_argument("--candidate-date", required=True)
    sync.add_argument("--candidate-sha", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    base_metrics, base_sev = _load_case_metrics_and_severity(args.baseline_file)
    cand_metrics, cand_sev = _load_case_metrics_and_severity(args.candidate_file)
    records = classify_drift(base_metrics, cand_metrics, base_sev, cand_sev)
    outcome = sync_regressions(
        records,
        GhCliIssueClient(),
        baseline=RunIdentity(args.baseline_date, args.baseline_sha),
        candidate=RunIdentity(args.candidate_date, args.candidate_sha),
    )
    print(json.dumps(outcome.as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
