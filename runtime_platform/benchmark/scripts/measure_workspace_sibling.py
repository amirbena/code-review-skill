#!/usr/bin/env python3
"""Maintainer-run measurement of workspace sibling context resolution (Issue #664).

Runs the ``workspace-sibling-context`` sub-corpus with the workspace grant
handed to the reviewer (``on``) and withheld (``off``) over identical
materialized inputs, alternating arms, once per review adapter, and writes one
JSON record with the pre-registered gate outcome per adapter. Decision record
and gate: runtime_platform/benchmark/workspace-sibling-context-measurement.md.

Usage::

    python3 runtime_platform/benchmark/scripts/measure_workspace_sibling.py --out measurement.json
    python3 runtime_platform/benchmark/scripts/measure_workspace_sibling.py \\
        --github-reviewer my_package.adapters:make_github_reviewer --runs 5

The local adapter is the production adapter. The GitHub adapter is
caller-supplied as ``module:factory``; the factory takes no arguments and
returns a reviewer callable like ``ReviewerAdapter`` (accepting the optional
``workspace_root`` keyword) that exposes ``last_report`` and, optionally,
``last_usage`` (``{"input_tokens": int, "output_tokens": int}``). Without
``--github-reviewer`` the GitHub adapter is recorded ``not-run``.

Every run is isolated: only the skill under test is loaded (no user-level
plugin can shadow it), the CLI's event stream is read, and a run fails closed
unless the skill that ran can be identified. Each run's raw stdout/stderr, exit
code, error category, skill identity and capability-activation trace are written
under ``--evidence-dir`` whether the run succeeded or not, and the record points
at them. An existing ``--out`` or non-empty evidence directory is never
overwritten, so an earlier record stays intact; ``--retry-of`` links a new record
to the one it follows.

Exit code reflects execution health only: 0 when every run executed, 1 when
any run errored, 2 when the runtime is unavailable, ``--runs`` is too low, or
isolation could not be established (the run stops at the first such failure; its
evidence is kept). The gate outcome never changes it.
"""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from runtime_platform.benchmark.reference import benchmark_fixture as bf  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_runner as br  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_workspace_sibling as bws  # noqa: E402
from runtime_platform.benchmark.scripts import benchmark_run_evidence as bre  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_review_adapter import (  # noqa: E402
    ProductionReviewerAdapter,
    RuntimeUnavailableError,
    check_runtime_available,
    resolve_cli_executable,
)

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "workspace-sibling-context"
DEFAULT_RUNS = 3
DEFAULT_TIMEOUT_SECONDS = 600.0


HARNESS_INVALID_CATEGORIES = ("isolation-failed", "stream-parse-failure")


class HarnessInvalid(RuntimeError):
    """The run cannot be interpreted (isolation not established); stop and keep the evidence."""


class ArmAdapter:
    """Wraps a reviewer so an arm differs only in whether the workspace grant
    is forwarded. The runner materializes the same siblings for both arms."""

    def __init__(self, inner: Callable[..., Any], *, grant: bool) -> None:
        self.inner = inner
        self.grant = grant

    def __call__(self, workspace: Any, **kwargs: Any) -> Any:
        if not self.grant:
            kwargs.pop("workspace_root", None)
        return self.inner(workspace, **kwargs)

    @property
    def last_report(self) -> str | None:
        return getattr(self.inner, "last_report", None)

    @property
    def last_evidence(self) -> bre.RunEvidence | None:
        return getattr(self.inner, "last_evidence", None)

    @property
    def last_tokens(self) -> int | None:
        usage = getattr(self.inner, "last_usage", None)
        if not usage:
            return None
        return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))


def load_cases(corpus_dir: Path = CORPUS_DIR) -> list[bf.BenchmarkCase]:
    return [bf.parse_case(yaml.safe_load(p.read_text(encoding="utf-8"))) for p in sorted(corpus_dir.glob("*.yaml"))]


