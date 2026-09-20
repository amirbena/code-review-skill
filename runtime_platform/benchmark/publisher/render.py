"""Issue and comment bodies. Free text from a record passes through `neutralize`."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from runtime_platform.benchmark.publisher import markers


@dataclass(frozen=True)
class Evidence:
    """The commit-pinned links and baseline identity a post names."""

    record_permalink: str
    baseline_permalink: str | None
    baseline_run_id: str | None
    baseline_repo_sha: str | None
    baseline_date: str | None


def _attribution_note(record: Mapping[str, Any]) -> str:
    if record["drift"]["attribution"] == "runtime-changed":
        return "\n\nThe model or runtime version differs from the baseline's (`runtime-changed`); this may be a model change rather than a Skill change."
    return ""


def _links(evidence: Evidence) -> str:
    baseline = f" · [baseline record]({evidence.baseline_permalink})" if evidence.baseline_permalink else ""
    return f"[sealed record]({evidence.record_permalink}){baseline}"


def drift_metadata(record: Mapping[str, Any], drift: Mapping[str, Any], evidence: Evidence, now: str) -> str:
    payload = {
        "fingerprint": drift["fingerprint"],
        "case_id": drift["case_id"],
        "drift_type": drift["drift_type"],
        "expected_finding_key": drift["expected_finding_key"],
        "lane": record["lane"],
        "run_id": record["run_id"],
        "baseline": {
            "run_id": evidence.baseline_run_id,
            "date": evidence.baseline_date,
            "repo_sha": evidence.baseline_repo_sha,
        },
        "candidate": {
            "run_id": record["run_id"],
            "date": record["started_at"][:10],
            "repo_sha": record["provenance"]["repo_sha"],
        },
        "record_permalink": evidence.record_permalink,
        "baseline_permalink": evidence.baseline_permalink,
        "attribution": record["drift"]["attribution"],
        "detected_at": now,
    }
    text = json.dumps(payload, indent=2, sort_keys=True).replace("<!--", "\\u003c!--")
    return "```json\n" + text + "\n```"


def issue_title(drift: Mapping[str, Any]) -> str:
    return f"Benchmark drift: {markers.neutralize(drift['case_id'], 120)} — {drift['drift_type']}"


def issue_body(
    record: Mapping[str, Any], drift: Mapping[str, Any], evidence: Evidence, now: str, recurrence_of: int | None
) -> str:
    fingerprint = drift["fingerprint"]
    recurrence = f"Recurrence of #{recurrence_of}\n\n" if recurrence_of else ""
    return (
        f"{markers.regression_marker(fingerprint)}\n{markers.applied_marker(record['run_id'], fingerprint)}\n\n"
        f"{recurrence}{markers.neutralize(drift['detail'])}\n\n"
        f"Lane `{record['lane']}`, run `{record['run_id']}` — {_links(evidence)}"
        f"{_attribution_note(record)}\n\n{drift_metadata(record, drift, evidence, now)}"
    )


def recurrence_comment(
    record: Mapping[str, Any], drift: Mapping[str, Any], evidence: Evidence, now: str
) -> str:
    return (
        f"{markers.applied_marker(record['run_id'], drift['fingerprint'])}\n\n"
        f"Regression still reproduces as of {now}.\n\n{markers.neutralize(drift['detail'])}\n\n"
        f"Lane `{record['lane']}`, run `{record['run_id']}` — {_links(evidence)}"
        f"{_attribution_note(record)}\n\n{drift_metadata(record, drift, evidence, now)}"
    )


def resolution_comment(record: Mapping[str, Any], fingerprint: str, evidence: Evidence, now: str, covering: Sequence[str]) -> str:
    lanes = ", ".join(f"`{lane}`" for lane in covering)
    return (
        f"{markers.applied_marker(record['run_id'], fingerprint)}\n\n"
        f"No longer reproduces as of {now} in every scheduled lane that covers this case ({lanes}). Closing.\n\n"
        f"Latest run `{record['run_id']}` — {_links(evidence)}"
    )


def duplicate_pointer_comment(kept: int) -> str:
    return f"Duplicate of #{kept} (one open issue per fingerprint). Closing."


def _drift_summary(record: Mapping[str, Any]) -> str:
    drift = record["drift"]
    outcome = drift["outcome"]
    if outcome["status"] == "not-evaluated":
        return f"not evaluated ({markers.neutralize(outcome['reason'], 160)})"
    if outcome["status"] == "none":
        return f"none ({len(drift['unconfirmed'])} unconfirmed)"
    systemic = ", systemic" if drift["systemic"] else ""
    return f"drift — {len(drift['confirmed'])} confirmed, {len(drift['unconfirmed'])} unconfirmed{systemic}"


def evidence_comment(
    record: Mapping[str, Any],
    evidence: Evidence,
    issue_lines: Sequence[str],
    notes: Sequence[str],
) -> str:
    cases = record["cases"]
    executed = sum(1 for case in cases if case["status"] == "executed")
    baseline = record["baseline"]
    lines = [
        f"**Benchmark run `{record['run_id']}`** — lane `{record['lane']}`, trigger `{record['trigger']}`",
        f"- Repository SHA `{record['provenance']['repo_sha'][:12]}`, model `{markers.neutralize(record['runtime']['model_id'], 80)}`",
        f"- Cases executed: {executed}/{len(cases)}",
        f"- Baseline: {baseline['state']}" + (f" (`{baseline['run_id']}`)" if baseline["run_id"] else ""),
        f"- Drift: {_drift_summary(record)}",
        f"- {_links(evidence)}",
        *[f"- {line}" for line in issue_lines],
        *[f"- {note}" for note in notes],
    ]
    return f"{markers.run_marker(record['run_id'])}\n\n" + "\n".join(lines)
