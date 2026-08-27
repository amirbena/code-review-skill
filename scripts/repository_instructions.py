#!/usr/bin/env python3
"""Test-only reference for repository-instruction discovery and resolution.

Mirrors shared/policies/repository-instructions.md. Not runtime logic, not packaged.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence


class InstructionResolutionError(RuntimeError):
    """An applicable instruction path is unsafe and is rejected outright
    (absolute, `..`, or a symlink resolving outside the repository snapshot)."""


class InstructionKind(Enum):
    AGENTS = "AGENTS.md"
    CLAUDE = "CLAUDE.md"


# Discovery looks for both names along a changed file's ancestry. Listing
# AGENTS.md before CLAUDE.md in a directory is a deterministic read order, not
# a precedence claim — precedence is `declared_precedence` / `resolve_conflict`.
_INSTRUCTION_NAMES: tuple[tuple[str, InstructionKind], ...] = (
    ("AGENTS.md", InstructionKind.AGENTS),
    ("CLAUDE.md", InstructionKind.CLAUDE),
)


class UnresolvedReason(Enum):
    DANGLING_SYMLINK = "dangling_symlink"
    UNREADABLE = "unreadable"
    MALFORMED_ENCODING = "malformed_encoding"
    NOT_A_FILE = "not_a_file"


@dataclass(frozen=True)
class InstructionFile:
    path: str
    kind: InstructionKind
    content: str
    digest: str


@dataclass(frozen=True)
class UnresolvedInstruction:
    """An applicable instruction path that exists conceptually but could not be
    read safely — surfaced so Repository Context is known-incomplete, never
    silently treated as absent."""

    path: str
    kind: InstructionKind
    reason: UnresolvedReason


@dataclass(frozen=True)
class RepositoryInstructionContext:
    repository_snapshot: str
    by_changed_file: tuple[tuple[str, tuple[InstructionFile, ...]], ...]
    unresolved: tuple[UnresolvedInstruction, ...]
    identity: str

    @property
    def is_complete(self) -> bool:
        """False when an applicable instruction file could not be read; a
        genuinely missing file does not make the context incomplete."""
        return not self.unresolved

    def chain_for(self, changed_file: str) -> tuple[InstructionFile, ...]:
        return dict(self.by_changed_file)[changed_file]

    def kind_chain_for(self, changed_file: str, kind: InstructionKind) -> tuple[InstructionFile, ...]:
        return tuple(item for item in self.chain_for(changed_file) if item.kind is kind)


# --- Discovery ----------------------------------------------------------------


def _normalize_changed_file(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise InstructionResolutionError(f"unsafe changed-file path: {value!r}")
    return path


def _candidate_paths(path: PurePosixPath) -> tuple[tuple[PurePosixPath, InstructionKind], ...]:
    """Root-to-most-specific: repo root, then each ancestor directory up to the
    file's own directory; both instruction names per directory."""
    directories = [PurePosixPath()]
    current = PurePosixPath()
    for part in path.parent.parts:
        current /= part
        directories.append(current)
    return tuple(
        (directory / name, kind)
        for directory in directories
        for name, kind in _INSTRUCTION_NAMES
    )


def _inside_root(resolved: Path, root: Path) -> bool:
    return resolved == root or root in resolved.parents


def _read_candidate(
    candidate: PurePosixPath,
    kind: InstructionKind,
    root: Path,
    loaded: dict[PurePosixPath, InstructionFile],
    unresolved: list[UnresolvedInstruction],
) -> None:
    """Resolve one candidate path. Missing -> nothing. Unsafe -> raise.
    Present-but-unreadable -> record as unresolved (context incomplete)."""
    target = root / candidate
    posix = candidate.as_posix()

    if target.is_symlink():
        resolved = target.resolve()  # follow the link chain without requiring the tail to exist
        if not _inside_root(resolved, root):
            raise InstructionResolutionError(
                f"instruction symlink escapes repository snapshot: {posix}"
            )
        if not resolved.exists():
            unresolved.append(UnresolvedInstruction(posix, kind, UnresolvedReason.DANGLING_SYMLINK))
            return
    elif not target.exists():
        return  # genuinely missing — a valid, complete outcome
    else:
        resolved = target.resolve(strict=True)
        if not _inside_root(resolved, root):
            raise InstructionResolutionError(f"instruction path escapes repository snapshot: {posix}")

    if not resolved.is_file():
        unresolved.append(UnresolvedInstruction(posix, kind, UnresolvedReason.NOT_A_FILE))
        return
    try:
        content = resolved.read_text(encoding="utf-8")
    except UnicodeError:
        unresolved.append(UnresolvedInstruction(posix, kind, UnresolvedReason.MALFORMED_ENCODING))
        return
    except OSError:
        unresolved.append(UnresolvedInstruction(posix, kind, UnresolvedReason.UNREADABLE))
        return
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    loaded[candidate] = InstructionFile(posix, kind, content, digest)


