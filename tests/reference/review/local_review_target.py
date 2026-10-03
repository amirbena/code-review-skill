#!/usr/bin/env python3
"""Test-only reference for one single-repository local Review Target.

Mirrors skills/local-code-review/policies/repository-state.md and the
report's Review Metadata / Review scope contract. Not packaged.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from tests.reference.review.pr_context_reconciliation import ReviewedState
from tests.reference.review.staged_fingerprint import compute_staged_fingerprint

_HEX = set("0123456789abcdef")


class LocalReviewTargetError(ValueError):
    """The local Review Target violates the repository-state contract."""


class SyncStatus(Enum):
    IN_SYNC = "in sync"
    LOCAL_AHEAD = "local ahead"
    LOCAL_BEHIND = "local behind"
    DIVERGED = "diverged"
    NO_TRACKING_BRANCH = "no tracking branch"


@dataclass(frozen=True)
class CategoryScope:
    """One delta category's inclusion in the review scope contract."""

    included: bool
    reason: Optional[str] = None  # required when excluded
    fingerprint: Optional[str] = None  # staged category only

    @classmethod
    def excluded(cls, reason: str) -> "CategoryScope":
        return cls(included=False, reason=reason)


def _is_sha(value: str) -> bool:
    return 7 <= len(value) <= 64 and set(value.lower()) <= _HEX


def _same_object(a: str, b: str) -> bool:
    a, b = a.lower(), b.lower()
    return a.startswith(b) or b.startswith(a)


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and set(value) <= _HEX


def staged_scope_from_raw_diff(raw_diff_bytes: bytes) -> CategoryScope:
    """Included staged scope; empty input yields the empty-input hash."""
    return CategoryScope(
        included=True, fingerprint=compute_staged_fingerprint(raw_diff_bytes)
    )


@dataclass(frozen=True)
class LocalReviewTarget:
    base_branch: str
    base_sha: str
    head_sha: str
    sync_status: SyncStatus
    committed: CategoryScope
    staged: CategoryScope
    unstaged: CategoryScope
    untracked: CategoryScope
    remote_head_sha: Optional[str] = None  # report renders "none" as absent

    def __post_init__(self) -> None:
        if not self.base_branch:
            raise LocalReviewTargetError("base_branch must not be empty")
        for name in ("base_sha", "head_sha"):
            value = getattr(self, name)
            if not _is_sha(value):
                raise LocalReviewTargetError(f"{name} is not a git object id: {value!r}")
        self._validate_remote_head()
        for name in ("committed", "staged", "unstaged", "untracked"):
            scope = getattr(self, name)
            if not scope.included and not (scope.reason or "").strip():
                raise LocalReviewTargetError(f"excluded {name} category requires a reason")
        self._validate_fingerprints()

    def _validate_remote_head(self) -> None:
        remote = self.remote_head_sha
        if self.sync_status is SyncStatus.NO_TRACKING_BRANCH:
            if remote is not None:
                raise LocalReviewTargetError("no tracking branch cannot have a remote HEAD")
        elif remote is None or not _is_sha(remote):
            raise LocalReviewTargetError(f"remote_head_sha is not a git object id: {remote!r}")
        elif self.sync_status is SyncStatus.IN_SYNC and not _same_object(remote, self.head_sha):
            raise LocalReviewTargetError("in sync requires remote HEAD to equal local HEAD")

    def _validate_fingerprints(self) -> None:
        for name in ("committed", "unstaged", "untracked"):
            if getattr(self, name).fingerprint is not None:
                raise LocalReviewTargetError(f"{name} category never carries a fingerprint")
        fingerprint = self.staged.fingerprint
        if fingerprint is None:
            if self.staged.included:
                raise LocalReviewTargetError("included staged category requires a fingerprint")
        elif not _is_sha256_hex(fingerprint):
            raise LocalReviewTargetError(f"staged fingerprint is not SHA-256 hex: {fingerprint!r}")

    def to_reviewed_state(self) -> ReviewedState:
        """Project to the reviewed-state identity; staged fingerprint required."""
        if self.staged.fingerprint is None:
            raise LocalReviewTargetError("reviewed state requires a staged fingerprint")
        return ReviewedState(
            staged_fingerprint=self.staged.fingerprint,
            base_sha=self.base_sha,
            head_sha=self.head_sha,
        )
