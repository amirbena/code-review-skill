"""Value types and ports the publisher uses; Git and GitHub are reached only through them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

HANDOFF_FILE = "benchmark-result.json"
HISTORY_BRANCH = "benchmark-history"


class PublicationFailure(RuntimeError):
    """A step failed; the run stays unpublished and the next sweep retries it."""


class FatalPublicationError(PublicationFailure):
    """Credential or identity failure: the whole sweep stops and never falls back to another identity."""


class PathExistsError(PublicationFailure):
    """A create-only write met an existing path."""


@dataclass(frozen=True)
class StagingRef:
    name: str
    sha: str


@dataclass(frozen=True)
class RefActivity:
    activity_type: str
    ref: str
    actor_login: str
    after: str


@dataclass(frozen=True)
class Comment:
    id: int
    author: str
    body: str
    url: str


@dataclass(frozen=True)
class Issue:
    number: int
    author: str
    body: str
    labels: tuple[str, ...]
    state: str
    url: str


class HandoffReader(Protocol):
    """Read-only view of the sealed handoff refs (`contents: read`)."""

    def list_staging_refs(self, prefix: str) -> list[StagingRef]: ...

    def read_handoff(self, ref: StagingRef) -> bytes | None: ...

    def ref_activities(self, ref_name: str) -> list[RefActivity] | None:
        """Server-side activity for the ref, or None when attribution is unavailable."""


class HistoryStore(Protocol):
    """The `benchmark-history` branch and staging-ref deletion (`contents: write`)."""

    def read_file(self, path: str) -> bytes | None: ...

    def list_dir(self, path: str) -> list[str]: ...

    def commit_files(self, files: Mapping[str, bytes], message: str) -> str:
        """Create-only: raises PathExistsError if any path exists; creates the branch when absent."""

    def last_commit_for(self, path: str) -> str | None: ...

    def delete_staging_ref(self, name: str) -> None: ...

    def permalink(self, commit: str, path: str) -> str: ...


class IssueTracker(Protocol):
    """Issues and comments (`issues: write`)."""

    def missing_labels(self, names: Sequence[str]) -> list[str]: ...

    def list_comments(self, issue: int) -> list[Comment]: ...

    def create_comment(self, issue: int, body: str) -> Comment: ...

    def list_issues(self, label: str, *, state: str, limit: int | None = None) -> list[Issue]:
        """Newest first; `limit` bounds the scan, None lists everything."""

    def get_issue(self, number: int) -> Issue | None: ...

    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> Issue: ...

    def close_issue(self, number: int) -> None: ...
