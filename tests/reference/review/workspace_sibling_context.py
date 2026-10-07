#!/usr/bin/env python3
"""Test-only reference model for shared/policies/workspace-sibling-context.md.

Not runtime logic, not packaged. It models the deterministic parts: grant
intake, availability, bounded immediate-child discovery with exclusion,
nomination, `workspace-resolved` selection, the object-database read with the
deny-list, provenance, publication surfaces, and the failure mapping. Reads
use real Git through the #133 reference mechanism.
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping, Sequence

from tests.reference.review import external_contract_context as ecc

MAX_LISTING = 200
MAX_SIBLINGS = 3

BASIS = "workspace-resolved"
TRUST = "workspace-granted-read-only"

_DENY_NAMES = (
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.jks", "id_rsa*", "id_ed25519*",
    "credentials*", "*.credentials", ".netrc", ".npmrc", ".pypirc", "*.tfvars", "secrets.*",
    "secret.*", "*.token", "token.*",
)
_DENY_PARTS = (".aws", ".ssh", ".gnupg")
_SECRET_RE = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
    r"|AKIA[0-9A-Z]{16}"
    r"|(?i:(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+))"
)


class Adapter(Enum):
    LOCAL = "local"
    GITHUB = "github"


class Outcome(Enum):
    NOT_ACTIVATED = "not-activated"
    GRANT_REJECTED = "grant-rejected"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"
    CAP_REACHED = "cap-reached"
    UNAVAILABLE = "unavailable"
    EVIDENCE_READ = "evidence-read"
    CONFLICT = "report-conflict"


class SignalKind(Enum):
    SERVICE_REF = "service-reference"
    API_REF = "api-reference"
    EVENT = "event-identifier"
    SCHEMA = "schema-file"
    CONFIG = "configuration-reference"
    IMPORT = "import-declaration"
    DOC = "documentation-reference"
    NAME_MATCH = "name-match"


@dataclass(frozen=True)
class Signal:
    kind: SignalKind
    target: str


@dataclass(frozen=True)
class PrIdentity:
    """The PR's own repository by identity, not only by path."""

    owner_name: str
    commits: frozenset[str] = frozenset()
    checkout: Path | None = None


@dataclass(frozen=True)
class Review:
    adapter: Adapter
    members: Sequence[Path]
    grant: Path | None = None
    explicit_repos: Sequence[Path] = ()
    pr: PrIdentity | None = None
    local_fs_access: bool = True
    is_worker: bool = False


def accepted_grant(candidates: Sequence[ecc.Candidate]) -> str | None:
    """Only the invocation channel can supply the root; any other is data."""
    roots = [c.path for c in candidates if c.channel is ecc.Channel.INVOCATION and c.path]
    return roots[0] if len(roots) == 1 else None


def should_load(
    *,
    grant_supplied: bool,
    eligible_question: bool,
    adapter: Adapter = Adapter.LOCAL,
    local_fs_access: bool = True,
    is_worker: bool = False,
    ambiguous: bool = False,
) -> bool:
    if not grant_supplied or is_worker:
        return False
    if adapter is Adapter.GITHUB and not local_fs_access:
        return False
    return eligible_question or ambiguous


def validate_grant(root: Path, members: Sequence[Path]) -> Outcome | None:
    if not root.is_dir() or not os.access(root, os.R_OK | os.X_OK):
        return Outcome.GRANT_REJECTED
    real = root.resolve()
    for member in members:
        ident = ecc._identity(member)
        if ident is not None and ident[0] == real:
            return Outcome.GRANT_REJECTED
    return None


@dataclass(frozen=True)
class Discovery:
    candidates: tuple[Path, ...] = ()
    excluded: Mapping[str, str] = field(default_factory=dict)
    truncated: bool = False


def _is_git_root(path: Path) -> bool:
    if not (path / ".git").exists():
        return False
    ident = ecc._identity(path)
    return ident is not None and ident[0] == path.resolve()


def _origin(path: Path) -> str:
    out = ecc._git(path, "config", "--get", "remote.origin.url")
    return out.stdout.strip() if out.returncode == 0 else ""


