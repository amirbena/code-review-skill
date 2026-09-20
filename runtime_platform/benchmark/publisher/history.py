"""Reads and writes of `benchmark-history` for one publication: baseline, records, lane views."""

from __future__ import annotations

import json
from typing import Any, Mapping

from runtime_platform.benchmark.publisher.layout import baseline_path, encode_json, record_path, run_sort_key
from runtime_platform.benchmark.publisher.ports import HistoryStore, PublicationFailure
from runtime_platform.benchmark.publisher.validation import Refusal
from runtime_platform.benchmark.scripts.benchmark_result import content_sha256, parse_run_id, validate_record


def same_record(existing: bytes, digest: str) -> bool:
    try:
        stored = json.loads(existing.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(stored, dict) and stored.get("content_sha256") == digest and content_sha256(stored) == digest


def load_baseline(store: HistoryStore, record: Mapping[str, Any]) -> dict[str, Any] | Refusal:
    """The exact baseline evidence a compared record names, verified against its recorded hash."""
    baseline = record["baseline"]
    if baseline["state"] != "compared":
        return {"baseline_permalink": None, "baseline_run_id": None, "baseline_repo_sha": None, "baseline_date": None}
    path = record_path(baseline["run_id"])
    data = store.read_file(path)
    if data is None or not same_record(data, baseline["record_sha256"]):
        return Refusal("baseline", f"baseline record {baseline['run_id']} is missing from history or does not match its recorded hash")
    stored = json.loads(data.decode("utf-8"))
    commit = store.last_commit_for(path)
    if commit is None:
        return Refusal("baseline", f"no history commit found for baseline record {baseline['run_id']}")
    return {
        "baseline_permalink": store.permalink(commit, path),
        "baseline_run_id": baseline["run_id"],
        "baseline_repo_sha": stored["provenance"]["repo_sha"],
        "baseline_date": stored["started_at"][:10],
    }


def persist(store: HistoryStore, record: Mapping[str, Any], existing: bytes | None, identity: str, now: str) -> str:
    """Create-only record write; the lane's bootstrap pointer lands in the same commit."""
    path = record_path(record["run_id"])
    if existing is not None:
        commit = store.last_commit_for(path)
        if commit is None:
            raise PublicationFailure(f"record {record['run_id']} exists but no history commit was found for it")
        return commit
    files = {path: encode_json(record)}
    lane = record["lane"]
    if record["baseline"]["state"] == "bootstrap" and store.read_file(baseline_path(lane)) is None:
        files[baseline_path(lane)] = encode_json(
            {
                "lane": lane,
                "run_id": record["run_id"],
                "record_path": path,
                "record_sha256": record["content_sha256"],
                "corpus_id": record["corpus"]["corpus_id"],
                "source": "bootstrap",
                "promoted_at": now,
                "promoted_by": identity,
            }
        )
    return store.commit_files(files, f"Record {record['run_id']}")


def latest_published_run_id(store: HistoryStore, lane: str) -> str | None:
    """The lane's newest run that has a receipt."""
    for year in sorted((n for n in store.list_dir(f"receipts/{lane}") if n.isdigit()), reverse=True):
        run_ids = [n[:-5] for n in store.list_dir(f"receipts/{lane}/{year}") if n.endswith(".json") and parse_run_id(n[:-5])]
        if run_ids:
            return max(run_ids, key=run_sort_key)
    return None


def lane_views(
    store: HistoryStore, record: Mapping[str, Any], lanes: list[str]
) -> tuple[dict[str, Mapping[str, Any] | None] | None, bool]:
    """Each lane's latest published record, and whether a newer record of this lane is already published."""
    latest = latest_published_run_id(store, record["lane"])
    superseded = latest is not None and run_sort_key(latest) > run_sort_key(record["run_id"])
    views: dict[str, Mapping[str, Any] | None] = {record["lane"]: record}
    for lane in (lane for lane in lanes if lane != record["lane"]):
        run_id = latest_published_run_id(store, lane)
        if run_id is None:
            views[lane] = None
            continue
        data = store.read_file(record_path(run_id))
        try:
            loaded = json.loads(data.decode("utf-8")) if data is not None else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            loaded = None
        if not isinstance(loaded, dict) or validate_record(loaded):
            return None, superseded
        views[lane] = loaded
    return views, superseded
