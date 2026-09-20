"""The ports bundle, sweep configuration, and report types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from runtime_platform.benchmark.publisher.ports import HandoffReader, HistoryStore, IssueTracker

PUBLISHED, ALREADY_PUBLISHED, REFUSED, FAILED = "published", "already-published", "refused", "failed"


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
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)


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
            "runs": [o.as_dict() for o in self.outcomes],
        }
