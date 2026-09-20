#!/usr/bin/env python3
"""Production benchmark CLI entrypoint (Issue #250).

Wires the existing test-only benchmark reference modules
(``runtime_platform/benchmark/reference/``) together with the production reviewer
adapter (``runtime_platform/benchmark/scripts/benchmark_review_adapter.py``) to actually run the
corpus — or one selected case — against a real runtime reading the
packaged ``local-code-review`` Skill, instead of a deterministic test
stub. This script reimplements none of the runner, matcher, metrics, or
regression-report logic; it only calls them and prints their output.

Usage::

    python3 runtime_platform/benchmark/scripts/run_benchmark.py
    python3 runtime_platform/benchmark/scripts/run_benchmark.py --case-id correctness-off-by-one-pagination
    python3 runtime_platform/benchmark/scripts/run_benchmark.py --corpus-dir docs/benchmark/corpus --cli claude --timeout 600

Environment variables:

- ``BENCHMARK_REVIEW_CLI`` — the review CLI executable name/path (default
  ``claude``, the Claude Code CLI). Overridden by ``--cli`` when given.
- ``BENCHMARK_REVIEW_CLI_ARGS`` — extra, shell-quoted args appended to
  every invocation of that CLI.

Runtime availability (see ``runtime_platform/benchmark/scripts/benchmark_review_adapter.py``,
``check_runtime_available``): before touching the corpus, any workspace, or
the matcher/metrics, this script checks whether the configured review CLI
executable can actually be found. If it cannot, it prints a clear,
actionable message to stderr and exits non-zero immediately — it never
fabricates a clean result and never silently skips cases because the
runtime is unavailable.

Exit code reflects execution health only (``RunResult.exit_code`` —
0 == every case executed without an execution-level failure), never review
quality: a run in which reviewers found many defects, found none, or a
matcher would score poorly is still a successful run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.scripts.benchmark_review_adapter import (  # noqa: E402
    ProductionReviewerAdapter,
    RuntimeUnavailableError,
    check_runtime_available,
    resolve_cli_executable,
    resolve_cli_extra_args,
)
from runtime_platform.benchmark.reference import benchmark_citation as bc  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_dupes as bdup  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_fixture as bf  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_metrics as bm  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_runner as br  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_severity as bsev  # noqa: E402

DEFAULT_CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the benchmark corpus (or one selected case) against a "
            "production reviewer adapter that drives a real runtime reading "
            "the packaged local-code-review Skill."
        )
    )
    parser.add_argument(
        "--corpus-dir",
        default=str(DEFAULT_CORPUS_DIR),
        help=f"Corpus directory to run (default: {DEFAULT_CORPUS_DIR}).",
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help="Run exactly this case id instead of the whole corpus.",
    )
    parser.add_argument(
        "--cli",
        default=None,
        help="Override the review CLI executable (else BENCHMARK_REVIEW_CLI, else 'claude').",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300.0,
        help="Per-case timeout in seconds for the review CLI subprocess (default: 300).",
    )
    return parser


def _load_cases_for_metrics(corpus_dir: Path, case_id: str | None) -> list[bf.BenchmarkCase]:
    import yaml  # local import, matches benchmark_runner's own lazy import of its only dev dep

    cases: list[bf.BenchmarkCase] = []
    for path in sorted(corpus_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        cases.append(bf.parse_case(data))
    if case_id is not None:
        cases = [c for c in cases if c.id == case_id]
    return cases


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    corpus_dir = Path(args.corpus_dir)

    executable = args.cli or resolve_cli_executable()
    try:
        check_runtime_available(executable)
    except RuntimeUnavailableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    adapter = ProductionReviewerAdapter(
        executable=executable,
        extra_args=resolve_cli_extra_args(),
        timeout=args.timeout,
    )

    if args.case_id:
        run_result = br.run_selected(corpus_dir, args.case_id, adapter)
    else:
        run_result = br.run_corpus(corpus_dir, adapter)

    output: dict = {"run": run_result.as_dict()}
    try:
        cases = _load_cases_for_metrics(corpus_dir, args.case_id)
        if cases:
            # Thread each case's captured post-image (issue #342) through to
            # the matcher's anchor-proximity check, so it actually runs on
            # production runs instead of being dead code exercised only by
            # tests that pass `post_image` manually.
            post_images = {
                r.id: r.post_image for r in run_result.case_results if r.post_image is not None
            }
            output["metrics"] = bm.compute_run_metrics(cases, run_result, post_images=post_images).as_dict()
            # The scheduled entrypoint seals these with `metrics`; only here are `post_images` available.
            output["severity"] = bsev.compute_run_severity_accuracy(cases, run_result, post_images=post_images).as_dict()
            output["duplicate_noise"] = bdup.compute_run_duplicate_noise(cases, run_result, post_images=post_images).as_dict()
            # Citation-existence fidelity (issue #349): its own metric
            # category beside `metrics`, never mixed into match outcomes.
            output["citation_fidelity"] = bc.compute_run_citation_fidelity(cases, run_result).as_dict()
    except Exception as exc:  # noqa: BLE001 - metrics are a convenience, never hide the run result
        output["metrics_error"] = str(exc)

    print(json.dumps(output, indent=2))
    return run_result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
