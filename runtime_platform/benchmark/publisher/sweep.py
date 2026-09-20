"""`sweep`: validate, persist, reconcile, announce, and receipt every unpublished sealed ref.

Contract: `runtime_platform/benchmark/publication-cli.md`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from runtime_platform.benchmark.publisher import history, lifecycle, markers, render
from runtime_platform.benchmark.publisher.layout import encode_json, receipt_path, record_path, run_id_from_ref
from runtime_platform.benchmark.publisher.model import (
    ALREADY_PUBLISHED,
    FAILED,
    PUBLISHED,
    REFUSED,
    Ports,
    RunOutcome,
    SweepConfig,
    SweepReport,
)
from runtime_platform.benchmark.publisher.ports import (
    FatalPublicationError,
    IssueTracker,
    PathExistsError,
    PublicationFailure,
    StagingRef,
)
from runtime_platform.benchmark.publisher.validation import Refusal, attest_origin, check_record, parse_handoff
from runtime_platform.benchmark.scripts.benchmark_result import validate_receipt
from runtime_platform.benchmark.scripts.benchmark_schedule_manifest import validate_manifest

STAGING_RETENTION_DAYS = 30
STEPS = ("validate", "persist", "reconcile", "announce", "receipt")


@dataclass(frozen=True)
class _Candidate:
    ref: StagingRef
    run_id: str | None
    record: dict[str, Any] | None
    refusal: Refusal | None


def _labels(manifest: Mapping[str, Any]) -> dict[str, str]:
    return {entry["role"]: entry["name"] for entry in manifest["labels"]}


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _preflight(config: SweepConfig, tracker: IssueTracker) -> None:
    """Fail closed before any write: a usable manifest and every required label."""
    errors = validate_manifest(config.manifest, require_provisioned=True)
    if errors:
        raise FatalPublicationError("manifest is not usable: " + "; ".join(errors))
    missing = tracker.missing_labels(sorted(_labels(config.manifest).values()))
    if missing:
        raise FatalPublicationError(f"required labels are missing (provisioning prerequisite): {', '.join(missing)}")


def _load_candidates(ports: Ports, config: SweepConfig, prefix: str) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for ref in ports.reader.list_staging_refs(prefix):
        run_id = run_id_from_ref(ref.name)
        if config.only_run_id is not None and run_id != config.only_run_id:
            continue
        if run_id is None:
            candidates.append(_Candidate(ref, None, None, Refusal("provenance", "ref name does not encode a valid run_id")))
            continue
        data = ports.reader.read_handoff(ref)
        if data is None:
            candidates.append(_Candidate(ref, run_id, None, Refusal("schema", "the ref carries no sealed result file")))
            continue
        record, refusal = parse_handoff(data)
        candidates.append(_Candidate(ref, run_id, record, refusal))
    return sorted(candidates, key=lambda c: (str((c.record or {}).get("sealed_at", "")), c.ref.name))


def _refused(candidate: _Candidate, refusal: Refusal) -> RunOutcome:
    return RunOutcome(candidate.ref.name, candidate.run_id, REFUSED, refusal.reason, refusal.gate)


def _issue_lines(reconciliation: lifecycle.Reconciliation) -> list[str]:
    lines = []
    for action in ("opened", "commented", "closed", "kept-open"):
        numbers = sorted(a.issue for a in reconciliation.actions if a.action == action)
        if numbers:
            lines.append(f"Issues {action}: " + ", ".join(f"#{n}" for n in numbers))
    if reconciliation.deferred:
        lines.append(f"{len(reconciliation.deferred)} confirmed drift(s) deferred by the new-issue cap; re-considered on the next run")
    return lines


def _announce(
    ports: Ports, config: SweepConfig, record: Mapping[str, Any], evidence: render.Evidence,
    reconciliation: lifecycle.Reconciliation, notes: list[str],
) -> str:
    tracking = config.manifest["lanes"][record["lane"]]["tracking_issue"]
    existing = markers.find_marked_comment(ports.tracker.list_comments(tracking), markers.run_marker(record["run_id"]), config.identity)
    if existing is not None:
        return existing.url
    if reconciliation.skipped and record["baseline"]["state"] != "bootstrap":
        notes = [*notes, reconciliation.skipped]
    posted = ports.tracker.create_comment(tracking, render.evidence_comment(record, evidence, _issue_lines(reconciliation), notes))
    if posted.author != config.identity:
        raise FatalPublicationError(f"evidence comment was authored by {posted.author!r}, not the publisher identity {config.identity!r}")
    return posted.url


def _write_receipt(
    ports: Ports, config: SweepConfig, record: Mapping[str, Any], commit: str, evidence_url: str,
    reconciliation: lifecycle.Reconciliation, now: str, steps: list[str],
) -> None:
    path = record_path(record["run_id"])
    receipt = {
        "schema": "benchmark-receipt/v1",
        "run_id": record["run_id"],
        "record_sha256": record["content_sha256"],
        "record_commit": commit,
        "record_permalink": ports.store.permalink(commit, path),
        "evidence_comment_url": evidence_url,
        "issue_links": [a.as_dict() for a in reconciliation.actions],
        "published_at": now,
        "publisher_identity": config.identity,
        "publisher_run_url": config.run_url,
        "steps_done": steps,
    }
    errors = validate_receipt(receipt)
    if errors:
        raise PublicationFailure("receipt does not conform to benchmark-receipt/v1: " + "; ".join(errors))
    try:
        ports.store.commit_files({receipt_path(record["run_id"]): encode_json(receipt)}, f"Receipt {record['run_id']}")
    except PathExistsError:
        pass


def _published(ports: Ports, config: SweepConfig, candidate: _Candidate, digest: str, receipt: bytes) -> RunOutcome:
    """A receipt exists: the run is done; delete its staging ref once the retention period has passed."""
    try:
        stored = json.loads(receipt.decode("utf-8"))
        published_at = datetime.strptime(stored["published_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, ValueError, TypeError):
        return RunOutcome(candidate.ref.name, candidate.run_id, REFUSED, "stored receipt is unreadable", "conflict")
    if stored.get("record_sha256") != digest:
        return RunOutcome(candidate.ref.name, candidate.run_id, REFUSED, "receipt names a different content hash", "conflict")
    if config.clock() - published_at >= timedelta(days=STAGING_RETENTION_DAYS):
        ports.store.delete_staging_ref(candidate.ref.name)
        return RunOutcome(candidate.ref.name, candidate.run_id, ALREADY_PUBLISHED, "staging ref deleted after retention")
    return RunOutcome(candidate.ref.name, candidate.run_id, ALREADY_PUBLISHED)


def _process(ports: Ports, config: SweepConfig, candidate: _Candidate) -> RunOutcome:
    if candidate.refusal is not None or candidate.record is None or candidate.run_id is None:
        return _refused(candidate, candidate.refusal or Refusal("schema", "no sealed result"))
    record, run_id = candidate.record, candidate.run_id
    refusal = check_record(record, candidate.ref, list(config.manifest["lanes"]))
    if refusal is not None:
        return _refused(candidate, refusal)

    digest = record["content_sha256"]
    existing = ports.store.read_file(record_path(run_id))
    receipt = ports.store.read_file(receipt_path(run_id))
    if existing is not None and not history.same_record(existing, digest):
        return _refused(candidate, Refusal("conflict", "history holds this run_id with a different content_sha256"))
    if receipt is not None:
        if existing is None:
            return _refused(candidate, Refusal("conflict", "a receipt exists without its record"))
        return _published(ports, config, candidate, digest, receipt)

    steps = list(STEPS) + (["local-once"] if config.local_once else [])
    if existing is None:
        activities = ports.reader.ref_activities(candidate.ref.name)
        refusal = attest_origin(
            candidate.ref, activities, config.manifest["publication"]["pusher_allowlist"],
            accept_unattributed=config.accept_unattributed,
        )
        if refusal is not None:
            return _refused(candidate, refusal)
        if not [a for a in activities or () if a.ref == f"refs/heads/{candidate.ref.name}"]:
            steps.append("origin-accepted-by-dispatch")
    baseline = history.load_baseline(ports.store, record)
    if isinstance(baseline, Refusal):
        return _refused(candidate, baseline)

    now = _timestamp(config.clock())
    commit = history.persist(ports.store, record, existing, config.identity, now)
    evidence = render.Evidence(record_permalink=ports.store.permalink(commit, record_path(run_id)), **baseline)

    views, superseded = history.lane_views(ports.store, record, list(config.manifest["lanes"]))
    notes: list[str] = []
    if superseded:
        reconciliation = lifecycle.Reconciliation(skipped="superseded by a newer published record of this lane: no drift issue is touched")
    else:
        labels = _labels(config.manifest)
        ctx = lifecycle.LifecycleContext(
            tracker=ports.tracker, identity=config.identity, regression_label=labels["drift"],
            keep_open_label=labels["keep-open"], max_new_issues=config.manifest["publication"]["max_new_issues_per_run"], now=now,
        )
        reconciliation = lifecycle.reconcile(ctx, record, views, evidence)
        if views is None:
            notes.append("another lane's latest record could not be loaded: no drift issue was closed")
    if record["baseline"]["state"] == "bootstrap":
        notes.append("first record of this lane: recorded as its baseline")

    evidence_url = _announce(ports, config, record, evidence, reconciliation, notes)
    _write_receipt(ports, config, record, commit, evidence_url, reconciliation, now, steps)
    return RunOutcome(
        candidate.ref.name, run_id, PUBLISHED, commit=commit,
        actions=[a.as_dict() for a in reconciliation.actions], deferred=reconciliation.deferred,
    )


def run_sweep(ports: Ports, config: SweepConfig) -> SweepReport:
    """Process every unpublished sealed ref in ascending `sealed_at`; a refusal never blocks the rest."""
    report = SweepReport(identity=config.identity)
    try:
        _preflight(config, ports.tracker)
        prefix = config.manifest["publication"]["staging_ref_pattern"].rstrip("*")
        candidates = _load_candidates(ports, config, prefix)
        if config.only_run_id is not None and not candidates:
            raise PublicationFailure(f"no staging ref for run_id {config.only_run_id}")
    except PublicationFailure as exc:
        report.aborted = str(exc)
        return report
    for candidate in candidates:
        try:
            report.outcomes.append(_process(ports, config, candidate))
        except FatalPublicationError as exc:
            report.outcomes.append(RunOutcome(candidate.ref.name, candidate.run_id, FAILED, str(exc)))
            report.aborted = str(exc)
            break
        except PublicationFailure as exc:
            report.outcomes.append(RunOutcome(candidate.ref.name, candidate.run_id, FAILED, str(exc)))
    return report
