#!/usr/bin/env python3
"""Test-only reference for the mutation-authority capability pipeline.

Mirrors shared/policies/mutation-authority.md. Not runtime logic, not
packaged.

Encodes the #300 canonical threat model's source/Git mutation scenarios
(docs/threat-model/catalog/mutation-authority.yaml, AUTH-001..AUTH-016,
excluding AUTH-014 which is a different, already-covered authority
domain) as an executable capability state machine plus a dedicated
mutation executor, so each scenario is pinned by a runnable test rather
than left as prose.

Pipeline:

    READ_ONLY -> PROPOSE_PATCH -> USER_APPROVES_EXACT_PATCH -> APPLY_PATCH -> VERIFY_MUTATION

with COMMIT and PUSH as separate, independently authorized capabilities.

Every denial here raises a MutationAuthorityError subclass — a caller
cannot mistake a denial for a soft/ignorable return value.
"""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Optional, Sequence


class MutationCapability(Enum):
    READ_ONLY = "read_only"
    PROPOSE_PATCH = "propose_patch"
    APPLY_PATCH = "apply_patch"
    COMMIT = "commit"
    PUSH = "push"


# The entire capability surface this module defines. Anything not in this
# set (merge, branch deletion, force push, settings change, deployment...)
# is unrepresentable: there is no function in this module that performs
# it, and no way to construct an authorization for it (AUTH-015).
CAPABILITY_SURFACE: frozenset[MutationCapability] = frozenset(MutationCapability)

_AUTHORIZABLE_CAPABILITIES: frozenset[MutationCapability] = frozenset(
    {MutationCapability.APPLY_PATCH, MutationCapability.COMMIT, MutationCapability.PUSH}
)


class MutationAuthorityError(RuntimeError):
    """Base class for every mutation-authority denial."""


class CapabilityAbsentError(MutationAuthorityError):
    """AUTH-001 / AUTH-002 / AUTH-004 / AUTH-015: no such capability exists
    for this invocation (default READ_ONLY, or a capability outside
    CAPABILITY_SURFACE)."""


class UnauthorizedMutationError(MutationAuthorityError):
    """AUTH-003 / AUTH-005 / AUTH-010 / AUTH-011: the capability exists but
    no valid trusted authorization covers this attempt."""


class StaleApprovalError(MutationAuthorityError):
    """AUTH-006 / AUTH-007 / AUTH-008: authorization no longer matches the
    current patch digest or base state."""


class ScopeEscapeError(MutationAuthorityError):
    """AUTH-009 / AUTH-016: touched paths exceed the authorized scope, or
    post-apply verification found an unrelated change."""


class AuthorizationReplayError(MutationAuthorityError):
    """AUTH-012 / AUTH-013: authorization already consumed, or presented
    outside the exact invocation/repo/worktree it was issued for
    (including a spawned child attempting to reuse a parent's grant)."""


# --- Trusted authorization channel -------------------------------------


class TrustedChannel:
    """Marker type for the only channel `authorize()` accepts.

    Only runtime/orchestration code may construct one. There is
    deliberately no constructor that derives a TrustedChannel from a
    string, a finding, repository content, or model output: repository
    content is always plain `str` (see `channel_from_repository_text`
    below), never this type, so passing repository-derived text where a
    TrustedChannel is required is a type error, not a runtime judgment
    call (AUTH-003 / AUTH-004).
    """

    __slots__ = ("principal",)

    def __init__(self, principal: str) -> None:
        if not principal:
            raise ValueError("a TrustedChannel must name a principal")
        self.principal = principal


def channel_from_repository_text(text: str) -> str:
    """Illustrative only: PR/issue/commit text, AGENTS.md/CLAUDE.md/
    CONTRIBUTING.md content, finding text, generated metadata, and model
    output all parse to plain `str` — never to a TrustedChannel. This
    function exists so a test can assert its return type is never
    accepted by `authorize()`."""
    return text


# --- Proposal (PROPOSE_PATCH) -------------------------------------------


