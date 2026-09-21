"""Sealed-record builders and an in-memory GitHub world for publisher tests."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Sequence

from runtime_platform.benchmark.publisher.layout import encode_json, staging_ref_name
from runtime_platform.benchmark.publisher.memory import InMemoryHandoff, InMemoryHistory, InMemoryTracker
from runtime_platform.benchmark.publisher.ports import RefActivity
from runtime_platform.benchmark.publisher.model import Ports, SweepConfig, SweepReport, WatchdogConfig, WatchdogReport
from runtime_platform.benchmark.publisher.sweep import run_sweep
from runtime_platform.benchmark.publisher.watchdog import run_watchdog
from runtime_platform.benchmark.scripts import benchmark_result as res
from runtime_platform.benchmark.scripts.benchmark_drift import fingerprint
from runtime_platform.benchmark.scripts.benchmark_schedule_manifest import load_manifest
from tests.support.paths import REPO_ROOT

REPOSITORY = "amirbena/code-review-skill"
SLUG = "benchmark-publication"
IDENTITY = f"{SLUG}[bot]"
PUSHER = "amirbena"
NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
CASES = [
    "correctness-off-by-one-pagination",
    "no-op-comment-and-rename",
    "quality-duplicated-branch-logic",
    "security-command-injection",
]
EXAMPLES = REPO_ROOT / "runtime_platform" / "benchmark" / "schemas" / "examples"
_TEMPLATE = json.loads((EXAMPLES / "sentinel-bootstrap.record.json").read_text(encoding="utf-8"))


def drift_item(case_id: str, drift_type: str = "decision-flip", key: str = "-", detail: str = "regressed") -> dict[str, str]:
    return {
        "case_id": case_id,
        "drift_type": drift_type,
        "expected_finding_key": key,
        "detail": detail,
        "fingerprint": fingerprint(case_id, drift_type, key),
    }


def make_record(
    *,
    lane: str = "sentinel",
    start: datetime = datetime(2026, 9, 16, 1, 0, tzinfo=timezone.utc),
    sha: str = "1" * 12,
    baseline: dict[str, Any] | None = None,
    comparable: Sequence[str] = CASES[:3],
    confirmed: Sequence[dict[str, str]] = (),
    attribution: str = "none",
    trigger: str = "scheduled",
    verified: bool = True,
    state: str = "bootstrap",
) -> dict[str, Any]:
    """A valid sealed record; `baseline=None` makes it a `state` record (bootstrap or incomparable)."""
    record = copy.deepcopy(_TEMPLATE)
    stamp = lambda moment: moment.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    record.pop("content_sha256", None)
    record.update(lane=lane, mode=lane, trigger=trigger)
    record.update(started_at=stamp(start), finished_at=stamp(start + timedelta(minutes=1)), sealed_at=stamp(start + timedelta(minutes=2)))
    record["provenance"]["repo_sha"] = (sha * 4)[:40]
    record["run_id"] = res.make_run_id(lane, record["started_at"], record["provenance"]["repo_sha"])
    record["verification"]["overall_verified"] = verified
    if baseline is None:
        record["baseline"]["state"] = state
        record["drift"].update(evaluated_scope=[], observations=[], confirmed=[], unconfirmed=[], evidence={}, attribution="none")
    else:
        record["baseline"] = {
            "state": "compared",
            "run_id": baseline["run_id"],
            "record_sha256": baseline["content_sha256"],
            "comparable_case_ids": list(comparable),
            "incomparable_cases": [],
        }
        items = [dict(item) for item in confirmed]
        record["drift"].update(
            evaluated_scope=list(comparable),
            observations=items,
            confirmed=items,
            unconfirmed=[],
            evidence={item["case_id"]: "excerpt" for item in items},
            attribution=attribution,
            outcome={"status": "drift" if items else "none", "reason": None},
        )
    return res.seal_record(record)


class _Hooked:
    """Tests set `hook(method, *args)` to raise before a write, simulating a GitHub failure."""

    hook: Callable[..., None] | None = None

    def _before(self, method: str, *args: Any) -> None:
        if self.hook:
            self.hook(method, *args)


class HookedHistory(_Hooked, InMemoryHistory):
    def commit_files(self, files: Any, message: str) -> str:
        self._before("commit_files", files)
        return super().commit_files(files, message)

    def delete_staging_ref(self, name: str) -> None:
        self._before("delete_staging_ref", name)
        super().delete_staging_ref(name)


class HookedTracker(_Hooked, InMemoryTracker):
    def create_comment(self, issue: int, body: str) -> Any:
        self._before("create_comment", issue, body)
        return super().create_comment(issue, body)

    def update_comment(self, comment_id: int, body: str) -> Any:
        self._before("update_comment", comment_id, body)
        return super().update_comment(comment_id, body)

    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> Any:
        self._before("create_issue", title, body)
        return super().create_issue(title=title, body=body, labels=labels)

    def close_issue(self, number: int) -> None:
        self._before("close_issue", number)
        super().close_issue(number)


class World:
    """Handoff refs, `benchmark-history`, and issues, all in memory, plus a fixed clock."""

    def __init__(self, *, identity: str = IDENTITY, labels: Sequence[str] | None = None) -> None:
        self.manifest = load_manifest()
        names = [entry["name"] for entry in self.manifest["labels"]] if labels is None else labels
        self.handoff = InMemoryHandoff()
        self.store = HookedHistory(REPOSITORY)
        self.tracker = HookedTracker(REPOSITORY, identity, names)
        self.now = NOW

    def seal(self, record: dict[str, Any], *, actor: str = PUSHER, activities: Any = "default", data: bytes | None = None) -> str:
        name = staging_ref_name(record["run_id"])
        sha = res.sha256_hex(name)[:40]
        if activities == "default":
            activities = [RefActivity("branch_creation", f"refs/heads/{name}", actor, sha)]
        self.handoff.add(name, encode_json(record) if data is None else data, sha=sha, activities=activities)
        return name

    def ports(self) -> Ports:
        return Ports(self.handoff, self.store, self.tracker)

    def config(self, **overrides: Any) -> SweepConfig:
        values: dict[str, Any] = dict(
            manifest=self.manifest, identity=IDENTITY, run_url="https://github.com/amirbena/code-review-skill/actions/runs/1",
            clock=lambda: self.now,
        )
        values.update(overrides)
        return SweepConfig(**values)

    def sweep(self, **overrides: Any) -> SweepReport:
        return run_sweep(self.ports(), self.config(**overrides))

    def watchdog(self, **overrides: Any) -> WatchdogReport:
        values: dict[str, Any] = dict(manifest=self.manifest, identity=IDENTITY, clock=lambda: self.now)
        values.update(overrides)
        return run_watchdog(self.ports(), WatchdogConfig(**values))

    def health_comments(self) -> list[Any]:
        return self.tracker.comments.get(self.manifest["health_issue"], [])

    def missed_run_issues(self, state: str = "open") -> list[Any]:
        return self.tracker.list_issues("benchmark-missed-run", state=state)

    def stored(self, path: str) -> dict[str, Any]:
        return json.loads(self.store.files[path].decode("utf-8"))

    def regression_issues(self, state: str = "open") -> list[Any]:
        return self.tracker.list_issues("benchmark-regression", state=state)

    def tracking_comments(self, lane: str = "sentinel") -> list[Any]:
        return self.tracker.comments.get(self.manifest["lanes"][lane]["tracking_issue"], [])