def discover(review: Review) -> Discovery:
    """One non-recursive listing of the granted root's immediate children."""
    assert review.grant is not None
    root = review.grant.resolve()
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return Discovery()
    truncated = len(names) > MAX_LISTING
    member_ids = [i for i in (ecc._identity(m) for m in review.members) if i]
    member_ids += [i for i in (ecc._identity(r) for r in review.explicit_repos) if i]
    pr_ids = [i for i in [ecc._identity(review.pr.checkout)] if i] if review.pr and review.pr.checkout else []
    found: dict[Path, Path] = {}
    excluded: dict[str, str] = {}
    for name in names[:MAX_LISTING]:
        entry = root / name
        try:
            real = entry.resolve(strict=True)
        except (OSError, RuntimeError):
            excluded[name] = "unresolvable-link"
            continue
        if entry.is_symlink() and real != root and root not in real.parents:
            excluded[name] = "symlink-escape"
            continue
        if not real.is_dir() or not _is_git_root(real):
            continue
        ident = ecc._identity(real)
        assert ident is not None
        if any(ident[0] == m[0] or ident[1] == m[1] for m in member_ids):
            excluded[name] = "member-or-alias"
            continue
        if any(ident[0] == p[0] or ident[1] == p[1] for p in pr_ids) or _is_pr_repo(review.pr, real):
            excluded[name] = "pr-repository"
            continue
        found.setdefault(real, real)
    return Discovery(tuple(found), excluded, truncated)


def _owner_name(url: str) -> str:
    """Exact normalized `owner/name` from an HTTPS or SSH remote URL."""
    tail = re.split(r"[:/]", url.strip().rstrip("/").removesuffix(".git").rstrip("/"))[-2:]
    return "/".join(tail).lower() if len(tail) == 2 and all(tail) else ""


def _is_pr_repo(pr: PrIdentity | None, repo: Path) -> bool:
    if pr is None:
        return False
    if _owner_name(_origin(repo)) == pr.owner_name.lower():
        return True
    head = ecc._git(repo, "rev-parse", "--verify", "--quiet", "HEAD")
    return head.returncode == 0 and head.stdout.strip() in pr.commits


@dataclass(frozen=True)
class Nomination:
    outcome: Outcome
    candidate: Path | None = None
    considered: tuple[str, ...] = ()


def nominate(candidates: Sequence[Path], signals: Sequence[Signal]) -> Nomination:
    """Nomination narrows; a candidate absent from discovery is never nominated."""
    hits: dict[Path, set[SignalKind]] = {}
    for signal in signals:
        for cand in candidates:
            if cand.name == signal.target:
                hits.setdefault(cand, set()).add(signal.kind)
    names = tuple(sorted(c.name for c in hits))
    if not hits:
        return Nomination(Outcome.UNRESOLVED)
    if len(hits) > 1:
        return Nomination(Outcome.AMBIGUOUS, considered=names)
    (cand, kinds), = hits.items()
    if kinds == {SignalKind.NAME_MATCH}:
        return Nomination(Outcome.AMBIGUOUS, considered=names)
    return Nomination(Outcome.EVIDENCE_READ, cand, names)


@dataclass(frozen=True)
class Head:
    sha: str | None
    dirty: bool = False


