#!/usr/bin/env python3
"""The evidence-destination contract: where benchmark evidence is written and read.

Contract: `runtime_platform/benchmark/scheduled-operations/private-evidence-repository.md` §4-§5.
Every producer (seal) and consumer (baseline history, stop-condition reads) resolves its git
remote here, so no entrypoint addresses `origin` implicitly and none can fall back to another
repository. Stdlib only; never touches GitHub's API or a model. It imports no execution module at load time (the
publisher shares its validation), so `benchmark_seal` and `benchmark_baseline` load lazily.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from runtime_platform.benchmark.scripts.benchmark_evidence_config import (  # noqa: F401
    PHASE_PRE_CUTOVER,
    PHASE_PRIVATE,
    PHASES,
    DestinationMisconfigured,
    validate_evidence_block,
)

EXIT_MISCONFIGURED = 2  # evidence-destination-misconfigured
EXIT_UNAVAILABLE = 3  # evidence-store-unavailable / seal-unconfirmed

STATUS_MISCONFIGURED = "evidence-destination-misconfigured"
STATUS_UNAVAILABLE = "evidence-store-unavailable"
STATUS_UNCONFIRMED = "seal-unconfirmed"

# The checkout's own remote, used only in `pre_cutover` and only after the identity proof.
CHECKOUT_REMOTE = "origin"
# A local bare repository can stand in for a remote only when the test harness sets this.
TEST_LOCAL_REMOTES_ENV = "BENCHMARK_EVIDENCE_TEST_LOCAL_REMOTES"

GIT_TIMEOUT_S = 60


class StoreUnavailable(RuntimeError):
    """The proven evidence store could not be reached, read, or written (exit 3)."""

    def __init__(self, message: str, *, error_class: str = "unknown", status: str = STATUS_UNAVAILABLE) -> None:
        super().__init__(message)
        self.error_class, self.status = error_class, status


@dataclass(frozen=True)
class Destination:
    """One resolved, identity-proven evidence destination; the only handle producers and consumers use."""

    repository: str
    phase: str
    remote: str  # the transport the checks proved to be `repository`; never printed unredacted
    namespaces: tuple[str, ...]
    history_branch: str
    repo_root: Path

    def check_namespace(self, ref: str) -> None:
        if not any(ref.startswith(ns) and len(ref) > len(ns) for ns in self.namespaces):
            raise DestinationMisconfigured(f"refusing {ref!r}: not under a registered evidence namespace")

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                ["git", *args], cwd=str(self.repo_root), capture_output=True, text=True,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"}, timeout=GIT_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired as exc:
            raise StoreUnavailable(f"git {args[0]} against the evidence store timed out", error_class="timeout") from exc
        except OSError as exc:
            raise StoreUnavailable(f"git {args[0]} could not run: {type(exc).__name__}", error_class="git-unavailable") from exc

    def _ls_remote(self, *patterns: str) -> list[str]:
        proc = self._git("ls-remote", "--heads", self.remote, *patterns)
        if proc.returncode != 0:
            raise StoreUnavailable(
                f"cannot read the evidence store {self.repository}: {classify_git_error(proc.stderr)}",
                error_class=classify_git_error(proc.stderr),
            )
        return [line.split()[1].removeprefix("refs/heads/") for line in proc.stdout.splitlines() if line.strip()]

    def preflight(self) -> None:
        """Read the history branch before any model cost is spent (exit 3 when the store is unreachable)."""
        self._ls_remote(f"refs/heads/{self.history_branch}")

    def list_refs(self, prefix: str) -> list[str]:
        """Ref names under a registered prefix on this store; a failed read is never an empty list."""
        self.check_namespace(prefix + "x")
        return self._ls_remote(f"refs/heads/{prefix}*")

    def seal(self, ref: str, files: Mapping[str, bytes], message: str) -> str:
        """Plain push of one orphan commit to this store only; the allow-list is checked first."""
        self.check_namespace(ref)
        from runtime_platform.benchmark.scripts import benchmark_seal as seal

        try:
            return seal.seal_to_ref(self.repo_root, self.remote, ref, files, message)
        except seal.SealUnconfirmedError as exc:
            raise StoreUnavailable(str(exc), error_class="read-back", status=STATUS_UNCONFIRMED) from exc
        except seal.SealError as exc:
            raise StoreUnavailable(
                f"the seal was not written ({classify_git_error(str(exc))}): {_excerpt(str(exc))}", error_class=classify_git_error(str(exc))
            ) from exc

    def history(self) -> Any:
        from runtime_platform.benchmark.scripts.benchmark_baseline import GitRefHistory

        return GitRefHistory(self.repo_root, remote=self.remote, branch=self.history_branch)

    def location(self, ref: str, commit: str) -> str:
        return f"{self.repository}:{ref}@{commit}"


def _excerpt(text: str, limit: int = 200) -> str:
    """A bounded, single-line, URL-redacted excerpt of a git error for the operator."""
    return redact(" ".join(text.split()))[:limit]


def classify_git_error(text: str) -> str:
    """A coarse, content-free class for a git failure; the raw text may carry URLs."""
    lowered = text.lower()
    for needle, label in (
        ("timed out", "timeout"),
        ("authentication", "unauthorized"), ("permission denied", "unauthorized"), ("403", "unauthorized"),
        ("could not read from remote", "unreachable"), ("repository not found", "not-found"),
        ("could not resolve", "unreachable"), ("unable to access", "unreachable"), ("does not appear to be a git", "not-found"),
        ("rejected", "rejected"), ("protected branch", "rejected"), ("declined", "rejected"),
    ):
        if needle in lowered:
            return label
    return "unknown"


def _remote_url(repo_root: Path, remote: str) -> str:
    proc = subprocess.run(
        ["git", "remote", "get-url", remote], cwd=str(repo_root), capture_output=True, text=True, timeout=GIT_TIMEOUT_S
    )
    if proc.returncode == 0:
        return proc.stdout.strip()
    if "://" in remote or re.match(r"^[\w.-]+@[\w.-]+:", remote) or remote.startswith(("/", "./", "../")):
        return remote
    raise DestinationMisconfigured("the evidence remote is neither a configured remote name nor a URL")


def redact(url: str) -> str:
    return re.sub(r"(://)[^/@]+@", r"\1***@", url)


ALLOWED_HOSTS = ("github.com",)


def _identity_path(url: str, local_allowed: bool) -> tuple[str | None, str]:
    """`(host, owner/name)` of a remote URL; refuses embedded credentials and (untested) local paths.

    A local remote has no host (`None`); it is accepted only when the test harness opts in.
    """
    if "://" in url:
        parts = urlsplit(url)
        if parts.scheme == "file":
            if not local_allowed:
                raise DestinationMisconfigured("a local evidence remote is refused outside the test harness")
            host, path = None, parts.path
        else:
            if parts.password is not None or (parts.username and parts.scheme in ("http", "https")):
                raise DestinationMisconfigured("the evidence remote URL embeds credentials; use the runtime's own authentication")
            host, path = (parts.hostname or "").lower(), parts.path
    elif (m := re.match(r"^[\w.-]+@([\w.-]+):(.+)$", url)):
        host, path = m.group(1).lower(), m.group(2)
    else:
        if not local_allowed:
            raise DestinationMisconfigured("a local evidence remote is refused outside the test harness")
        host, path = None, url
    return host, path.rstrip("/").removesuffix(".git").lstrip("/")


def prove_identity(url: str, repository: str, *, env: Mapping[str, str]) -> None:
    """The remote must be `repository` on an allowed host: an exact `owner/name` path, never a suffix match.

    Only a test-harness local bare repository (no host) may match by path suffix.
    """
    host, path = _identity_path(url, env.get(TEST_LOCAL_REMOTES_ENV) == "1")
    wanted, path = repository.lower(), path.lower()
    if host is None:
        proven = path == wanted or path.endswith("/" + wanted)
    else:
        proven = host in ALLOWED_HOSTS and path == wanted
    if not proven:
        raise DestinationMisconfigured(f"the evidence remote {redact(url)!r} is not the declared evidence repository {repository}")


def resolve_destination(
    manifest: Mapping[str, Any],
    *,
    evidence_remote: str | None,
    repo_root: Path,
    env: Mapping[str, str] | None = None,
    source_repository: str | None = None,
) -> Destination:
    """Validate the `evidence` block and prove the transport remote is the declared repository (§4.3 steps 1-4).

    `manifest` is any mapping with an `evidence` block (the expected-run manifest). `source_repository`
    defaults to its top-level `repository`; a temporary spec passes its own and must name the same source.
    """
    env = os.environ if env is None else env
    source = source_repository if source_repository is not None else manifest.get("repository")
    if isinstance(manifest.get("repository"), str) and isinstance(source, str) and manifest["repository"] != source:
        raise DestinationMisconfigured("the spec's source repository differs from the manifest's")
    block = manifest.get("evidence")
    errors = validate_evidence_block(block, source)
    if errors:
        raise DestinationMisconfigured(f"invalid evidence destination: {errors[0]}")
    assert isinstance(block, dict)
    remote = evidence_remote
    if remote is None:
        if block["phase"] == PHASE_PRIVATE:
            raise DestinationMisconfigured("the private phase needs an explicit evidence remote; the checkout's own remote is never used")
        remote = CHECKOUT_REMOTE
    url = _remote_url(repo_root, remote)
    prove_identity(url, block["repository"], env=env)
    return Destination(
        repository=block["repository"], phase=block["phase"], remote=remote,
        namespaces=tuple(block["namespaces"]), history_branch=block["history_branch"], repo_root=Path(repo_root),
    )


def write_diagnostics(files: Mapping[str, bytes], run_id: str, commit_file: str, diagnostics_dir: Path | None = None) -> Path:
    """Preserve the would-be sealed files locally (best effort; a Routine sandbox does not outlive its session)."""
    from runtime_platform.benchmark.scripts import benchmark_seal as seal

    target = diagnostics_dir or Path(tempfile.gettempdir()) / f"benchmark-unsealed-{run_id}"
    return seal.seal_to_directory(target, files, commit_file)


def unavailable_status(exc: StoreUnavailable, *, run_id: str | None, destination: Destination | str | None, diagnostics: Path | None) -> dict[str, Any]:
    """The JSON an exit-3 run prints: no URL, no record content."""
    repository = destination.repository if isinstance(destination, Destination) else destination
    return {
        "status": exc.status, "run_id": run_id, "destination": repository, "error_class": exc.error_class,
        "sealed": False, "diagnostics": str(diagnostics) if diagnostics else None,
    }


def add_remote_argument(parser: Any) -> None:
    """`--evidence-remote` (alias `--seal-remote`): the one remote argument every entrypoint shares."""
    parser.add_argument(
        "--evidence-remote", "--seal-remote", dest="evidence_remote", default=None,
        help="Git remote name or URL of the evidence store. It must prove to be the manifest's evidence.repository; "
        "omitted, only the pre_cutover phase uses the checkout's own remote, and only after the same proof.",
    )


def exit_for(exc: Exception, *, run_id: str | None = None, destination: Destination | str | None = None,
             files: Mapping[str, bytes] | None = None, commit_file: str | None = None) -> int:
    """Report a destination failure and return its exit code (2 misconfigured, 3 unavailable); never a fallback."""
    import json
    import sys

    if isinstance(exc, DestinationMisconfigured):
        print(f"error: {STATUS_MISCONFIGURED}: {exc}", file=sys.stderr)
        return EXIT_MISCONFIGURED
    assert isinstance(exc, StoreUnavailable)
    diagnostics = None
    if files and run_id and commit_file:
        try:
            diagnostics = write_diagnostics(files, run_id, commit_file)
        except OSError:
            diagnostics = None
    print(f"error: {exc.status}: {exc}", file=sys.stderr)
    print(json.dumps(unavailable_status(exc, run_id=run_id, destination=destination, diagnostics=diagnostics), indent=2))
    return EXIT_UNAVAILABLE
