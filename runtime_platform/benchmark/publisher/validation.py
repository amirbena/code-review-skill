"""The acceptance gates of `execution-publication-boundary.md` §2: refuse and report, never repair."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from runtime_platform.benchmark.publisher.layout import run_id_from_ref, staging_ref_name
from runtime_platform.benchmark.publisher.ports import RefActivity, StagingRef
from runtime_platform.benchmark.scripts.benchmark_result import (
    RESULT_SCHEMA_ID,
    RESULT_SCHEMA_PATH,
    content_sha256,
    load_schema,
    parse_run_id,
    validate_against_schema,
    validate_record,
)

MAX_HANDOFF_BYTES = 10 * 1024 * 1024
_MAX_LISTED_ERRORS = 3


@dataclass(frozen=True)
class Refusal:
    gate: str
    reason: str

    def as_dict(self) -> dict[str, str]:
        return {"gate": self.gate, "reason": self.reason}


def parse_handoff(data: bytes) -> tuple[dict[str, Any] | None, Refusal | None]:
    """Sealed bytes are parsed as data only; nothing in them is evaluated."""
    if len(data) > MAX_HANDOFF_BYTES:
        return None, Refusal("schema", f"handoff file exceeds {MAX_HANDOFF_BYTES} bytes")
    try:
        record = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        return None, Refusal("schema", f"handoff file is not valid JSON: {exc}")
    if not isinstance(record, dict):
        return None, Refusal("schema", "handoff file is not a JSON object")
    return record, None


def _listed(errors: Sequence[str]) -> str:
    extra = len(errors) - _MAX_LISTED_ERRORS
    shown = "; ".join(errors[:_MAX_LISTED_ERRORS])
    return shown + (f"; and {extra} more" if extra > 0 else "")


def check_record(record: Mapping[str, Any], ref: StagingRef, lanes: Sequence[str]) -> Refusal | None:
    """Gates 1-4, plus the ref-to-record identity binding."""
    if record.get("schema") != RESULT_SCHEMA_ID:
        return Refusal("schema", f"unknown schema version {record.get('schema')!r}")
    schema_errors = validate_against_schema(record, load_schema(RESULT_SCHEMA_PATH))
    if schema_errors:
        return Refusal("schema", _listed(schema_errors))
    if record["content_sha256"] != content_sha256(record):
        return Refusal("content-hash", "content_sha256 does not match the record body")
    if not record["verification"]["overall_verified"]:
        return Refusal("verification", "verification.overall_verified is not true")
    if record["lane"] not in lanes or parse_run_id(record["run_id"]) is None:
        return Refusal("provenance", f"lane {record['lane']!r} or run_id is not a scheduled identity")
    baseline_run_id = record["baseline"]["run_id"]
    if baseline_run_id is not None and baseline_run_id.split("-", 1)[0] != record["lane"]:
        return Refusal("baseline", "baseline.run_id belongs to a different lane: a cross-lane comparison is never published")
    if run_id_from_ref(ref.name) != record["run_id"] or ref.name != staging_ref_name(record["run_id"]):
        return Refusal("provenance", "staging ref name does not encode the record's run_id")
    errors = validate_record(record)
    return Refusal("conformance", _listed(errors)) if errors else None


def attest_origin(
    ref: StagingRef,
    activities: Sequence[RefActivity] | None,
    allowlist: Sequence[str],
    *,
    accept_unattributed: bool,
) -> Refusal | None:
    """Gate 5: server-side attribution of the ref's creation; commit author metadata is never used."""
    wanted = f"refs/heads/{ref.name}"
    relevant = [a for a in (activities or ()) if a.ref == wanted]
    if not relevant:
        if accept_unattributed:
            return None
        return Refusal("origin", "server-side attribution is unavailable for the ref; dispatch the run_id to accept it")
    creations = [a for a in relevant if a.activity_type == "branch_creation"]
    if not any(a.actor_login in allowlist and a.after == ref.sha for a in creations):
        return Refusal("origin", "no branch_creation of this ref at the fetched SHA by an allowlisted pusher")
    return None