def resolve_repository_instructions(
    root: Path,
    changed_files: Iterable[str],
    *,
    repository_snapshot: str,
) -> RepositoryInstructionContext:
    """Resolve each changed file's root-to-specific applicable instruction
    chain (hierarchical AGENTS.md plus any applicable CLAUDE.md on the same
    ancestry) from one snapshot, deduplicating candidate reads."""
    root = root.resolve(strict=True)
    normalized = tuple(sorted({_normalize_changed_file(path).as_posix() for path in changed_files}))

    candidates: dict[PurePosixPath, InstructionKind] = {}
    for path in normalized:
        for candidate, kind in _candidate_paths(PurePosixPath(path)):
            candidates.setdefault(candidate, kind)

    loaded: dict[PurePosixPath, InstructionFile] = {}
    unresolved: list[UnresolvedInstruction] = []
    for candidate in sorted(candidates, key=lambda item: (len(item.parts), item.as_posix())):
        _read_candidate(candidate, candidates[candidate], root, loaded, unresolved)

    mapping = tuple(
        (
            path,
            tuple(
                loaded[candidate]
                for candidate, _ in _candidate_paths(PurePosixPath(path))
                if candidate in loaded
            ),
        )
        for path in normalized
    )
    unresolved_sorted = tuple(sorted(unresolved, key=lambda item: (item.path, item.reason.value)))
    serializable = {
        "repository_snapshot": repository_snapshot,
        "by_changed_file": [
            [path, [[item.path, item.kind.value, item.digest] for item in chain]]
            for path, chain in mapping
        ],
        "unresolved": [[item.path, item.kind.value, item.reason.value] for item in unresolved_sorted],
    }
    identity = hashlib.sha256(
        json.dumps(serializable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return RepositoryInstructionContext(repository_snapshot, mapping, unresolved_sorted, identity)


# --- AGENTS.md vs. CLAUDE.md precedence -------------------------------------
#
# The policy allows AGENTS.md to win over CLAUDE.md ONLY when the target
# repository itself declares that relationship. There is no universal rule.


class InstructionPrecedence(Enum):
    NONE_DECLARED = "none_declared"
    CLAUDE_DEFERS_TO_AGENTS = "claude_defers_to_agents"


class ConflictOutcome(Enum):
    NO_CONFLICT = "no_conflict"
    RESOLVED_BY_DECLARED_PRECEDENCE = "resolved_by_declared_precedence"
    AMBIGUOUS_SURFACED = "ambiguous_surfaced"


# A CLAUDE.md that names AGENTS.md together with one of these establishes a
# repository-declared deferral. Absent such a statement, precedence is undeclared.
_DEFERRAL_SIGNALS: tuple[str, ...] = (
    "canonical",
    "defer to agents.md",
    "defers to agents.md",
    "takes precedence",
    "authoritative",
    "follow agents.md",
    "read and follow",
    "instruction source",
    "source of truth",
)


def _claude_defers_to_agents(text: str) -> bool:
    lowered = " ".join(text.lower().split())
    if "agents.md" not in lowered:
        return False
    return any(signal in lowered for signal in _DEFERRAL_SIGNALS)


def declared_precedence(chain: Sequence[InstructionFile]) -> InstructionPrecedence:
    """Repository-declared precedence only: an applicable CLAUDE.md stating it
    defers to AGENTS.md. Never assume AGENTS.md wins otherwise."""
    for item in chain:
        if item.kind is InstructionKind.CLAUDE and _claude_defers_to_agents(item.content):
            return InstructionPrecedence.CLAUDE_DEFERS_TO_AGENTS
    return InstructionPrecedence.NONE_DECLARED


def resolve_conflict(
    chain: Sequence[InstructionFile],
    *,
    materially_conflicts: bool,
) -> ConflictOutcome:
    """Resolve an AGENTS.md/CLAUDE.md disagreement the reviewer judged
    material. Declared deferral resolves it; otherwise it is surfaced as
    ambiguous — never silently decided."""
    has_agents = any(item.kind is InstructionKind.AGENTS for item in chain)
    has_claude = any(item.kind is InstructionKind.CLAUDE for item in chain)
    if not (has_agents and has_claude) or not materially_conflicts:
        return ConflictOutcome.NO_CONFLICT
    if declared_precedence(chain) is InstructionPrecedence.CLAUDE_DEFERS_TO_AGENTS:
        return ConflictOutcome.RESOLVED_BY_DECLARED_PRECEDENCE
    return ConflictOutcome.AMBIGUOUS_SURFACED


def context_is_graded_ready(context: RepositoryInstructionContext) -> bool:
    """An unreadable applicable instruction file never becomes a clean/graded
    result on its own — it must be surfaced first."""
    return context.is_complete
