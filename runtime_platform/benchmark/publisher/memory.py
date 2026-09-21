"""In-memory ports: the test double, and the read-through overlay `--dry-run` writes into."""

from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass
from typing import Mapping, Sequence

from runtime_platform.benchmark.publisher.ports import (
    Comment,
    HistoryStore,
    Issue,
    IssueTracker,
    PathExistsError,
    RefActivity,
    StagingRef,
)

DRY_RUN_ISSUE_BASE = 900_000_000


class InMemoryHandoff:
    def __init__(self) -> None:
        self.refs: dict[str, tuple[str, bytes | None]] = {}
        self.activities: dict[str, list[RefActivity] | None] = {}

    def add(self, name: str, data: bytes | None, *, sha: str, activities: list[RefActivity] | None) -> None:
        self.refs[name] = (sha, data)
        self.activities[name] = activities

    def list_staging_refs(self, prefix: str) -> list[StagingRef]:
        return [StagingRef(name, sha) for name, (sha, _) in sorted(self.refs.items()) if name.startswith(prefix)]

    def read_handoff(self, ref: StagingRef) -> bytes | None:
        return self.refs[ref.name][1]

    def ref_activities(self, ref_name: str) -> list[RefActivity] | None:
        return self.activities.get(ref_name)


@dataclass(frozen=True)
class Commit:
    sha: str
    message: str
    paths: tuple[str, ...]


class InMemoryHistory:
    def __init__(self, repository: str, inner: HistoryStore | None = None) -> None:
        self.repository = repository
        self.inner = inner
        self.files: dict[str, bytes] = {}
        self.commits: list[Commit] = []
        self.deleted_refs: list[str] = []
        self._path_commit: dict[str, str] = {}

    def read_file(self, path: str) -> bytes | None:
        if path in self.files:
            return self.files[path]
        return self.inner.read_file(path) if self.inner else None

    def list_dir(self, path: str) -> list[str]:
        names = {p[len(path) + 1:].split("/", 1)[0] for p in self.files if p.startswith(path + "/")}
        return sorted(names | set(self.inner.list_dir(path) if self.inner else ()))

    def commit_files(self, files: Mapping[str, bytes], message: str) -> str:
        for path in files:
            if self.read_file(path) is not None:
                raise PathExistsError(f"{path} already exists")
        sha = hashlib.sha1(f"{len(self.commits)}:{message}".encode()).hexdigest()
        self.files.update(files)
        self.commits.append(Commit(sha, message, tuple(files)))
        self._path_commit.update({path: sha for path in files})
        return sha

    def last_commit_for(self, path: str) -> str | None:
        if path in self._path_commit:
            return self._path_commit[path]
        return self.inner.last_commit_for(path) if self.inner else None

    def delete_staging_ref(self, name: str) -> None:
        self.deleted_refs.append(name)

    def permalink(self, commit: str, path: str) -> str:
        return f"https://github.com/{self.repository}/blob/{commit}/{path}"


class InMemoryTracker:
    """A fake GitHub issue surface; `identity` is the account every write is attributed to."""

    def __init__(self, repository: str, identity: str, labels: Sequence[str], inner: IssueTracker | None = None) -> None:
        self.repository, self.identity, self.labels, self.inner = repository, identity, set(labels), inner
        self.issues: dict[int, Issue] = {}
        self.comments: dict[int, list[Comment]] = {}
        self._next_number = DRY_RUN_ISSUE_BASE if inner else 1
        self._next_comment = 1
        self.edits: dict[int, str] = {}

    def _url(self, number: int) -> str:
        return f"https://github.com/{self.repository}/issues/{number}"

    def seed_issue(self, number: int, *, author: str, body: str, labels: Sequence[str], state: str = "open") -> Issue:
        issue = Issue(number, author, body, tuple(labels), state, self._url(number))
        self.issues[number] = issue
        self._next_number = max(self._next_number, number + 1)
        return issue

    def seed_comment(self, issue: int, *, author: str, body: str) -> Comment:
        comment = Comment(self._next_comment, author, body, f"{self._url(issue)}#issuecomment-{self._next_comment}")
        self._next_comment += 1
        self.comments.setdefault(issue, []).append(comment)
        return comment

    def missing_labels(self, names: Sequence[str]) -> list[str]:
        if self.inner:
            return self.inner.missing_labels(names)
        return [n for n in names if n not in self.labels]

    def list_comments(self, issue: int) -> list[Comment]:
        inner = self.inner.list_comments(issue) if self.inner and issue < DRY_RUN_ISSUE_BASE else []
        inner = [dataclasses.replace(c, body=self.edits[c.id]) if c.id in self.edits else c for c in inner]
        return inner + list(self.comments.get(issue, []))

    def create_comment(self, issue: int, body: str) -> Comment:
        return self.seed_comment(issue, author=self.identity, body=body)

    def update_comment(self, comment_id: int, body: str) -> Comment:
        """A local comment is replaced; a real one read through the overlay is shadowed, never written."""
        for issue, comments in self.comments.items():
            for index, comment in enumerate(comments):
                if comment.id == comment_id:
                    comments[index] = dataclasses.replace(comment, body=body)
                    return comments[index]
        self.edits[comment_id] = body
        return Comment(comment_id, self.identity, body, "")

    def list_issues(self, label: str, *, state: str, limit: int | None = None) -> list[Issue]:
        local = {n: i for n, i in self.issues.items()}
        inner = {i.number: i for i in self.inner.list_issues(label, state=state, limit=limit)} if self.inner else {}
        merged = {**inner, **local}
        rows = [i for i in merged.values() if label in i.labels and i.state == state]
        rows.sort(key=lambda i: -i.number)
        return rows[:limit] if limit else rows

    def get_issue(self, number: int) -> Issue | None:
        return self.issues.get(number) or (self.inner.get_issue(number) if self.inner else None)

    def create_issue(self, *, title: str, body: str, labels: Sequence[str]) -> Issue:
        number = self._next_number
        self._next_number += 1
        return self.seed_issue(number, author=self.identity, body=body, labels=labels)

    def close_issue(self, number: int) -> None:
        issue = self.get_issue(number)
        if issue is not None:
            self.issues[number] = Issue(issue.number, issue.author, issue.body, issue.labels, "closed", issue.url)


def dry_run_overlay(
    store: HistoryStore, tracker: IssueTracker, repository: str, identity: str
) -> tuple[InMemoryHistory, InMemoryTracker]:
    """Wrap real ports so every write lands in memory and reads fall through to GitHub."""
    return InMemoryHistory(repository, store), InMemoryTracker(repository, identity, [], tracker)
