#!/usr/bin/env python3
"""Test-only reference for the repository-backed PR checkout lifecycle.

Mirrors skills/github-pr-review/policies/repository-checkout.md.
Not runtime logic, not packaged.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Sequence

_SHA_CHARS = set("0123456789abcdefABCDEF")

# Git env that neutralises repo-provided executable configuration when running
# against untrusted PR contents. Applied to every git call here.
_SAFE_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ATTR_NOSYSTEM": "1",
}
_SAFE_GIT_FLAGS = (
    "-c", "core.hooksPath=/dev/null",
    "-c", "core.fsmonitor=false",
    "-c", "protocol.file.allow=always",  # needed only for local-remote fixtures
    "-c", "advice.detachedHead=false",
)


class CheckoutError(RuntimeError):
    """Base class for repository-checkout failures."""


class RemoteUnavailableError(CheckoutError):
    """Clone/fetch failed: unreachable remote, auth failure, or no read access."""


class RefNotFoundError(CheckoutError):
    """A required base/head ref could not be resolved from the remote."""


class InvalidShaError(CheckoutError):
    """A supplied SHA is malformed or absent from fetched history."""


@dataclass(frozen=True)
class NormalizedPrSource:
    """The single PR model the checkout consumes.

    Real GitHub metadata and the local simulation both produce this — the
    checkout path has no `if simulation` branches.
    """

    repo_url: str
    pr_number: int
    base_ref: str
    base_sha: str
    head_ref: str
    head_sha: str
    pull_ref: Optional[str] = None  # e.g. "refs/pull/123/head" when published

    def __post_init__(self) -> None:
        for name in ("base_sha", "head_sha"):
            value = getattr(self, name)
            if not (7 <= len(value) <= 64 and set(value) <= _SHA_CHARS):
                raise InvalidShaError(f"{name} is not a git object id: {value!r}")


@dataclass(frozen=True)
class CheckoutHandle:
    """A read-only, detached checkout at the PR head. Never mutate it."""

    path: Path
    source: NormalizedPrSource
    base_sha: str
    head_sha: str

    def _git(self, *args: str) -> str:
        return _run_git(self.path, args)

    def merge_base(self) -> str:
        return self._git("merge-base", self.base_sha, self.head_sha)

    def changed_files(self) -> list[str]:
        out = self._git("diff", "--name-only", f"{self.merge_base()}..{self.head_sha}")
        return [line for line in out.splitlines() if line]

    def diff(self, *paths: str) -> str:
        return self._git("diff", f"{self.merge_base()}..{self.head_sha}", "--", *paths)

    def read_file(self, rel_path: str) -> str:
        target = (self.path / rel_path).resolve()
        _require_inside(target, self.path, "read_file")
        return target.read_text(encoding="utf-8")


def _run_git(cwd: Path, args: Sequence[str], *, check: bool = True) -> str:
    env = {**os.environ, **_SAFE_GIT_ENV}
    proc = subprocess.run(
        ["git", *_SAFE_GIT_FLAGS, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if check and proc.returncode != 0:
        raise CheckoutError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _require_inside(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise CheckoutError(f"{label}: {resolved} escapes {root_resolved}")
    return resolved


#: Marker file written into every checkout this module creates. Deletion is
#: refused unless it is present, so an unconstrained rmtree cannot happen.
_OWNERSHIP_MARKER = ".pr-checkout-owned-by-github-pr-review"


def _safe_rmtree(path: Path, scratch_root: Path) -> None:
    resolved = path.resolve()
    _require_inside(resolved, scratch_root, "cleanup")
    if resolved == scratch_root.resolve():
        raise CheckoutError("cleanup refused: path is the scratch root itself")
    if not (resolved / _OWNERSHIP_MARKER).is_file():
        raise CheckoutError(f"cleanup refused: {resolved} is not an owned checkout")
    shutil.rmtree(resolved, ignore_errors=True)


@contextlib.contextmanager
def prepare_repository_checkout(
    source: NormalizedPrSource,
    *,
    scratch_parent: Optional[Path] = None,
) -> Iterator[CheckoutHandle]:
    """Materialise an isolated, read-only checkout at the PR head, then always
    clean it up.

    Lifecycle: mkdtemp under a safe parent -> blobless clone -> fetch base and
    head -> detached checkout of head_sha -> yield -> cleanup in finally
    (after success, any failure, or interruption the runtime surfaces here).
    """
    scratch_root = Path(scratch_parent) if scratch_parent else Path(tempfile.gettempdir())
    scratch_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="pr-review-", dir=str(scratch_root)))
    (work / _OWNERSHIP_MARKER).write_text("do not edit; safe to delete\n", encoding="utf-8")
    repo = work / "checkout"
    try:
        _clone_and_fetch(source, repo)
        head = _resolve_head_sha(repo, source)
        _run_git(repo, ("checkout", "--detach", head))
        yield CheckoutHandle(path=repo, source=source, base_sha=source.base_sha, head_sha=head)
    finally:
        _safe_rmtree(work, scratch_root)


def _clone_and_fetch(source: NormalizedPrSource, repo: Path) -> None:
    parent = repo.parent
    try:
        _run_git(
            parent,
            (
                "clone", "--no-checkout", "--no-tags", "--filter=blob:none",
                source.repo_url, repo.name,
            ),
        )
    except CheckoutError as exc:
        raise RemoteUnavailableError(
            f"clone of {source.repo_url} failed (unreachable, unauthenticated, "
            f"or no read access): {exc}"
        ) from exc
    # Disable any credential/pager/hook config the clone may carry.
    _run_git(repo, ("config", "--local", "core.hooksPath", "/dev/null"))
    fetch_refs = [source.base_ref, source.head_ref]
    if source.pull_ref:
        fetch_refs.insert(0, source.pull_ref)
    try:
        _run_git(repo, ("fetch", "--no-tags", "origin", *dict.fromkeys(fetch_refs)))
    except CheckoutError:
        # Fall back to fetching the immutable SHAs directly.
        try:
            _run_git(repo, ("fetch", "--no-tags", "origin", source.base_sha, source.head_sha))
        except CheckoutError as exc:
            raise RefNotFoundError(
                f"could not fetch base/head for PR #{source.pr_number}: {exc}"
            ) from exc


def _resolve_head_sha(repo: Path, source: NormalizedPrSource) -> str:
    """Prefer the immutable head SHA; verify it exists in fetched history."""
    for candidate in (source.head_sha, source.pull_ref, source.head_ref):
        if not candidate:
            continue
        resolved = _run_git(repo, ("rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}"), check=False)
        if resolved:
            if source.head_sha and not resolved.startswith(source.head_sha) and not source.head_sha.startswith(resolved):
                continue
            return resolved
    raise InvalidShaError(
        f"PR #{source.pr_number} head {source.head_sha!r} is not present after fetch"
    )
