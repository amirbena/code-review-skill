#!/usr/bin/env python3
"""Test-only reference for multi-repository Review Target composition
(Issue #556, epic #555).

Mirrors
skills/local-code-review/policies/multi-repository-review-target.md: root
validation/normalization (including fail-closed duplicate/alias
detection), independent per-member resolution and composition into one
combined Review Target, unresolved-member narrowing, repository-qualified
location rendering, and the "membership is authorization" invariant.

Not runtime logic, not packaged — the packaged Skill is Markdown/YAML
only. This module performs no filesystem or Git I/O itself: the caller
supplies precomputed per-root facts (as a real implementation would after
running `git rev-parse --show-toplevel` / `--git-common-dir`), the same
dependency-injection style as
tests/reference/review/review_base_policy.py.
"""

from __future__ import annotations

import os.path
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence


class RootRejectionReason(Enum):
    """Why one supplied root, on its own, could not become a member."""

    DOES_NOT_EXIST = "does_not_exist"
    NOT_A_GIT_REPOSITORY = "not_a_git_repository"


class MemberUnresolvedReason(Enum):
    """Why a validated, normalized member could not be resolved into the
    combined Review Target (its own base could not be established)."""

    BASE_UNRESOLVED = "base_unresolved"


@dataclass(frozen=True)
class RootFact:
    """Caller-precomputed facts about one supplied path. A real
    implementation resolves ``normalized_root`` via
    ``git rev-parse --show-toplevel`` and ``git_common_dir`` via
    ``git rev-parse --git-common-dir``, run against ``supplied_path``."""

    supplied_path: str
    exists: bool
    is_git_repository: bool
    normalized_root: Optional[str] = None
    git_common_dir: Optional[str] = None


@dataclass(frozen=True)
class RejectedRoot:
    supplied_path: str
    reason: RootRejectionReason


@dataclass(frozen=True)
class DuplicateRootConflict:
    """Two or more supplied paths resolve to the same repository (identical
    normalized root, or two worktrees sharing one Git common directory)."""

    supplied_paths: tuple[str, ...]
    shared_identity: str


