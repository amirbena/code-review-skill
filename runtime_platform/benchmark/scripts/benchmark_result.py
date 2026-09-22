#!/usr/bin/env python3
"""Canonical `benchmark-result/v1` record: identity, sealing, and conformance validation.

Contract: `runtime_platform/benchmark/benchmark-result-schema.md`. Stores and checks a
sealed run; never runs the reviewer, evaluates drift, or persists to `benchmark-history`.

Usage::

    python3 runtime_platform/benchmark/scripts/benchmark_result.py validate record.json
    python3 runtime_platform/benchmark/scripts/benchmark_result.py validate --receipt receipt.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.scripts.benchmark_corpus_membership import canonical_lane  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_fingerprint import fingerprint  # noqa: E402

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"
RESULT_SCHEMA_PATH = SCHEMA_DIR / "benchmark-result-v1.schema.json"
RECEIPT_SCHEMA_PATH = SCHEMA_DIR / "benchmark-receipt-v1.schema.json"

RESULT_SCHEMA_ID = "benchmark-result/v1"
EVIDENCE_MAX_BYTES = 32 * 1024
FIXTURE_DIGEST_MISMATCH = "fixture-digest-mismatch"

_RUN_ID_RE = re.compile(r"^(sentinel|comprehensive)-(\d{8}T\d{6}Z)-([0-9a-f]{12})$")


# --------------------------------------------------------------------------
# Canonical JSON, hashing, identity.
# --------------------------------------------------------------------------


def canonical_json(value: Any) -> str:
    """The canonicalization `benchmark_fingerprint.fingerprint` uses: sorted keys, minimal separators."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_sha256(record: Mapping[str, Any]) -> str:
    """SHA-256 of the canonical-JSON sealed body (the record without `content_sha256`)."""
    body = {k: v for k, v in record.items() if k != "content_sha256"}
    return sha256_hex(canonical_json(body))


def seal_record(body: Mapping[str, Any]) -> dict[str, Any]:
    """Attach `content_sha256` to a sealed body; the record is immutable afterwards."""
    return {**body, "content_sha256": content_sha256(body)}


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def make_run_id(lane: str, started_at: str, repo_sha: str) -> str:
    """`<lane>-<YYYYMMDDTHHMMSSZ>-<repo_sha[:12]>` from the run's UTC start time."""
    return f"{lane}-{_parse_timestamp(started_at).strftime('%Y%m%dT%H%M%SZ')}-{repo_sha[:12]}"


def parse_run_id(run_id: str) -> tuple[str, str, str] | None:
    """`(lane, compact UTC start, sha12)`, or None when `run_id` is malformed."""
    match = _RUN_ID_RE.match(run_id)
    return match.groups() if match else None  # type: ignore[return-value]


def fixture_digest(fixture_path: Path) -> str:
    """Per-fixture content digest: the same file digest `corpus_id` is built from."""
    return hashlib.sha256(fixture_path.read_bytes()).hexdigest()


def membership_digest(case_ids: Sequence[str]) -> str:
    """Digest of a lane's membership: canonical JSON of its sorted case ids."""
    return sha256_hex(canonical_json(sorted(case_ids)))


# --------------------------------------------------------------------------
# Per-case comparability (A7).
# --------------------------------------------------------------------------


