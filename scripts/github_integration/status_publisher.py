"""Publish the SHA-bound review status through the Commit Status API."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from scripts.github_integration.boundary import (
    GitHubCallError,
    GitHubClient,
    GitHubPermissionError,
)

STATUS_CONTEXT = "code-review/github-pr-review"
RETRY_ATTEMPTS = 3
FULL_SHA_RE = re.compile(r"[0-9a-f]{40}")
REPO_RE = re.compile(r"[\w.-]+/[\w.-]+")


class Reasoning(Enum):
    CLEAN = "REVIEW CLEAN"
    CHANGES_REQUIRED = "CHANGES REQUIRED"
    INCOMPLETE = "REVIEW INCOMPLETE"
    JIRA_UNRESOLVED = "JIRA CONTEXT UNRESOLVED"
    CONTEXT_UNAVAILABLE = "REPOSITORY CONTEXT UNAVAILABLE"
    NO_NEW_DELTA = "NO NEW DELTA"


class StatusPermissionError(GitHubPermissionError):
    pass


@dataclass(frozen=True)
class PublishRequest:
    """Already-resolved facts; verdict and authorization are decided upstream."""

    reasoning: Reasoning
    repo: str
    pr_number: int
    reviewed_head_sha: str
    is_aggregator: bool = False
    self_review: bool = False
    active_mode: bool = False
    reviewer_independent: bool = False


@dataclass(frozen=True)
class PublishOutcome:
    action: str  # "published" | "noop" | "withheld"
    context: str
    sha: str
    state: str | None = None
    message: str = ""


def map_state(reasoning: Reasoning) -> str | None:
    """Canonical verdict to status state; `None` means nothing to publish."""
    if reasoning is Reasoning.CLEAN:
        return "success"
    if reasoning is Reasoning.NO_NEW_DELTA:
        return None
    return "failure"


def _description(reasoning: Reasoning, sha: str) -> str:
    return f"{reasoning.value} (reviewed {sha[:7]})"


def _withheld(req: PublishRequest, reason: str) -> PublishOutcome:
    return PublishOutcome(
        "withheld", STATUS_CONTEXT, req.reviewed_head_sha, None, f"STATUS WITHHELD ({reason})"
    )


def _success_authorized(req: PublishRequest) -> bool:
    return req.active_mode and req.reviewer_independent and not req.self_review


def _validate(req: PublishRequest) -> None:
    if not REPO_RE.fullmatch(req.repo) or ".." in req.repo:
        raise ValueError(f"invalid repository: {req.repo!r}")
    if not FULL_SHA_RE.fullmatch(req.reviewed_head_sha):
        raise ValueError("reviewed_head_sha must be the full 40-character commit SHA")
    if not isinstance(req.pr_number, int) or req.pr_number <= 0:
        raise ValueError(f"invalid PR number: {req.pr_number!r}")


def _with_retry(call: Callable[[], object], sleep: Callable[[float], None]):
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return call()
        except GitHubCallError as exc:
            transient = exc.status == 0 or (exc.status or 0) >= 500
            if not transient or attempt == RETRY_ATTEMPTS - 1:
                raise
            sleep(2**attempt)


def _current_state(client: GitHubClient, req: PublishRequest, sleep) -> tuple[str, str] | None:
    endpoint = f"repos/{req.repo}/commits/{req.reviewed_head_sha}/status?per_page=100"
    combined = _with_retry(lambda: client.read(endpoint), sleep) or {}
    for status in combined.get("statuses", []):
        if status.get("context") == STATUS_CONTEXT:
            return status.get("state"), status.get("description") or ""
    return None


def publish_status(
    client: GitHubClient,
    req: PublishRequest,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> PublishOutcome:
    """Upsert the one stable context on the reviewed SHA, or withhold."""
    _validate(req)
    intended = map_state(req.reasoning)
    if not req.is_aggregator:
        return _withheld(req, "parallel worker cannot publish the aggregated status")
    if intended is None:
        return _withheld(req, "no new delta; existing status already covers this HEAD")

    pull = _with_retry(lambda: client.read(f"repos/{req.repo}/pulls/{req.pr_number}"), sleep)
    live_head = ((pull or {}).get("head") or {}).get("sha")
    if live_head != req.reviewed_head_sha:
        return _withheld(req, "HEAD advanced")
    if intended == "success" and not _success_authorized(req):
        if req.self_review:
            return _withheld(req, "self-review: success not published")
        return _withheld(req, "success requires ACTIVE publication mode and reviewer independence")

    description = _description(req.reasoning, req.reviewed_head_sha)
    if _current_state(client, req, sleep) == (intended, description):
        return PublishOutcome("noop", STATUS_CONTEXT, req.reviewed_head_sha, intended)

    payload = {"state": intended, "context": STATUS_CONTEXT, "description": description}
    endpoint = f"repos/{req.repo}/statuses/{req.reviewed_head_sha}"
    try:
        _with_retry(lambda: client.write("POST", endpoint, payload), sleep)
    except GitHubPermissionError as exc:
        raise StatusPermissionError(
            "Cannot publish the review status: the token needs `Commit statuses: write` "
            f"(fine-grained) or `repo:status` (classic) on {req.repo}. {exc}"
        ) from exc
    return PublishOutcome("published", STATUS_CONTEXT, req.reviewed_head_sha, intended)