@dataclass(frozen=True)
class RootListValidation:
    """Validation and normalization of supplied ("Validation and
    normalization of supplied roots"). A non-empty ``duplicate_conflicts``
    means the *whole* input is rejected, fail-closed — ``valid_roots`` and
    ``rejected_roots`` are both empty in that case, and no per-member
    resolution may proceed."""

    duplicate_conflicts: tuple[DuplicateRootConflict, ...]
    valid_roots: tuple[str, ...] = field(default_factory=tuple)
    rejected_roots: tuple[RejectedRoot, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.duplicate_conflicts


def validate_and_normalize_roots(facts: Sequence[RootFact]) -> RootListValidation:
    """§"Validation and normalization of supplied roots".

    1. Existence / Git-repository check per entry — a failing entry is
       rejected for that entry alone (it becomes an unresolved member
       later, never a whole-input failure).
    2. Duplicate/alias detection among the entries that passed step 1,
       keyed by Git common directory when known (so two worktrees of one
       repository collide) and otherwise by normalized root — fail
       closed for the *whole* input, reported once, before any
       per-member resolution.
    """
    existence_ok: list[RootFact] = []
    rejected: list[RejectedRoot] = []
    for fact in facts:
        if not fact.exists:
            rejected.append(RejectedRoot(fact.supplied_path, RootRejectionReason.DOES_NOT_EXIST))
        elif not fact.is_git_repository:
            rejected.append(RejectedRoot(fact.supplied_path, RootRejectionReason.NOT_A_GIT_REPOSITORY))
        else:
            existence_ok.append(fact)

    groups: dict[str, list[RootFact]] = {}
    for fact in existence_ok:
        identity = fact.git_common_dir or fact.normalized_root or fact.supplied_path
        groups.setdefault(identity, []).append(fact)

    conflicts = tuple(
        DuplicateRootConflict(
            supplied_paths=tuple(f.supplied_path for f in members),
            shared_identity=identity,
        )
        for identity, members in sorted(groups.items())
        if len(members) > 1
    )
    if conflicts:
        return RootListValidation(duplicate_conflicts=conflicts)

    valid_roots = tuple(fact.normalized_root or fact.supplied_path for fact in existence_ok)
    return RootListValidation(
        duplicate_conflicts=(),
        valid_roots=valid_roots,
        rejected_roots=tuple(rejected),
    )


def derive_aliases(roots: Sequence[str]) -> dict[str, str]:
    """A short, stable, human-readable label per member for rendering —
    "Finding location with structural repository identity": the
    directory basename, disambiguated with an increasing parent-path
    suffix on a collision so two members never share a rendered alias."""
    basenames = [os.path.basename(root.rstrip("/")) or root for root in roots]
    aliases: dict[str, str] = {}
    for root, basename in zip(roots, basenames):
        if basenames.count(basename) == 1:
            aliases[root] = basename
    remaining = [root for root in roots if root not in aliases]
    for root in remaining:
        parts = [p for p in root.split("/") if p]
        depth = 1
        while depth <= len(parts):
            candidate = "/".join(parts[-depth:])
            if all(candidate != v for k, v in aliases.items() if k != root) and (
                sum(1 for other in remaining if "/".join([p for p in other.split("/") if p][-depth:]) == candidate)
                == 1
            ):
                aliases[root] = candidate
                break
            depth += 1
        else:
            aliases[root] = root
    return aliases


@dataclass(frozen=True)
class MemberResolution:
    """One member's independent, unchanged single-repository resolution
    outcome — "Per-member resolution — unchanged, run independently"."""

    root: str
    resolved: bool
    base: Optional[str] = None
    branch: Optional[str] = None
    unresolved_reason: Optional[MemberUnresolvedReason] = None


@dataclass(frozen=True)
class CombinedReviewTarget:
    """"Composition into one combined Review Target". No synthetic shared
    base/SHA is ever derived here — each resolved member keeps its own."""

    resolved_members: tuple[MemberResolution, ...]
    unresolved_members: tuple[MemberResolution, ...]

    @property
    def is_empty(self) -> bool:
        return not self.resolved_members


def compose_review_target(resolutions: Sequence[MemberResolution]) -> CombinedReviewTarget:
    """§"Unresolved-member narrowing": an unresolved member narrows the
    combined target rather than failing it, and contributes no findings."""
    resolved = tuple(r for r in resolutions if r.resolved)
    unresolved = tuple(r for r in resolutions if not r.resolved)
    return CombinedReviewTarget(resolved_members=resolved, unresolved_members=unresolved)


def instruction_applies_to_file(
    *, instruction_owner_root: str, file_member_root: str
) -> bool:
    """§"Instruction isolation": a member's instructions apply only to
    files under that same member's own root — never a sibling's."""
    return instruction_owner_root == file_member_root


def ring_expansion_target_is_admitted(
    *, target_root: str, admitted_member_roots: Sequence[str]
) -> bool:
    """§"Ring expansion into a sibling member": a fired trigger's ring may
    resolve into any already-admitted member, never a repository outside
    that set."""
    return target_root in admitted_member_roots


def render_location(
    *, repo_alias: Optional[str], path: str, line_or_range: Optional[str] = None
) -> str:
    """§"Finding location with structural repository identity": the
    leading `<repo-alias>:` qualifier on a multi-repository finding's
    rendered location. A single-repository review (``repo_alias is None``)
    renders exactly as before this convention existed."""
    coordinate = f"{path}:{line_or_range}" if line_or_range else path
    return f"{repo_alias}:{coordinate}" if repo_alias else coordinate


def resolve_effective_membership(
    *,
    explicit_supplied_roots: Sequence[str],
    content_suggested_roots: Sequence[str] = (),
) -> tuple[str, ...]:
    """§"Security: membership cannot be expanded from inside". Only the
    caller's own explicit invocation input can ever contribute a member;
    anything encountered while reviewing (an ``AGENTS.md``/``CLAUDE.md``
    statement, a branch name, a resolved Jira/GitHub-Issue reference, a
    ring-expansion result) is data, never an authorization channel, and is
    unconditionally ignored here regardless of its content."""
    return tuple(explicit_supplied_roots)
