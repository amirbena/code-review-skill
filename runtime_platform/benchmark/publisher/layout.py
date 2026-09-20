"""`benchmark-history` paths and canonical file encoding."""

from __future__ import annotations

import json
from typing import Any

from runtime_platform.benchmark.scripts.benchmark_result import parse_run_id

STAGING_REF_PREFIX = "claude/benchmark-result-"


def _year(run_id: str) -> str:
    parsed = parse_run_id(run_id)
    if parsed is None:
        raise ValueError(f"malformed run_id {run_id!r}")
    return parsed[1][:4]


def _lane(run_id: str) -> str:
    return run_id.split("-", 1)[0]


def record_path(run_id: str) -> str:
    return f"records/{_lane(run_id)}/{_year(run_id)}/{run_id}.json"


def receipt_path(run_id: str) -> str:
    return f"receipts/{_lane(run_id)}/{_year(run_id)}/{run_id}.json"


def baseline_path(lane: str) -> str:
    return f"baselines/{lane}.json"


def staging_ref_name(run_id: str) -> str:
    return STAGING_REF_PREFIX + run_id


def run_id_from_ref(ref_name: str) -> str | None:
    """The run id a staging ref name encodes, or None when the name is not a valid one."""
    if not ref_name.startswith(STAGING_REF_PREFIX):
        return None
    run_id = ref_name[len(STAGING_REF_PREFIX):]
    return run_id if parse_run_id(run_id) else None


def run_sort_key(run_id: str) -> tuple[str, str]:
    """Orders one lane's runs by UTC start time, then commit."""
    parsed = parse_run_id(run_id)
    return (parsed[1], parsed[2]) if parsed else ("", run_id)


def encode_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