def partition_case_comparability(
    candidate_cases: Sequence[Mapping[str, Any]],
    baseline_cases: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Split one lane's cases by `fixture_digest`.

    A digest mismatch makes only that case incomparable; cases present on one
    side only are reported as added/removed and never block the comparison.
    """
    baseline_by_id = {c["id"]: c for c in baseline_cases}
    candidate_ids = {c["id"] for c in candidate_cases}
    comparable: list[str] = []
    incomparable: list[dict[str, str]] = []
    for case in sorted(candidate_cases, key=lambda c: c["id"]):
        base = baseline_by_id.get(case["id"])
        if base is None:
            continue
        if base["fixture_digest"] == case["fixture_digest"]:
            comparable.append(case["id"])
        else:
            incomparable.append(
                {
                    "id": case["id"],
                    "reason": FIXTURE_DIGEST_MISMATCH,
                    "baseline_fixture_digest": base["fixture_digest"],
                    "candidate_fixture_digest": case["fixture_digest"],
                }
            )
    return {
        "comparable_case_ids": comparable,
        "incomparable_cases": incomparable,
        "added_case_ids": sorted(candidate_ids - set(baseline_by_id)),
        "removed_case_ids": sorted(set(baseline_by_id) - candidate_ids),
    }


# --------------------------------------------------------------------------
# JSON Schema subset validator (stdlib only; keywords the two schemas use).
# --------------------------------------------------------------------------

_TYPE_CHECKS = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v),
}


def load_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(ref: str, root: Mapping[str, Any]) -> Mapping[str, Any]:
    node: Any = root
    for part in ref.removeprefix("#/").split("/"):
        node = node[part]
    return node


def _pattern_matches(pattern: str, text: str) -> bool:
    # ECMA `$` never matches before a trailing newline; Python's does.
    return re.search(re.sub(r"(?<!\\)\$$", r"\\Z", pattern), text) is not None


def _describe(value: Any) -> str:
    if isinstance(value, float) and not math.isfinite(value):
        return "a non-finite number"
    return type(value).__name__


def validate_against_schema(
    instance: Any, schema: Mapping[str, Any], root: Mapping[str, Any] | None = None, path: str = "$"
) -> list[str]:
    root = root if root is not None else schema
    if "$ref" in schema:
        return validate_against_schema(instance, _resolve(schema["$ref"], root), root, path)

    errors: list[str] = []
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected {schema['const']!r}, got {instance!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    if "type" in schema:
        allowed = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_TYPE_CHECKS[t](instance) for t in allowed):
            return errors + [f"{path}: expected type {allowed}, got {_describe(instance)}"]
    if "anyOf" in schema and not any(
        not validate_against_schema(instance, sub, root, path) for sub in schema["anyOf"]
    ):
        errors.append(f"{path}: matches none of the allowed shapes")
    for sub in schema.get("allOf", ()):
        errors.extend(validate_against_schema(instance, sub, root, path))

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errors.append(f"{path}: shorter than {schema['minLength']}")
        if len(instance) > schema.get("maxLength", len(instance)):
            errors.append(f"{path}: longer than {schema['maxLength']}")
        if "pattern" in schema and not _pattern_matches(schema["pattern"], instance):
            errors.append(f"{path}: does not match {schema['pattern']}")
    if _TYPE_CHECKS["number"](instance) and instance < schema.get("minimum", instance):
        errors.append(f"{path}: below minimum {schema['minimum']}")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if schema.get("uniqueItems") and len({canonical_json(i) for i in instance}) != len(instance):
            errors.append(f"{path}: items are not unique")
        if "items" in schema:
            for index, item in enumerate(instance):
                errors.extend(validate_against_schema(item, schema["items"], root, f"{path}[{index}]"))
    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", ()):
            if name not in instance:
                errors.append(f"{path}: missing required field '{name}'")
        extra = schema.get("additionalProperties", True)
        for name, value in instance.items():
            child = f"{path}.{name}"
            if name in properties:
                errors.extend(validate_against_schema(value, properties[name], root, child))
            elif extra is False:
                errors.append(f"{child}: unexpected field")
            elif isinstance(extra, dict):
                errors.extend(validate_against_schema(value, extra, root, child))
    return errors


# --------------------------------------------------------------------------
# Cross-field rules the schema cannot express.
# --------------------------------------------------------------------------


def _semantic_errors(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if record["content_sha256"] != content_sha256(record):
        errors.append("content_sha256 does not match the canonical-JSON sealed body")
    if record["run_id"] != make_run_id(record["lane"], record["started_at"], record["provenance"]["repo_sha"]):
        errors.append("run_id does not match lane, started_at, and provenance.repo_sha")
    if record["lane"] != canonical_lane(record["mode"]):
        errors.append(f"lane {record['lane']!r} is not the canonical lane of mode {record['mode']!r}")

    started, finished, sealed = (_parse_timestamp(record[k]) for k in ("started_at", "finished_at", "sealed_at"))
    if not started <= finished <= sealed:
        errors.append("timestamps must satisfy started_at <= finished_at <= sealed_at")
    if not record["verification"]["overall_verified"]:
        errors.append("only verified runs are sealed: verification.overall_verified must be true")

    case_ids = [c["id"] for c in record["cases"]]
    if len(set(case_ids)) != len(case_ids):
        errors.append("cases[].id values must be unique")
    if record["corpus"]["case_count"] != len(case_ids):
        errors.append("corpus.case_count does not equal the number of cases")
    if record["corpus"]["membership_digest"] != membership_digest(case_ids):
        errors.append("corpus.membership_digest does not match the case ids")
    return errors + _baseline_and_drift_errors(record, set(case_ids))


def _baseline_and_drift_errors(record: Mapping[str, Any], case_ids: set[str]) -> list[str]:
    errors: list[str] = []
    baseline, drift = record["baseline"], record["drift"]
    state = baseline["state"]
    comparable = set(baseline["comparable_case_ids"])
    incomparable = {c["id"] for c in baseline["incomparable_cases"]}

    if not (comparable | incomparable) <= case_ids:
        errors.append("baseline comparable/incomparable ids must be cases of this run")
    if comparable & incomparable:
        errors.append("a case cannot be both comparable and incomparable")
    if state == "compared":
        if baseline["run_id"] is None or baseline["record_sha256"] is None:
            errors.append("baseline.state 'compared' requires baseline.run_id and baseline.record_sha256")
    elif baseline["run_id"] is not None or baseline["record_sha256"] is not None or comparable or incomparable:
        errors.append(f"baseline.state {state!r} must carry no baseline reference or case partition")

    outcome = drift["outcome"]
    if (outcome["status"] == "not-evaluated") != bool(outcome["reason"]):
        errors.append("drift.outcome.reason is required exactly when status is 'not-evaluated'")
    if state != "compared" and outcome["status"] != "not-evaluated":
        errors.append(f"baseline.state {state!r} requires drift.outcome.status 'not-evaluated'")
    if outcome["status"] == "drift" and not drift["confirmed"]:
        errors.append("drift.outcome.status 'drift' requires confirmed drift")
    if outcome["status"] == "none" and drift["confirmed"]:
        errors.append("drift.outcome.status 'none' contradicts confirmed drift")
    if outcome["status"] == "not-evaluated" and (drift["observations"] or drift["evaluated_scope"]):
        errors.append("a 'not-evaluated' run must have no evaluated scope or observations")

    if not set(drift["evaluated_scope"]) <= comparable:
        errors.append("drift.evaluated_scope must be within baseline.comparable_case_ids")

    for group in ("observations", "confirmed", "unconfirmed"):
        for item in drift[group]:
            expected = fingerprint(item["case_id"], item["drift_type"], item["expected_finding_key"])
            if item["fingerprint"] != expected:
                errors.append(f"drift.{group}: fingerprint of {item['case_id']!r} does not match its identity triple")
            if item["case_id"] not in drift["evaluated_scope"]:
                errors.append(f"drift.{group}: {item['case_id']!r} is outside drift.evaluated_scope")

    observed = {i["fingerprint"] for i in drift["observations"]}
    confirmed = {i["fingerprint"] for i in drift["confirmed"]}
    unconfirmed = {i["fingerprint"] for i in drift["unconfirmed"]}
    if confirmed & unconfirmed or confirmed | unconfirmed != observed:
        errors.append("drift.confirmed and drift.unconfirmed must partition drift.observations")

    confirmed_cases = {i["case_id"] for i in drift["confirmed"]}
    for case_id, excerpt in drift["evidence"].items():
        if case_id not in confirmed_cases:
            errors.append(f"drift.evidence[{case_id!r}] is not a confirmed-drift case")
        if len(excerpt.encode("utf-8")) > EVIDENCE_MAX_BYTES:
            errors.append(f"drift.evidence[{case_id!r}] exceeds {EVIDENCE_MAX_BYTES} bytes")
    return errors


def validate_record(record: Any) -> list[str]:
    """All conformance errors for a sealed record; empty means conformant."""
    errors = validate_against_schema(record, load_schema(RESULT_SCHEMA_PATH))
    return errors or _semantic_errors(record)


def validate_receipt(receipt: Any) -> list[str]:
    return validate_against_schema(receipt, load_schema(RECEIPT_SCHEMA_PATH))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Validate sealed records (or receipts) against their schema.")
    validate.add_argument("files", nargs="+", type=Path)
    validate.add_argument("--receipt", action="store_true", help="Validate benchmark-receipt/v1 instead.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    check = validate_receipt if args.receipt else validate_record
    failed = False
    for path in args.files:
        try:
            errors = check(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            errors = [f"unreadable: {exc}"]
        for error in errors:
            print(f"{path}: {error}", file=sys.stderr)
        failed = failed or bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