def measure_adapter(
    adapter: str,
    cases: Sequence[bf.BenchmarkCase],
    runs: int,
    make_reviewer: Callable[[], Callable[..., Any]],
    evidence_dir: Path | None = None,
) -> list[bws.RunObservation]:
    """Alternate off/on per run so slow drift lands on both arms. With an
    evidence directory, each run's raw evidence is written there first, success
    or failure; a reviewer that produces none (a caller-supplied adapter that
    does not support it) is recorded without."""
    observations: list[bws.RunObservation] = []
    for case in (c for c in cases if bws.applies_to(c.id, adapter)):
        for index in range(1, runs + 1):
            for arm in ("off", "on"):
                wrapped = ArmAdapter(make_reviewer(), grant=arm == "on")
                started = time.monotonic()
                result = br.run_case(case, wrapped)
                seconds = round(time.monotonic() - started, 3)
                evidence = wrapped.last_evidence
                evidence_file = None
                if evidence is not None and evidence_dir is not None:
                    evidence_file = bre.write_run_evidence(evidence_dir, f"{adapter}-{case.id}-{arm}-{index}", evidence)
                observations.append(
                    bws.observe_run(
                        case, result, wrapped.last_report, arm=arm, seconds=seconds, tokens=wrapped.last_tokens,
                        error_category=evidence.error_category if evidence else None,
                        evidence_file=evidence_file,
                        skill=evidence.skill if evidence else None,
                        activation=evidence.activation if evidence else None,
                    )
                )
                if evidence is not None and evidence.error_category in HARNESS_INVALID_CATEGORIES:
                    raise HarnessInvalid(
                        f"{adapter}/{case.id}/{arm}/{index}: {evidence.error_message} (evidence: {evidence_file})"
                    )
    return observations


def _load_factory(spec: str) -> Callable[[], Callable[..., Any]]:
    module_name, _, attr = spec.partition(":")
    if not module_name or not attr:
        raise ValueError("--github-reviewer must be module:factory")
    return getattr(importlib.import_module(module_name), attr)


def _skill_sha() -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return completed.stdout.strip() or None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure workspace sibling context resolution (issue #664).")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help=f"Runs per arm per case (default {DEFAULT_RUNS}).")
    parser.add_argument("--cli", default=None, help="Review CLI executable (default: $BENCHMARK_REVIEW_CLI or claude).")
    parser.add_argument("--github-reviewer", default=None, help="module:factory for the caller-supplied GitHub adapter.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Per-run timeout in seconds.")
    parser.add_argument("--model", default=None, help="Model label recorded in the metadata only.")
    parser.add_argument("--out", default=None, help="Write the JSON record here (default: stdout). Never overwritten.")
    parser.add_argument(
        "--evidence-dir", default=None,
        help="Directory for per-run raw evidence (default: <out>.evidence, or ./workspace-sibling-evidence-<UTC time>). Must be absent or empty.",
    )
    parser.add_argument("--case", action="append", help="Restrict to this case id (repeatable). Default: the whole sub-corpus.")
    parser.add_argument("--smoke", action="store_true", help="Allow a single run per arm for a harness check. Records smoke=true; never a measurement.")
    parser.add_argument("--allow-dirty", action="store_true", help="Run although the skill checkout has uncommitted changes. The record then cannot be tied to a revision; use only for a harness check.")
    parser.add_argument("--retry-of", default=None, help="Reference (path, sha256 or issue comment) of the record this run follows; stored in the metadata.")
    return parser


def tree_is_dirty(root: Path = REPO_ROOT) -> bool | None:
    """True when tracked files differ from HEAD, None when git cannot say."""
    completed = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True, check=False
    )
    return bool(completed.stdout.strip()) if completed.returncode == 0 else None


