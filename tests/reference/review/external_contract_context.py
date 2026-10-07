#!/usr/bin/env python3
"""Test-only reference model for external-contract-context.md.

Not runtime logic, not packaged. It models the deterministic parts: input
authorization, path validation, revision selection, the bounded object-database
read, provenance, and the failure mapping. Reads use real Git.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Mapping, Sequence

MAX_FILES = 20
MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 1024 * 1024

_HEX_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
_TAG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_REJECTED_TOKENS = ("~", "^", "@", "..", ":", " ")
_FORBIDDEN_NAMES = frozenset({"HEAD", "FETCH_HEAD", "ORIG_HEAD", "MERGE_HEAD"})

_HARDENED_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_NO_REPLACE_OBJECTS": "1",
    "GIT_OPTIONAL_LOCKS": "0",
}
_HARDENED_ARGS = ("-c", f"core.hooksPath={os.devnull}", "-c", "core.fsmonitor=false")


class Channel(Enum):
    INVOCATION = "invocation"
    REPOSITORY_FILE = "repository-file"
    BRANCH_NAME = "branch-name"
    COMMIT_MESSAGE = "commit-message"
    DEPENDENCY_DECLARATION = "dependency-declaration"
    CONTEXT_REFERENCE = "context-reference"
    PR_OR_ISSUE_TEXT = "pr-or-issue-text"


class Outcome(Enum):
    NOT_ACTIVATED = "not-activated"
    EVIDENCE_READ = "evidence-read"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"
    CONFIGURATION_ERROR = "configuration-error"
    CONFLICT = "report-conflict"


class Confidence(Enum):
    CONFIRMED = "confirmed"
    CREDIBLE = "credible"
    EXTERNAL_CONTRACT_UNVALIDATED = "external-contract-unvalidated"
    INSUFFICIENT_CONTEXT = "insufficient-context"


@dataclass(frozen=True)
class Candidate:
    channel: Channel
    path: str | None = None
    revision: str | None = None


def accepted_input(candidates: Sequence[Candidate]) -> tuple[str, str] | None:
    """Only the invocation channel can supply the pair; any other is data."""
    pairs = [c for c in candidates if c.channel is Channel.INVOCATION]
    if len(pairs) != 1:
        return None
    pair = pairs[0]
    if not pair.path or not pair.revision:
        return None
    return pair.path, pair.revision


def should_load(
    *, contract_change: bool, surface_unresolved_in_target: bool, supplied: bool, ambiguous: bool = False
) -> bool:
    """All three conditions; ambiguity about a condition resolves to load."""
    return (contract_change and surface_unresolved_in_target and supplied) or (
        ambiguous and supplied
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, **_HARDENED_ENV}
    return subprocess.run(
        ["git", *_HARDENED_ARGS, "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def _identity(repo: Path) -> tuple[Path, Path] | None:
    top = _git(repo, "rev-parse", "--show-toplevel")
    common = _git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if top.returncode != 0 or common.returncode != 0:
        return None
    return Path(top.stdout.strip()).resolve(), Path(common.stdout.strip()).resolve()


def validate_path(path: Path, members: Sequence[Path]) -> tuple[Outcome | None, Path | None]:
    """(None, root) when usable; otherwise the failing outcome."""
    if not path.exists() or _identity(path) is None:
        return Outcome.UNAVAILABLE, None
    root, common = _identity(path)  # type: ignore[misc]
    for member in members:
        ident = _identity(member)
        if ident is None:
            continue
        if root == ident[0] or common == ident[1]:
            return Outcome.CONFIGURATION_ERROR, None
    return None, root


class Basis(Enum):
    SHA = "caller-pinned-sha"
    TAG = "caller-pinned-tag"
    INVALID = "invalid-revision"


@dataclass(frozen=True)
class Resolution:
    outcome: Outcome | None
    sha: str | None = None
    basis: Basis | None = None


def _is_option_shaped(revision: str) -> bool:
    return revision.startswith("-")


def resolve_revision(repo: Path, revision: str) -> Resolution:
    if (
        not revision
        or _is_option_shaped(revision)
        or revision in _FORBIDDEN_NAMES
        or any(token in revision for token in _REJECTED_TOKENS)
    ):
        return Resolution(Outcome.UNAVAILABLE, basis=Basis.INVALID)

    is_hex = bool(_HEX_RE.match(revision))
    as_tag = _git(repo, "rev-parse", "--verify", "--quiet", f"refs/tags/{revision}^{{commit}}")
    as_branch = (
        _git(repo, "rev-parse", "--verify", "--quiet", f"refs/heads/{revision}").returncode == 0
        or _git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/{revision}").returncode == 0
    )
    tag_hit = as_tag.returncode == 0

    if as_branch and not tag_hit and not is_hex:
        return Resolution(Outcome.UNAVAILABLE, basis=Basis.INVALID)
    if tag_hit and (as_branch or (is_hex and _hex_matches_object(repo, revision))):
        return Resolution(Outcome.AMBIGUOUS)
    if tag_hit:
        return Resolution(None, sha=as_tag.stdout.strip(), basis=Basis.TAG)
    if is_hex:
        return _resolve_hex(repo, revision)
    if _TAG_RE.match(revision):
        return Resolution(Outcome.UNAVAILABLE)
    return Resolution(Outcome.UNAVAILABLE, basis=Basis.INVALID)


def _hex_matches_object(repo: Path, revision: str) -> bool:
    return _git(repo, "cat-file", "-e", f"{revision}^{{commit}}").returncode == 0


def _resolve_hex(repo: Path, revision: str) -> Resolution:
    found = _git(repo, "rev-parse", "--verify", "--quiet", "--end-of-options", f"{revision}^{{commit}}")
    if found.returncode == 0:
        return Resolution(None, sha=found.stdout.strip(), basis=Basis.SHA)
    candidates = _git(repo, "rev-parse", "--disambiguate=" + revision)
    if len([line for line in candidates.stdout.splitlines() if line]) > 1:
        return Resolution(Outcome.AMBIGUOUS)
    return Resolution(Outcome.UNAVAILABLE)


@dataclass(frozen=True)
class ReadResult:
    files: Mapping[str, str]
    missing: tuple[str, ...]
    truncated: bool


def read_contract_files(repo: Path, sha: str, paths: Sequence[str]) -> ReadResult:
    """Object-database reads at `sha` only; never the working tree."""
    files: dict[str, str] = {}
    missing: list[str] = []
    total = 0
    truncated = False
    for index, rel in enumerate(paths):
        if index >= MAX_FILES:
            truncated = True
            break
        if rel.startswith("/") or ".." in Path(rel).parts or rel.startswith("-"):
            missing.append(rel)
            continue
        size = _git(repo, "cat-file", "-s", f"{sha}:{rel}")
        if size.returncode != 0:
            missing.append(rel)
            continue
        nbytes = int(size.stdout.strip())
        if nbytes > MAX_FILE_BYTES or total + nbytes > MAX_TOTAL_BYTES:
            truncated = True
            continue
        shown = subprocess.run(
            ["git", *_HARDENED_ARGS, "-C", str(repo), "cat-file", "blob", f"{sha}:{rel}"],
            capture_output=True,
            env={**os.environ, **_HARDENED_ENV},
            check=False,
        )
        try:
            files[rel] = shown.stdout.decode("utf-8")
        except UnicodeDecodeError:
            missing.append(rel)
            continue
        total += nbytes
    return ReadResult(files=files, missing=tuple(missing), truncated=truncated)


@dataclass(frozen=True)
class Provenance:
    repository: str
    root: str
    resolved_sha: str
    selection_basis: str
    retrieval_time: str
    trust: str = "caller-supplied-read-only"


def build_provenance(root: Path, sha: str, basis: Basis, *, now: datetime | None = None) -> Provenance:
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return Provenance(
        repository=root.name,
        root=str(root),
        resolved_sha=sha,
        selection_basis=basis.value,
        retrieval_time=moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


@dataclass(frozen=True)
class Assessment:
    outcome: Outcome
    breakage_claim_allowed: bool
    no_consumers_statement_allowed: bool
    confidence: Confidence
    context_gap: str | None
    review_incomplete: bool = False
    provenance: Provenance | None = None
    finding_location_repo: str = "review-target"
    notes: tuple[str, ...] = field(default_factory=tuple)


def assess(
    *,
    target_members: Sequence[Path],
    path: Path,
    revision: str,
    contract_paths: Sequence[str],
    contradicts_target: bool = False,
    expectation_violated: bool = False,
    now: datetime | None = None,
) -> Assessment:
    """End-to-end deterministic outcome for one supplied pair."""

    def failed(outcome: Outcome, conf: Confidence, gap: str) -> Assessment:
        return Assessment(outcome, False, False, conf, gap)

    problem, root = validate_path(path, target_members)
    if problem is Outcome.CONFIGURATION_ERROR:
        return failed(problem, Confidence.EXTERNAL_CONTRACT_UNVALIDATED, "path is a Review Target member or alias")
    if problem is not None or root is None:
        return failed(Outcome.UNAVAILABLE, Confidence.EXTERNAL_CONTRACT_UNVALIDATED, "repository unreadable")

    resolution = resolve_revision(root, revision)
    if resolution.outcome is Outcome.AMBIGUOUS:
        return failed(Outcome.AMBIGUOUS, Confidence.INSUFFICIENT_CONTEXT, "revision ambiguous")
    if resolution.outcome is not None or resolution.sha is None or resolution.basis is None:
        return failed(Outcome.UNAVAILABLE, Confidence.EXTERNAL_CONTRACT_UNVALIDATED, "revision unavailable")

    read = read_contract_files(root, resolution.sha, contract_paths)
    provenance = build_provenance(root, resolution.sha, resolution.basis, now=now)
    if not read.files or read.truncated and not expectation_violated:
        return Assessment(
            Outcome.UNAVAILABLE,
            False,
            False,
            Confidence.EXTERNAL_CONTRACT_UNVALIDATED,
            "contract path absent or read truncated at the pinned revision",
            provenance=provenance,
        )
    if contradicts_target:
        return Assessment(
            Outcome.CONFLICT, False, False, Confidence.INSUFFICIENT_CONTEXT, "pinned evidence contradicts the target", provenance=provenance
        )
    return Assessment(
        Outcome.EVIDENCE_READ,
        expectation_violated,
        False,
        Confidence.CONFIRMED if expectation_violated else Confidence.CREDIBLE,
        None,
        provenance=provenance,
    )