def _reject_out_of_scope_path(rel_path: str) -> None:
    p = PurePosixPath(rel_path)
    if p.is_absolute() or ".." in p.parts:
        raise ScopeEscapeError(f"path escapes worktree: {rel_path!r}")
    if p.parts and p.parts[0] == ".git":
        raise ScopeEscapeError(f"path targets .git: {rel_path!r}")


@dataclass(frozen=True)
class PatchProposal:
    """Output of PROPOSE_PATCH. Pure data — constructing one never touches
    the filesystem or invokes Git."""

    patch_text: str
    target_paths: frozenset[str]
    base_sha: str

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.patch_text.encode("utf-8")).hexdigest()


def propose_patch(patch_text: str, target_paths: Sequence[str], base_sha: str) -> PatchProposal:
    """PROPOSE_PATCH: pure computation, never a write.

    No `open(..., "w")`, no filesystem mutation, no Git command that
    changes state happens in this function — it only validates and
    returns data. A caller who never advances past this capability has
    changed nothing about the target repository.
    """
    paths = frozenset(target_paths)
    for rel_path in paths:
        _reject_out_of_scope_path(rel_path)
    return PatchProposal(patch_text=patch_text, target_paths=paths, base_sha=base_sha)


# --- Authorization -------------------------------------------------------


@dataclass(frozen=True)
class InvocationContext:
    """Identifies the exact invocation/repo/worktree an authorization (and
    the executor consuming it) must agree on."""

    invocation_id: str
    repo_id: str
    worktree_root: Path


@dataclass(frozen=True)
class MutationAuthorization:
    """A single, narrowly bound grant for exactly one capability.

    APPLY_PATCH, COMMIT, and PUSH each require their own instance —
    holding one never implies, upgrades to, or substitutes for another
    (AUTH-010, AUTH-011). `binding_value` is interpreted per capability:
    the approved patch digest for APPLY_PATCH, the digest of the
    already-applied change for COMMIT, and the exact commit sha for PUSH.
    """

    capability: MutationCapability
    channel: TrustedChannel
    invocation_id: str
    repo_id: str
    worktree_root: Path
    base_sha: str
    binding_value: str

    def key(self) -> tuple:
        """Identity used for single-use/replay tracking. Two
        authorizations are the same grant only if every binding
        coordinate matches."""
        return (
            self.capability,
            id(self.channel),
            self.invocation_id,
            self.repo_id,
            str(self.worktree_root),
            self.base_sha,
            self.binding_value,
        )


def authorize(
    *,
    capability: MutationCapability,
    channel: TrustedChannel,
    ctx: InvocationContext,
    base_sha: str,
    binding_value: str,
) -> MutationAuthorization:
    """The only function that produces a MutationAuthorization.

    Raises unless `capability` is one of the three authorizable
    capabilities and `channel` is a genuine TrustedChannel instance — a
    `str` (i.e. anything derived from repository content, see
    `channel_from_repository_text`) is rejected structurally, not by
    content inspection.
    """
    if capability not in _AUTHORIZABLE_CAPABILITIES:
        raise CapabilityAbsentError(
            f"{capability} is not an authorizable capability "
            f"(default-granted, or outside {sorted(c.value for c in CAPABILITY_SURFACE)})"
        )
    if not isinstance(channel, TrustedChannel):
        raise UnauthorizedMutationError(
            "authorization channel must be a TrustedChannel instance; "
            "repository-derived text can never establish authorization"
        )
    return MutationAuthorization(
        capability=capability,
        channel=channel,
        invocation_id=ctx.invocation_id,
        repo_id=ctx.repo_id,
        worktree_root=ctx.worktree_root,
        base_sha=base_sha,
        binding_value=binding_value,
    )


class AuthorizationLedger:
    """Tracks consumed authorizations for one executor.

    A ledger is per-executor. A spawned child gets a brand-new, empty
    ledger with no reference to the parent's — see `spawn_child` on
    MutationExecutor and AUTH-013 / DELEG-007.
    """

    def __init__(self) -> None:
        self._consumed: set[tuple] = set()

    def is_consumed(self, auth: MutationAuthorization) -> bool:
        return auth.key() in self._consumed

    def consume(self, auth: MutationAuthorization) -> None:
        key = auth.key()
        if key in self._consumed:
            raise AuthorizationReplayError("authorization already consumed; single-use")
        self._consumed.add(key)


