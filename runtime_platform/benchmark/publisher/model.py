"""The ports bundle, the sweep and watchdog configuration, and report types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from runtime_platform.benchmark.publisher.ports import HandoffReader, HistoryStore, IssueTracker

PUBLISHED, ALREADY_PUBLISHED, REFUSED, FAILED = "published", "already-published", "refused", "failed"
SCOPE_ALL, SCOPE_RUN_ID = "all", "run-id"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_instant(instant: datetime) -> str:
    return instant.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_instant(text: object) -> datetime | None:
    """A zone-aware instant from an ISO-8601 string, or None when it is not one."""
    try:
        instant = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return instant if instant.tzinfo is not None else None


@dataclass(frozen=True)
class Ports:
    reader: HandoffReader
    store: HistoryStore
    tracker: IssueTracker


@dataclass(frozen=True)
class SweepConfig:
    manifest: Mapping[str, Any]
    identity: str
    run_url: str
    local_once: bool = False
    only_run_id: str | None = None
    accept_unattributed: bool = False
    dry_run: bool = False
    clock: Callable[[], datetime] = utc_now


@dataclass(frozen=True)
class WatchdogConfig:
    manifest: Mapping[str, Any]
    identity: str
    sweep_succeeded: bool = False
    clock: Callable[[], datetime] = utc_now


@dataclass
class RunOutcome:
    ref: str
    run_id: str | None
    status: str
    detail: str = ""
    gate: str | None = None
    commit: str | None = None
    actions: list[dict[str, Any]] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in (None, "", [])}


@dataclass
class SweepReport:
    identity: str
    scope: str = SCOPE_ALL
    dry_run: bool = False
    outcomes: list[RunOutcome] = field(default_factory=list)
    aborted: str | None = None

    @property
    def ok(self) -> bool:
        return self.aborted is None and all(o.status in (PUBLISHED, ALREADY_PUBLISHED) for o in self.outcomes)

    def as_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity,
            "ok": self.ok,
            "aborted": self.aborted,
            "scope": self.scope,
            "dry_run": self.dry_run,
            "runs": [o.as_dict() for o in self.outcomes],
        }


@dataclass
class WatchdogReport:
    identity: str
    lanes: list[dict[str, Any]] = field(default_factory=list)
    health: dict[str, Any] = field(default_factory=dict)
    aborted: str | None = None

    @property
    def ok(self) -> bool:
        return self.aborted is None

    def as_dict(self) -> dict[str, Any]:
        return {"identity": self.identity, "ok": self.ok, "aborted": self.aborted, "lanes": self.lanes, "health": self.health}
