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

Exit code reflects execution health only: 0 when every run executed, 1 when
any run errored, 2 when the runtime is unavailable or ``--runs`` is too low.
The gate outcome never changes it.
"""

from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from runtime_platform.benchmark.reference import benchmark_fixture as bf  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_runner as br  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_workspace_sibling as bws  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_review_adapter import (  # noqa: E402
    ProductionReviewerAdapter,
    RuntimeUnavailableError,
    check_runtime_available,
    resolve_cli_executable,
)

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "workspace-sibling-context"
DEFAULT_RUNS = 3
DEFAULT_TIMEOUT_SECONDS = 600.0


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
    def last_tokens(self) -> int | None:
        usage = getattr(self.inner, "last_usage", None)
        if not usage:
            return None
        return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))


def load_cases(corpus_dir: Path = CORPUS_DIR) -> list[bf.BenchmarkCase]:
    return [bf.parse_case(yaml.safe_load(p.read_text(encoding="utf-8"))) for p in sorted(corpus_dir.glob("*.yaml"))]


def measure_adapter(
    adapter: str, cases: Sequence[bf.BenchmarkCase], runs: int, make_reviewer: Callable[[], Callable[..., Any]]
) -> list[bws.RunObservation]:
    """Alternate off/on per run so slow drift lands on both arms."""
    observations: list[bws.RunObservation] = []
    for case in (c for c in cases if bws.applies_to(c.id, adapter)):
        for _ in range(runs):
            for arm in ("off", "on"):
                wrapped = ArmAdapter(make_reviewer(), grant=arm == "on")
                started = time.monotonic()
                result = br.run_case(case, wrapped)
                observations.append(
                    bws.observe_run(
                        case, result, wrapped.last_report, arm=arm,
                        seconds=round(time.monotonic() - started, 3), tokens=wrapped.last_tokens,
                    )
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
    parser.add_argument("--out", default=None, help="Write the JSON record here (default: stdout).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.runs < bws.MIN_RUNS_PER_ARM:
        print(f"--runs must be at least {bws.MIN_RUNS_PER_ARM}: verdicts need two runs per arm", file=sys.stderr)
        return 2
    executable = args.cli or resolve_cli_executable()
    try:
        check_runtime_available(executable)
    except RuntimeUnavailableError as exc:
        print(f"runtime unavailable: {exc}", file=sys.stderr)
        return 2

    cases = load_cases()
    local_ids = [c.id for c in cases if bws.applies_to(c.id, bws.LOCAL)]
    github_ids = [c.id for c in cases if bws.applies_to(c.id, bws.GITHUB)]
    runs: dict[str, list[bws.RunObservation] | None] = {
        bws.LOCAL: measure_adapter(
            bws.LOCAL, cases, args.runs, lambda: ProductionReviewerAdapter(executable=executable, timeout=args.timeout)
        ),
        bws.GITHUB: None,
    }
    if args.github_reviewer:
        runs[bws.GITHUB] = measure_adapter(bws.GITHUB, cases, args.runs, _load_factory(args.github_reviewer))

    record = bws.measurement_record(
        runs,
        {bws.LOCAL: local_ids, bws.GITHUB: github_ids},
        runs_per_arm=args.runs,
        metadata={"skill_sha": _skill_sha(), "runtime": executable, "model": args.model, "github_reviewer": args.github_reviewer},
    )
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    json.dump(record["summary"], sys.stderr, indent=2)
    sys.stderr.write("\n")
    errored = any(not r.executed for rs in runs.values() for r in (rs or []))
    return 1 if errored else 0


if __name__ == "__main__":
    sys.exit(main())
