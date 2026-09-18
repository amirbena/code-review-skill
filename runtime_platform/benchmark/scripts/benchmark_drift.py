#!/usr/bin/env python3
"""Drift detection and regression issue lifecycle (Issue #339).

Full contract: `runtime_platform/benchmark/drift-detection-and-regression-lifecycle.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Reused, not reinvented (see the contract doc §1): `tests/reference/benchmark`
# is the only executable projection of #53/#54/#55/#56/#57 today.
from runtime_platform.benchmark.reference import benchmark_metrics as bmet  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_severity as bsev  # noqa: E402

# --------------------------------------------------------------------------
# Meaningful drift vs. noise (contract §2).
# --------------------------------------------------------------------------

DRIFT_MISSED_REQUIRED_FINDING = "missed-required-finding"
DRIFT_DECISION_FLIP = "decision-flip"
DRIFT_SEVERITY_ACCURACY_DROP = "severity-accuracy-drop"

# Sentinel `expected_finding_key` for a case-level (not per-finding) drift_type.
CASE_LEVEL_FINDING_KEY = "-"

# More than a 20-percentage-point exact-rate drop is meaningful; at or below
# absorbs single-run flakiness in a small matched set (contract §2).
DEFAULT_SEVERITY_EXACT_RATE_TOLERANCE = Fraction(1, 5)


@dataclass(frozen=True)
class DriftRecord:
    case_id: str
    drift_type: str
    expected_finding_key: str
    detail: str

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.case_id, self.drift_type, self.expected_finding_key)

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "drift_type": self.drift_type,
            "expected_finding_key": self.expected_finding_key,
            "detail": self.detail,
            "fingerprint": self.fingerprint,
        }


def fingerprint(case_id: str, drift_type: str, expected_finding_key: str) -> str:
    """Stable identity for a regression (contract §3): sha256 of the
    canonical `{case_id, drift_type, expected_finding_key}` triple, built
    from the fields directly so a caller's key ordering/whitespace never
    changes the result."""
    canonical = json.dumps(
        {
            "case_id": case_id,
            "drift_type": drift_type,
            "expected_finding_key": expected_finding_key,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def classify_drift(
    baseline_metrics: Mapping[str, bmet.CaseMetrics],
    candidate_metrics: Mapping[str, bmet.CaseMetrics],
    baseline_severity: Mapping[str, bsev.CaseSeverityAccuracy],
    candidate_severity: Mapping[str, bsev.CaseSeverityAccuracy],
    *,
    severity_exact_rate_tolerance: Fraction = DEFAULT_SEVERITY_EXACT_RATE_TOLERANCE,
) -> list[DriftRecord]:
    """The §2 policy, applied per case. Cases present in only one run, and
    every noise example the contract lists, never reach a `DriftRecord`."""
    records: list[DriftRecord] = []

    for case_id in sorted(set(baseline_metrics) & set(candidate_metrics)):
        base, cand = baseline_metrics[case_id], candidate_metrics[case_id]

        newly_missed = sorted(set(cand.missed_keys) - set(base.missed_keys))
        for key in newly_missed:
            records.append(
                DriftRecord(
                    case_id,
                    DRIFT_MISSED_REQUIRED_FINDING,
                    key,
                    f"required finding '{key}' was matched in the baseline and is now missed",
                )
            )

        if not base.missed_keys and cand.missed_keys:
            records.append(
                DriftRecord(
                    case_id,
                    DRIFT_DECISION_FLIP,
                    CASE_LEVEL_FINDING_KEY,
                    "case satisfied every required finding in the baseline and no longer does",
                )
            )

    for case_id in sorted(set(baseline_severity) & set(candidate_severity)):
        base_sev, cand_sev = baseline_severity[case_id], candidate_severity[case_id]
        base_rate, cand_rate = base_sev.exact_rate, cand_sev.exact_rate
        if base_rate is None or cand_rate is None:
            continue  # undefined rate (nothing matched) is not comparable.
        if base_rate - cand_rate > severity_exact_rate_tolerance:
            records.append(
                DriftRecord(
                    case_id,
                    DRIFT_SEVERITY_ACCURACY_DROP,
                    CASE_LEVEL_FINDING_KEY,
                    f"severity exact-match rate dropped from {base_rate} to {cand_rate}",
                )
            )

    return sorted(records, key=lambda r: (r.case_id, r.drift_type, r.expected_finding_key))


# --------------------------------------------------------------------------
# GitHub issue lifecycle (contract §4-§6).
# --------------------------------------------------------------------------

REGRESSION_LABEL = "benchmark-regression"
KEEP_OPEN_LABEL = "keep-open"
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


def _load_case_metrics_and_severity(
    path: Path,
) -> tuple[dict[str, bmet.CaseMetrics], dict[str, bsev.CaseSeverityAccuracy]]:
    """`path` is a pre-computed per-case metrics/severity JSON file, the
    shape a caller (e.g. a nightly Routine step) is expected to produce by
    running #55/#56 over #338's history entries before invoking this CLI —
    this CLI never re-runs the reviewer or the matcher itself."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    metrics = {
        row["id"]: bmet.CaseMetrics(
            id=row["id"],
            status=row["status"],
            findings_completeness=row["findings_completeness"],
            false_negatives=row["false_negatives"],
            false_positives=row["false_positives"],
            missed_keys=tuple(row["missed_keys"]),
            incorrect_indices=tuple(row["incorrect_indices"]),
            near_misses=row["near_misses"],
            absorbed_extra_match=row["absorbed_extra_match"],
            tolerated_unexpected=row["tolerated_unexpected"],
        )
        for row in raw["metrics"]
    }
    severity = {
        row["id"]: bsev.CaseSeverityAccuracy(
            id=row["id"],
            status=row["status"],
            matched=row["matched"],
            severity_exact=row["severity_exact"],
            over_severity=row["over_severity"],
            under_severity=row["under_severity"],
            mismatches=tuple(row.get("mismatches", ())),
        )
        for row in raw["severity"]
    }
    return metrics, severity


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    detect = sub.add_parser("detect", help="Classify drift between a baseline and candidate metrics/severity file.")
    detect.add_argument("--baseline-file", required=True, type=Path)
    detect.add_argument("--candidate-file", required=True, type=Path)

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

    if args.command == "detect":
        print(json.dumps([r.as_dict() for r in records], indent=2))
        return 0

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