def _prepare_outputs(args: argparse.Namespace) -> tuple[Path | None, Path]:
    """Resolve the record and evidence paths and refuse to overwrite either."""
    out = Path(args.out) if args.out else None
    if out is not None and out.exists():
        raise FileExistsError(f"{out} exists; an earlier record is never overwritten")
    if args.evidence_dir:
        evidence = Path(args.evidence_dir)
    elif out is not None:
        evidence = out.with_name(out.name + ".evidence")
    else:
        evidence = Path.cwd() / f"workspace-sibling-evidence-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}"
    if evidence.exists() and any(evidence.iterdir()):
        raise FileExistsError(f"{evidence} is not empty; earlier evidence is never overwritten")
    return out, evidence


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.smoke and not args.case:
        print("--smoke needs at least one --case; it is not a measurement", file=sys.stderr)
        return 2
    if args.runs < bws.MIN_RUNS_PER_ARM and not args.smoke:
        print(f"--runs must be at least {bws.MIN_RUNS_PER_ARM}: verdicts need two runs per arm", file=sys.stderr)
        return 2
    if not (args.smoke or args.allow_dirty) and tree_is_dirty() is not False:
        print("the skill checkout has uncommitted changes (or git cannot tell): commit first so the record names a revision, or pass --allow-dirty", file=sys.stderr)
        return 2
    try:
        out, evidence_dir = _prepare_outputs(args)
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    executable = args.cli or resolve_cli_executable()
    try:
        check_runtime_available(executable)
    except RuntimeUnavailableError as exc:
        print(f"runtime unavailable: {exc}", file=sys.stderr)
        return 2

    cases = load_cases()
    unknown = sorted(set(args.case or ()) - {c.id for c in cases})
    if unknown:
        print(f"unknown --case: {unknown}", file=sys.stderr)
        return 2
    selected = [c for c in cases if not args.case or c.id in args.case]
    local_ids = [c.id for c in selected if bws.applies_to(c.id, bws.LOCAL)]
    github_ids = [c.id for c in selected if bws.applies_to(c.id, bws.GITHUB)]
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        runs: dict[str, list[bws.RunObservation] | None] = {
            bws.LOCAL: measure_adapter(
                bws.LOCAL, selected, args.runs,
                lambda: ProductionReviewerAdapter(executable=executable, timeout=args.timeout, verified_isolation=True),
                evidence_dir,
            ),
            bws.GITHUB: None,
        }
        if args.github_reviewer:
            runs[bws.GITHUB] = measure_adapter(
                bws.GITHUB, selected, args.runs, _load_factory(args.github_reviewer), evidence_dir
            )
    except HarnessInvalid as exc:
        print(f"harness invalid, stopping: {exc}\nevidence kept in {evidence_dir}", file=sys.stderr)
        return 2

    skills = [r.skill for rs in runs.values() for r in (rs or []) if r.skill]
    record = bws.measurement_record(
        runs,
        {bws.LOCAL: local_ids, bws.GITHUB: github_ids},
        runs_per_arm=args.runs,
        metadata={
            "skill_sha": _skill_sha(),
            "runtime": executable,
            "model": args.model,
            "github_reviewer": args.github_reviewer,
            "isolation": "verified: --setting-sources project,local, stream-json init checked, fail closed",
            "skill_identities": [json.loads(sk) for sk in sorted({json.dumps(sk, sort_keys=True) for sk in skills})],
            "skill_tree_dirty": tree_is_dirty(),
            "evidence_dir": str(evidence_dir),
            "retry_of": args.retry_of,
            "started_at": started_at,
            "smoke": bool(args.smoke),
            "cases": [c.id for c in selected],
        },
    )
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if out is not None:
        with open(out, "x", encoding="utf-8") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)
    json.dump(record["summary"], sys.stderr, indent=2)
    sys.stderr.write("\n")
    if args.smoke:
        sys.stderr.write("smoke run: not a C3 measurement\n")
    errored = any(not r.executed for rs in runs.values() for r in (rs or []))
    return 1 if errored else 0


if __name__ == "__main__":
    sys.exit(main())