def resolve_head(repo: Path) -> Head:
    """Committed HEAD to a full SHA once; detached or unborn is unavailable."""
    if ecc._git(repo, "symbolic-ref", "--quiet", "HEAD").returncode != 0:
        return Head(None)
    found = ecc._git(repo, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if found.returncode != 0:
        return Head(None)
    status = ecc._git(repo, "status", "--porcelain")
    return Head(found.stdout.strip(), dirty=bool(status.stdout.strip()))


def is_denied(rel: str) -> bool:
    parts = tuple(part.lower() for part in Path(rel).parts)
    if any(part in _DENY_PARTS for part in parts) or "/".join(parts) == ".git/config":
        return True
    return any(fnmatch.fnmatchcase(parts[-1], pattern) for pattern in _DENY_NAMES)


def redact(text: str) -> str:
    return _SECRET_RE.sub("[REDACTED]", text)


@dataclass(frozen=True)
class Provenance:
    repository: str
    resolved_sha: str
    selection_basis: str
    retrieval_time: str
    trust: str
    dirty: bool

    @property
    def reference(self) -> str:
        return f"{self.repository}@{self.resolved_sha[:7]}"


@dataclass(frozen=True)
class Resolution:
    outcome: Outcome
    files: Mapping[str, str] = field(default_factory=dict)
    skipped: tuple[str, ...] = ()
    provenance: Provenance | None = None
    context_gap: str | None = None
    breakage_claim_allowed: bool = False
    absence_claim_allowed: bool = False
    can_confirm_alone: bool = False
    review_incomplete: bool = False
    finding_location_repo: str = "review-target"


class Resolver:
    """One per review; owns the listing cache, caps, and the read trace."""

    def __init__(self, review: Review) -> None:
        self.review = review
        self.trace: list[tuple[str, ...]] = []
        self._discovery: Discovery | None = None
        self._siblings: set[Path] = set()
        self._rejected = False

    def _gap(self, outcome: Outcome, gap: str, **kw) -> Resolution:
        return Resolution(outcome, context_gap=gap, **kw)

    def resolve(
        self,
        signals: Sequence[Signal],
        paths: Sequence[str],
        *,
        explicit_resolved: bool = False,
        contradicts_target: bool = False,
        now: datetime | None = None,
    ) -> Resolution:
        review = self.review
        if review.grant is None or review.is_worker or explicit_resolved:
            return Resolution(Outcome.NOT_ACTIVATED)
        if review.adapter is Adapter.GITHUB and not review.local_fs_access:
            return Resolution(Outcome.NOT_ACTIVATED)
        if self._discovery is None:
            problem = validate_grant(review.grant, review.members)
            if problem is not None:
                self._rejected = True
                self._discovery = Discovery()
                self.trace.append(("rejected-grant",))
            else:
                self.trace.append(("list", review.grant.name))
                self._discovery = discover(review)
        if self._rejected:
            return self._gap(Outcome.GRANT_REJECTED, "workspace grant rejected")
        nomination = nominate(self._discovery.candidates, signals)
        if nomination.outcome is Outcome.UNRESOLVED:
            return self._gap(Outcome.UNRESOLVED, "no sibling nominated")
        if nomination.outcome is Outcome.AMBIGUOUS:
            return self._gap(
                Outcome.AMBIGUOUS, "ambiguous sibling candidates: " + ", ".join(nomination.considered)
            )
        sibling = nomination.candidate
        assert sibling is not None
        if sibling not in self._siblings and len(self._siblings) >= MAX_SIBLINGS:
            return self._gap(Outcome.CAP_REACHED, f"sibling cap of {MAX_SIBLINGS} reached")
        self._siblings.add(sibling)
        head = resolve_head(sibling)
        if head.sha is None:
            return self._gap(Outcome.UNAVAILABLE, f"{sibling.name} HEAD unborn, detached, or unresolvable")
        allowed = [p for p in paths if not is_denied(p)]
        skipped = tuple(p for p in paths if is_denied(p))
        for rel in allowed:
            self.trace.append(("read", sibling.name, head.sha, rel))
        read = ecc.read_contract_files(sibling, head.sha, allowed)
        moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        provenance = Provenance(
            sibling.name, head.sha, BASIS, moment.strftime("%Y-%m-%dT%H:%M:%SZ"), TRUST, head.dirty
        )
        if not read.files or read.truncated:
            return self._gap(
                Outcome.UNAVAILABLE,
                f"{sibling.name}@{head.sha[:7]}: path absent or read truncated",
                skipped=skipped,
                provenance=provenance,
            )
        if contradicts_target:
            return Resolution(
                Outcome.CONFLICT, read.files, skipped, provenance,
                "sibling evidence contradicts the Review Target",
            )
        return Resolution(Outcome.EVIDENCE_READ, read.files, skipped, provenance)


def reevaluate(resolution: Resolution, decides: Callable[[Mapping[str, str]], bool]) -> str:
    """Only the one affected question: resolved, or fall through unchanged."""
    if resolution.outcome is Outcome.EVIDENCE_READ and decides(resolution.files):
        return "resolved"
    return "unresolved"


def worker_brief(resolver: Resolver) -> Mapping[str, object]:
    """What a worker or parallel-review copy receives: nothing from the grant."""
    return {"workspace_root": None, "listing": None, "sibling_evidence": None}


def render(resolution: Resolution, rel: str, *, published: bool, conclusion: str, excerpt: str = "") -> str:
    """Published surfaces carry a conclusion plus a reference; never content."""
    prov = resolution.provenance
    assert prov is not None
    ref = f"{prov.reference}:{rel}"
    dirty = " (dirty sibling; committed state)" if prov.dirty else ""
    if published or not excerpt:
        return f"{conclusion} See {ref}{dirty}."
    return f"{conclusion} See {ref}{dirty}: {redact(excerpt)}"