# --- Git plumbing (used only by the mutation executor below) -------------

_SAFE_GIT_ENV_OVERRIDES = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
}
_SAFE_GIT_FLAGS = ("-c", "core.hooksPath=/dev/null")


def _run_git(cwd: Path, args: Sequence[str], *, check: bool = True) -> str:
    import os

    env = {**os.environ, **_SAFE_GIT_ENV_OVERRIDES}
    proc = subprocess.run(
        ["git", *_SAFE_GIT_FLAGS, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if check and proc.returncode != 0:
        raise MutationAuthorityError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


@dataclass(frozen=True)
class _Snapshot:
    status: str
    refs: str
    head: str


def _snapshot(root: Path) -> _Snapshot:
    status = _run_git(root, ("status", "--porcelain=v1", "--untracked-files=all"))
    refs = _run_git(root, ("for-each-ref",))
    head = _run_git(root, ("rev-parse", "HEAD"), check=False).strip()
    return _Snapshot(status=status, refs=refs, head=head)


def _status_entries(status: str) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in status.splitlines():
        if not line:
            continue
        code, path = line[:2], line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        entries[path] = code
    return entries


def _changed_paths(before: _Snapshot, after: _Snapshot) -> frozenset[str]:
    b, a = _status_entries(before.status), _status_entries(after.status)
    return frozenset(p for p in a if a.get(p) != b.get(p))


def _refs_mutated(before: _Snapshot, after: _Snapshot) -> bool:
    return before.refs != after.refs or before.head != after.head


# --- Mutation results ------------------------------------------------------


@dataclass(frozen=True)
class ApplyResult:
    applied_paths: frozenset[str]
    patch_digest: str


@dataclass(frozen=True)
class CommitResult:
    commit_sha: str
    patch_digest: str


# --- The dedicated mutation executor ---------------------------------------


class MutationExecutor:
    """The single, dedicated entry point for APPLY_PATCH / COMMIT / PUSH.

    No other function in this module performs a working-tree write, `git
    commit`, or `git push`. Concentrating the write-capable surface here
    is what makes ambient write access unrepresentable elsewhere — see
    shared/policies/mutation-authority.md, "Dedicated mutation executor."
    """

    def __init__(self, ctx: InvocationContext, ledger: Optional[AuthorizationLedger] = None) -> None:
        self._ctx = ctx
        self._ledger = ledger if ledger is not None else AuthorizationLedger()

    @property
    def context(self) -> InvocationContext:
        return self._ctx

    def spawn_child(self, child_invocation_id: str) -> "MutationExecutor":
        """A nested/child agent gets its own executor, bound to a
        *different* invocation id, with a fresh, empty ledger. It
        receives no reference to this executor's ledger or any of this
        executor's authorizations, so nothing this executor already holds
        is usable through the child (AUTH-013 / DELEG-007's #301-owned
        side: non-inheritance of authorization across the spawn
        boundary)."""
        if child_invocation_id == self._ctx.invocation_id:
            raise AuthorizationReplayError(
                "a spawned child must not share its parent's invocation id"
            )
        child_ctx = InvocationContext(
            invocation_id=child_invocation_id,
            repo_id=self._ctx.repo_id,
            worktree_root=self._ctx.worktree_root,
        )
        return MutationExecutor(child_ctx, AuthorizationLedger())

    def _check_binding(
        self,
        auth: MutationAuthorization,
        *,
        capability: MutationCapability,
        base_sha: Optional[str],
        binding_value: str,
    ) -> None:
        if not isinstance(auth, MutationAuthorization) or not isinstance(auth.channel, TrustedChannel):
            raise UnauthorizedMutationError("authorization is missing or not trusted-channel issued")
        if auth.capability is not capability:
            raise UnauthorizedMutationError(
                f"authorization is for {auth.capability}, not {capability}; "
                "capabilities are never inherited from one another"
            )
        if (
            auth.invocation_id != self._ctx.invocation_id
            or auth.repo_id != self._ctx.repo_id
            or auth.worktree_root != self._ctx.worktree_root
        ):
            raise AuthorizationReplayError(
                "authorization is bound to a different invocation, repository, or worktree"
            )
        if self._ledger.is_consumed(auth):
            raise AuthorizationReplayError("authorization already consumed; single-use, non-replayable")
        if base_sha is not None and auth.base_sha != base_sha:
            raise StaleApprovalError("worktree base has advanced since approval; re-approval required")
        if auth.binding_value != binding_value:
            raise StaleApprovalError("authorized digest/target does not match what was presented")

    def apply_patch(
        self,
        proposal: PatchProposal,
        authorization: MutationAuthorization,
        *,
        current_base_sha: str,
    ) -> ApplyResult:
        self._check_binding(
            authorization,
            capability=MutationCapability.APPLY_PATCH,
            base_sha=current_base_sha,
            binding_value=proposal.digest,
        )
        for rel_path in proposal.target_paths:
            _reject_out_of_scope_path(rel_path)

        root = self._ctx.worktree_root
        before = _snapshot(root)
        proc = subprocess.run(
            ["git", *_SAFE_GIT_FLAGS, "apply", "--whitespace=nowarn", "-"],
            cwd=str(root),
            input=proposal.patch_text,
            capture_output=True,
            text=True,
        )
        # Consume the authorization the moment the apply attempt has run —
        # whether it succeeds or fails, this exact grant is spent.
        self._ledger.consume(authorization)
        if proc.returncode != 0:
            raise MutationAuthorityError(f"git apply failed: {proc.stderr.strip()}")
        after = _snapshot(root)

        if _refs_mutated(before, after):
            raise ScopeEscapeError("APPLY_PATCH must not mutate refs/HEAD")

        changed = _changed_paths(before, after)
        unexpected = changed - proposal.target_paths
        if unexpected:
            raise ScopeEscapeError(
                f"unexpected paths changed beyond authorized scope: {sorted(unexpected)}"
            )
        return ApplyResult(applied_paths=changed, patch_digest=proposal.digest)

    def commit(
        self,
        result: ApplyResult,
        authorization: MutationAuthorization,
        *,
        message: str,
    ) -> CommitResult:
        self._check_binding(
            authorization,
            capability=MutationCapability.COMMIT,
            base_sha=None,
            binding_value=result.patch_digest,
        )
        root = self._ctx.worktree_root
        _run_git(root, ("add", "-A"))
        _run_git(root, ("commit", "-m", message))
        self._ledger.consume(authorization)
        commit_sha = _run_git(root, ("rev-parse", "HEAD")).strip()
        return CommitResult(commit_sha=commit_sha, patch_digest=result.patch_digest)

    def push(
        self,
        commit: CommitResult,
        authorization: MutationAuthorization,
        *,
        remote: str,
        ref: str,
    ) -> None:
        self._check_binding(
            authorization,
            capability=MutationCapability.PUSH,
            base_sha=None,
            binding_value=commit.commit_sha,
        )
        root = self._ctx.worktree_root
        _run_git(root, ("push", remote, ref))
        self._ledger.consume(authorization)


# Governance: fragments that, if present in this module's public function
# signatures, would mean a caller-controlled escape hatch crept into the
# gate (a flag that flips a check open). test_mutation_authority.py checks
# public signatures against these — mirrors
# review_action_authorization.py's PROHIBITED_ESCAPE_HATCH_FRAGMENTS.
PROHIBITED_ESCAPE_HATCH_FRAGMENTS: frozenset[str] = frozenset(
    {
        "override",
        "force",
        "bypass",
        "skip_gate",
        "skip_verification",
        "trust_caller",
        "assume_authorized",
        "disable_scope_check",
        "inherit_parent",
    }
)
