#!/usr/bin/env python3
"""Test-only reference for the benchmark runner (Issue #52).

Test-only: not runtime logic, not packaged — the packaged Skills are
Markdown/YAML only. This module mirrors ``docs/benchmark/runner-contract.md``:
per-case isolation into a disposable workspace, the repository-safety
invariants for every protected source checkout, cleanup on both the success
and failure paths, the machine-readable per-case result shape, single-case
vs. whole-corpus runs, and the "exit status = execution health, not review
quality" rule.

It is a *runner*, not a matcher and not a scorer: it records what a
reviewer adapter produced, verbatim, and never compares it to a fixture's
``expected`` block. Issue #41 owns the match relation and metrics, Issue
#53 the regression report, Issue #50 the fixture format, Issue #51 the
corpus.

The contract is the *behaviour and guarantees*; this module is one
executable projection of them so a test can prove a run executes the
corpus, emits stable per-case results, and leaves a deliberately dirty
source repository byte-for-byte unchanged after both a passing and a
failing case.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from tests.reference import benchmark_fixture as bf

# --------------------------------------------------------------------------
# Git plumbing — hermetic (no system/global config, fixed identity), used
# only for workspace materialization and read-only source-repo snapshots.
# --------------------------------------------------------------------------

_GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "Benchmark Runner",
    "GIT_AUTHOR_EMAIL": "runner@example.invalid",
    "GIT_COMMITTER_NAME": "Benchmark Runner",
    "GIT_COMMITTER_EMAIL": "runner@example.invalid",
    "GIT_TERMINAL_PROMPT": "0",
}


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env={**os.environ, **_GIT_ENV},
        check=check,
    )


# --------------------------------------------------------------------------
# Result shapes (docs/benchmark/runner-contract.md §6).
# --------------------------------------------------------------------------


class RunnerSafetyError(RuntimeError):
    """A protected source checkout was mutated, or cleanup failed.

    Raised only for the run-level failures in
    ``docs/benchmark/runner-contract.md`` §4–§5; a per-case problem is a
    ``CaseResult`` with ``status == "error"`` instead.
    """


@dataclass(frozen=True)
class ProducedFinding:
    """One reviewer result, recorded verbatim. The runner never inspects
    ``severity`` beyond carrying it — classification/matching is #41."""

    severity: str
    location: Any
    claim: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"severity": self.severity, "location": self.location}
        if self.claim is not None:
            out["claim"] = self.claim
        if self.extra:
            out["extra"] = dict(self.extra)
        return out


# A reviewer adapter: given the isolated workspace path, return produced
# findings. The runner owns everything else; the adapter owns how a review
# is performed (a runtime reading a Skill in production, a stub in tests).
ReviewerAdapter = Callable[[Path], Sequence[ProducedFinding]]

# For repo_ref inputs: resolve the fixture's repo_ref mapping to a local
# path the runner can clone from a disposable copy. Keeps the isolation
# contract testable without real network clones; production may plug in a
# real clone here instead.
RepoRefResolver = Callable[[Mapping[str, Any]], Path]

_EXECUTED = "executed"
_ERROR = "error"


@dataclass(frozen=True)
class CaseResult:
    id: str
    input_kind: str
    status: str  # "executed" | "error"
    produced_findings: tuple[ProducedFinding, ...] = ()
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "input_kind": self.input_kind,
            "status": self.status,
        }
        if self.status == _EXECUTED:
            out["produced_findings"] = [f.as_dict() for f in self.produced_findings]
        else:
            out["error"] = self.error
        return out


@dataclass(frozen=True)
class RunResult:
    case_results: tuple[CaseResult, ...]
    ok: bool
    error: str | None = None  # run-level failure reason, when ok is False

    @property
    def exit_code(self) -> int:
        """Execution health only — never whether reviewers found defects."""
        return 0 if self.ok else 1

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ok": self.ok,
            "cases": [r.as_dict() for r in self.case_results],
        }
        if self.error is not None:
            out["error"] = self.error
        return out


# --------------------------------------------------------------------------
# Source-repository integrity snapshot (read-only).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RepoState:
    """Observable state of a protected source checkout. Compared by value
    before/after a run; never requires the repo to be clean."""

    head: str
    porcelain: str
    branches: tuple[str, ...]
    stash: tuple[str, ...]


