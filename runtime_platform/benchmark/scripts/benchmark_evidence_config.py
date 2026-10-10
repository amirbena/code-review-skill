"""Pure validation of the manifest's `evidence` block (no git, no subprocess).

Contract: `runtime_platform/benchmark/scheduled-operations/private-evidence-repository.md` §4.1-§4.4.
Shared by the manifest validator, the execution entrypoints and the publisher.
"""

from __future__ import annotations

import re

PHASE_PRE_CUTOVER = "pre_cutover"
PHASE_PRIVATE = "private"
PHASES = (PHASE_PRE_CUTOVER, PHASE_PRIVATE)

_BLOCK_KEYS = {"phase", "repository", "namespaces", "history_branch"}
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_NAMESPACE_RE = re.compile(r"^claude/[a-z][a-z0-9-]*-$")
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$")


class DestinationMisconfigured(RuntimeError):
    """The evidence destination is missing, invalid, unproven, or breaks its phase's rule (exit 2)."""


def validate_evidence_block(block: object, source_repository: object) -> list[str]:
    """Every problem with a manifest `evidence` block; empty means valid (matrix V2, V4, V5, V7)."""
    if not isinstance(block, dict):
        return ["evidence: must be an object"]
    errors = [f"evidence: missing field {k!r}" for k in sorted(_BLOCK_KEYS - block.keys())]
    errors += [f"evidence: unknown field {k!r}" for k in sorted(block.keys() - _BLOCK_KEYS)]
    phase, repository = block.get("phase"), block.get("repository")
    if "phase" in block and phase not in PHASES:
        errors.append(f"evidence.phase: must be one of {', '.join(PHASES)}")
    if "repository" in block and (not isinstance(repository, str) or not _REPO_RE.match(repository)):
        errors.append("evidence.repository: must be an 'owner/name' identity")
    elif isinstance(repository, str) and isinstance(source_repository, str):
        same = repository.lower() == source_repository.lower()
        if phase == PHASE_PRE_CUTOVER and not same:
            errors.append("evidence.repository: in pre_cutover it must equal the source repository")
        if phase == PHASE_PRIVATE and same:
            errors.append("evidence.repository: in private it must differ from the source repository")
    namespaces = block.get("namespaces")
    if "namespaces" in block:
        if not isinstance(namespaces, list) or not namespaces:
            errors.append("evidence.namespaces: must be a non-empty list")
        else:
            for ns in namespaces:
                if not isinstance(ns, str) or not _NAMESPACE_RE.match(ns):
                    errors.append(f"evidence.namespaces: {ns!r} must be a 'claude/<name>-' prefix")
            if len(set(map(str, namespaces))) != len(namespaces):
                errors.append("evidence.namespaces: duplicate entries")
    branch = block.get("history_branch")
    if "history_branch" in block and (not isinstance(branch, str) or not _BRANCH_RE.match(branch) or branch.startswith("claude/")):
        errors.append("evidence.history_branch: must be a branch name outside claude/")
    return errors


