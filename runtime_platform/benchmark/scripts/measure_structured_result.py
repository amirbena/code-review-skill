#!/usr/bin/env python3
"""Maintainer-run measurement of structured-result runtime properties (Issue #529).

Runs each case of the fixed subset with ``structured_review_result`` on and
off, alternating arms, and writes one JSON record. Decision record and
reading guide: runtime_platform/benchmark/structured-result-runtime-properties.md.

Usage::

    python3 runtime_platform/benchmark/scripts/measure_structured_result.py --out measurement.json
    python3 runtime_platform/benchmark/scripts/measure_structured_result.py --runs 5 --case-id dd-blocking-p0-sql-injection

Exit code reflects execution health only: 0 when every run executed,
1 when any run errored, 2 when the runtime is unavailable. Flags in the
record never change it.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from runtime_platform.benchmark.reference import benchmark_fixture as bf  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_runner as br  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_structured_result as bsr  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_review_adapter import (  # noqa: E402
    HASHING_ALLOWED_TOOLS,
    ProductionReviewerAdapter,
    RuntimeUnavailableError,
    check_runtime_available,
    resolve_cli_executable,
)

CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus"
DEFAULT_RUNS = 3
DEFAULT_TIMEOUT_SECONDS = 600.0

# The fixed subset (structured-result-runtime-properties.md, "Fixture subset").
FIXTURE_SUBSET = (
    "decision-derivation/dd-blocking-p0-sql-injection.yaml",
    "decision-derivation/dd-blocking-p1-inverted-error-rate.yaml",
    "quality-duplicated-branch-logic.yaml",
    "no-op-comment-and-rename.yaml",
)

AdapterFactory = Callable[[bool], ProductionReviewerAdapter]


def load_subset(corpus_dir: Path = CORPUS_DIR, case_ids: Sequence[str] = ()) -> list[bf.BenchmarkCase]:
    cases = [bf.parse_case(yaml.safe_load((corpus_dir / rel).read_text(encoding="utf-8"))) for rel in FIXTURE_SUBSET]
    if not case_ids:
        return cases
    unknown = set(case_ids) - {c.id for c in cases}
    if unknown:
        raise ValueError(f"not in the measurement subset: {sorted(unknown)}")
    return [c for c in cases if c.id in case_ids]


def measure_case(case: bf.BenchmarkCase, runs: int, make_adapter: AdapterFactory) -> dict:
    """Alternate off/on so slow drift in the runtime lands on both arms."""
    observations = []
    for _ in range(runs):
        for structured in (False, True):
            adapter = make_adapter(structured)
            result = br.run_case(case, adapter)
            observations.append(bsr.observe_run(case, result, adapter.last_report, structured=structured))
    return bsr.case_record(case.id, observations)


def _skill_sha() -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    return completed.stdout.strip() or None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure structured-result runtime properties (issue #529).")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help=f"Runs per arm per case (default {DEFAULT_RUNS}).")
    parser.add_argument("--case-id", action="append", default=[], help="Limit to these subset cases (repeatable).")
    parser.add_argument("--cli", default=None, help="Review CLI executable (default: $BENCHMARK_REVIEW_CLI or claude).")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS, help="Per-run timeout in seconds.")
    parser.add_argument("--model", default=None, help="Model label recorded in the metadata only.")
    parser.add_argument("--out", default=None, help="Write the JSON record here (default: stdout).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.runs < bsr.MIN_RUNS_PER_ARM:
        print(f"--runs must be at least {bsr.MIN_RUNS_PER_ARM}: verdicts need two runs per arm", file=sys.stderr)
        return 2
    executable = args.cli or resolve_cli_executable()
    try:
        check_runtime_available(executable)
    except RuntimeUnavailableError as exc:
        print(f"runtime unavailable: {exc}", file=sys.stderr)
        return 2

    def make_adapter(structured: bool) -> ProductionReviewerAdapter:
        return ProductionReviewerAdapter(
            executable=executable,
            timeout=args.timeout,
            structured_review_result=structured,
            allowed_tools=HASHING_ALLOWED_TOOLS,
        )

    cases = [measure_case(case, args.runs, make_adapter) for case in load_subset(case_ids=args.case_id)]
    record = bsr.measurement_record(
        cases,
        runs_per_arm=args.runs,
        metadata={
            "skill_sha": _skill_sha(),
            "runtime": executable,
            "model": args.model,
            "allowed_tools": HASHING_ALLOWED_TOOLS,
        },
    )
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    json.dump(record["summary"], sys.stderr, indent=2)
    sys.stderr.write("\n")
    errored = any(c["errored_runs"]["on"] or c["errored_runs"]["off"] for c in cases)
    return 1 if errored else 0


if __name__ == "__main__":
    sys.exit(main())
