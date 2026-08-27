#!/usr/bin/env python3
"""Test-only reference for hierarchical repository-instruction resolution.

Mirrors shared/policies/repository-instructions.md. Not runtime logic, not packaged.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


class InstructionResolutionError(RuntimeError):
    """An applicable instruction file could not be resolved safely."""


@dataclass(frozen=True)
class InstructionFile:
    path: str
    content: str
    digest: str


@dataclass(frozen=True)
class RepositoryInstructionContext:
    repository_snapshot: str
    by_changed_file: tuple[tuple[str, tuple[InstructionFile, ...]], ...]
    identity: str

    def chain_for(self, changed_file: str) -> tuple[InstructionFile, ...]:
        return dict(self.by_changed_file)[changed_file]


def _normalize_changed_file(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise InstructionResolutionError(f"unsafe changed-file path: {value!r}")
    return path


def _candidate_paths(path: PurePosixPath) -> tuple[PurePosixPath, ...]:
    directories = [PurePosixPath()]
    current = PurePosixPath()
    for part in path.parent.parts:
        current /= part
        directories.append(current)
    return tuple(directory / "AGENTS.md" for directory in directories)


def resolve_repository_instructions(
    root: Path,
    changed_files: Iterable[str],
    *,
    repository_snapshot: str,
) -> RepositoryInstructionContext:
    """Resolve root-to-specific AGENTS.md chains for the supplied target files."""
    root = root.resolve(strict=True)
    normalized = tuple(sorted({_normalize_changed_file(path).as_posix() for path in changed_files}))
    candidates = {candidate for path in normalized for candidate in _candidate_paths(PurePosixPath(path))}
    loaded: dict[PurePosixPath, InstructionFile] = {}
    for candidate in sorted(candidates, key=lambda item: (len(item.parts), item.as_posix())):
        target = root / candidate
        try:
            if not target.exists():
                continue
            resolved = target.resolve(strict=True)
            if root != resolved and root not in resolved.parents:
                raise InstructionResolutionError(f"instruction path escapes repository: {candidate}")
            if not resolved.is_file():
                raise InstructionResolutionError(f"instruction path is not a file: {candidate}")
            content = resolved.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise InstructionResolutionError(f"cannot read applicable instruction {candidate}: {exc}") from exc
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        loaded[candidate] = InstructionFile(candidate.as_posix(), content, digest)

    mapping = tuple(
        (
            path,
            tuple(loaded[candidate] for candidate in _candidate_paths(PurePosixPath(path)) if candidate in loaded),
        )
        for path in normalized
    )
    serializable = {
        "repository_snapshot": repository_snapshot,
        "by_changed_file": [
            [path, [[item.path, item.digest] for item in chain]] for path, chain in mapping
        ],
    }
    identity = hashlib.sha256(
        json.dumps(serializable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return RepositoryInstructionContext(repository_snapshot, mapping, identity)