def capture_repo_state(repo: Path) -> RepoState:
    return RepoState(
        head=_git(repo, "rev-parse", "HEAD").stdout.strip(),
        porcelain=_git(repo, "status", "--porcelain=v1", "--untracked-files=all").stdout,
        branches=tuple(
            sorted(
                line
                for line in _git(
                    repo, "for-each-ref", "--format=%(refname)", "refs/heads"
                ).stdout.splitlines()
                if line
            )
        ),
        stash=tuple(_git(repo, "stash", "list").stdout.splitlines()),
    )


# --------------------------------------------------------------------------
# Per-case execution.
# --------------------------------------------------------------------------


class _PatchDidNotApply(Exception):
    pass


class _WorkspaceSetupFailed(Exception):
    pass


def _materialize_patch(case: bf.BenchmarkCase, workspace: Path) -> None:
    """Build the pre-image tree in ``workspace`` and apply ``input.patch``
    there — and only there (contract §3)."""
    _git(workspace, "init", "-q", "-b", "main", ".")
    _git(workspace, "config", "commit.gpgsign", "false")
    base = case.input.get("base", {}) or {}
    for rel, content in base.items():
        dest = workspace / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
    _git(workspace, "add", "-A")
    _git(workspace, "commit", "-q", "--allow-empty", "-m", "pre-image")

    patch_file = workspace / ".benchmark-input.patch"
    patch_file.write_text(case.input["patch"], encoding="utf-8")
    applied = _git(workspace, "apply", "--whitespace=nowarn", str(patch_file), check=False)
    patch_file.unlink()
    if applied.returncode != 0:
        raise _PatchDidNotApply(applied.stderr.strip() or "git apply failed")


def _materialize_repo_ref(
    case: bf.BenchmarkCase, workspace: Path, resolver: RepoRefResolver | None
) -> None:
    """Obtain the referenced state as a disposable clone in ``workspace``.
    Never reuses a protected source checkout (contract §3)."""
    if resolver is None:
        raise _WorkspaceSetupFailed("no repo_ref resolver supplied")
    ref = case.input["repo_ref"]
    origin = Path(resolver(ref))
    if not origin.exists():
        raise _WorkspaceSetupFailed(f"repo_ref origin does not exist: {origin}")
    cloned = _git(workspace.parent, "clone", "-q", str(origin), str(workspace), check=False)
    if cloned.returncode != 0:
        raise _WorkspaceSetupFailed(cloned.stderr.strip() or "git clone failed")
    target = ref.get("commit") or ref.get("base")
    if target:
        checked = _git(workspace, "checkout", "-q", str(target), check=False)
        if checked.returncode != 0:
            raise _WorkspaceSetupFailed(f"cannot checkout {target!r}")


def run_case(
    case: bf.BenchmarkCase,
    reviewer: ReviewerAdapter,
    *,
    workspace_parent: Path | None = None,
    repo_ref_resolver: RepoRefResolver | None = None,
    _cleanup: Callable[[Path], None] = lambda p: shutil.rmtree(p, ignore_errors=False),
) -> CaseResult:
    """Execute one case in an isolated, disposable workspace and return its
    machine-readable result. Cleanup runs on both the success and failure
    path; a failed cleanup raises :class:`RunnerSafetyError` after the
    workspace result is determined (contract §5)."""
    kind = case.input_kind
    workspace = Path(
        tempfile.mkdtemp(prefix=f"benchmark-{case.id}-", dir=str(workspace_parent) if workspace_parent else None)
    )
    result: CaseResult
    try:
        try:
            if kind == "patch":
                _materialize_patch(case, workspace)
            else:
                _materialize_repo_ref(case, workspace, repo_ref_resolver)
        except _PatchDidNotApply:
            return CaseResult(case.id, kind, _ERROR, error="patch-did-not-apply")
        except _WorkspaceSetupFailed:
            return CaseResult(case.id, kind, _ERROR, error="workspace-setup-failed")
        except Exception:  # noqa: BLE001 - any setup failure is a per-case error
            return CaseResult(case.id, kind, _ERROR, error="workspace-setup-failed")

        try:
            produced = tuple(reviewer(workspace))
        except Exception:  # noqa: BLE001 - adapter failure is a per-case error, not a crash
            return CaseResult(case.id, kind, _ERROR, error="reviewer-adapter-raised")

        result = CaseResult(case.id, kind, _EXECUTED, produced_findings=produced)
        return result
    finally:
        try:
            _cleanup(workspace)
        except Exception as exc:  # noqa: BLE001
            raise RunnerSafetyError(f"cleanup failed for {case.id}: {exc}") from exc


# --------------------------------------------------------------------------
# Run modes (contract §2) with the source-repo safety wrapper (§4).
# --------------------------------------------------------------------------


def _load_corpus(corpus_dir: Path) -> list[bf.BenchmarkCase]:
    """Parse every fixture. A parse failure fails the whole run before any
    case executes (fail-closed, contract §2)."""
    import yaml  # local import: only the runner's own dependency, already a dev dep

    cases: list[bf.BenchmarkCase] = []
    for path in sorted(corpus_dir.glob("*.yaml")):
        cases.append(bf.parse_case(yaml.safe_load(path.read_text(encoding="utf-8"))))
    return cases


def _execute(
    cases: Iterable[bf.BenchmarkCase],
    reviewer: ReviewerAdapter,
    *,
    source_repo: Path | None,
    workspace_parent: Path | None,
    repo_ref_resolver: RepoRefResolver | None,
    cleanup: Callable[[Path], None] | None,
) -> RunResult:
    before = capture_repo_state(source_repo) if source_repo else None

    case_results: list[CaseResult] = []
    run_error: str | None = None
    kwargs: dict[str, Any] = {
        "workspace_parent": workspace_parent,
        "repo_ref_resolver": repo_ref_resolver,
    }
    if cleanup is not None:
        kwargs["_cleanup"] = cleanup
    try:
        for case in cases:
            case_results.append(run_case(case, reviewer, **kwargs))
    except RunnerSafetyError:
        # A failed cleanup is a run-level execution failure
        # (docs/benchmark/runner-contract.md §5).
        run_error = "cleanup-failed"

    if run_error is None and before is not None:
        after = capture_repo_state(source_repo)  # type: ignore[arg-type]
        if after != before:
            run_error = "source-checkout-mutated"

    return RunResult(tuple(case_results), ok=run_error is None, error=run_error)


def run_corpus(
    corpus_dir: Path,
    reviewer: ReviewerAdapter,
    *,
    source_repo: Path | None = None,
    workspace_parent: Path | None = None,
    repo_ref_resolver: RepoRefResolver | None = None,
    cleanup: Callable[[Path], None] | None = None,
) -> RunResult:
    """Execute the whole corpus (contract §2). Every ``*.yaml`` is parsed
    up front; a malformed corpus fails the run before any case executes."""
    try:
        cases = _load_corpus(corpus_dir)
    except bf.FixtureFormatError:
        return RunResult((), ok=False, error="corpus-parse-failed")
    return _execute(
        cases,
        reviewer,
        source_repo=source_repo,
        workspace_parent=workspace_parent,
        repo_ref_resolver=repo_ref_resolver,
        cleanup=cleanup,
    )


def run_selected(
    corpus_dir: Path,
    case_id: str,
    reviewer: ReviewerAdapter,
    *,
    source_repo: Path | None = None,
    workspace_parent: Path | None = None,
    repo_ref_resolver: RepoRefResolver | None = None,
    cleanup: Callable[[Path], None] | None = None,
) -> RunResult:
    """Execute exactly the case named by ``case_id`` (contract §2). An
    unknown id is a run-level failure, never a silent no-op."""
    try:
        cases = _load_corpus(corpus_dir)
    except bf.FixtureFormatError:
        return RunResult((), ok=False, error="corpus-parse-failed")
    selected = [c for c in cases if c.id == case_id]
    if not selected:
        return RunResult((), ok=False, error="unknown-case-id")
    return _execute(
        selected,
        reviewer,
        source_repo=source_repo,
        workspace_parent=workspace_parent,
        repo_ref_resolver=repo_ref_resolver,
        cleanup=cleanup,
    )


def run_cases(
    cases: Sequence[bf.BenchmarkCase],
    reviewer: ReviewerAdapter,
    *,
    source_repo: Path | None = None,
    workspace_parent: Path | None = None,
    repo_ref_resolver: RepoRefResolver | None = None,
    cleanup: Callable[[Path], None] | None = None,
) -> RunResult:
    """Execute an explicit list of already-parsed cases — the seam tests
    use to run synthetic ``repo_ref`` / failing cases that are not in the
    on-disk corpus. Same guarantees as :func:`run_corpus`."""
    return _execute(
        cases,
        reviewer,
        source_repo=source_repo,
        workspace_parent=workspace_parent,
        repo_ref_resolver=repo_ref_resolver,
        cleanup=cleanup,
    )
