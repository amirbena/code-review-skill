#!/usr/bin/env python3
"""Deterministic Top-K benchmark selector CLI (Issue #334). Contract:
runtime_platform/benchmark/selection.md.

Turns an already-narrowed candidate pool (the committed inverted index,
#333) and a PR's already-resolved taxonomy classification (the output of
``runtime_platform/benchmark/scripts/classify_pr_diff.py``, produced separately — this
script takes no model-call dependency of its own) into a deterministic,
explainable, coverage-bounded Top-K selection. Reimplements no scoring
logic locally: every computation is
``runtime_platform/benchmark/reference/benchmark_selection.py``.

Ships informational-only (runtime_platform/benchmark/selection.md §6): this script
never fails the process on ``insufficient-coverage`` — that outcome is
reported, visibly and non-silently, in the emitted JSON and (optionally)
the step summary, never folded into a passing result and never treated as
a gate. Whether/when it becomes a required check is Issue #335's scope,
not this script's.

Usage::

    python3 runtime_platform/benchmark/scripts/select_benchmark_cases.py \\
        --pr-classification path/to/classification.json

    python3 runtime_platform/benchmark/scripts/select_benchmark_cases.py \\
        --pr-classification path/to/classification.json \\
        --k 8 --step-summary "$GITHUB_STEP_SUMMARY"

``--pr-classification`` points at a JSON file shaped like
``classify_pr_diff.classify_pr_diff``'s return value: a mapping with
exactly the four taxonomy dimension keys, each a non-empty list of
values.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from runtime_platform.benchmark.reference import benchmark_selection as sel  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_taxonomy as tax  # noqa: E402

DEFAULT_INDEX_PATH = _REPO_ROOT / "docs" / "benchmark" / "corpus-index.json"


def load_pr_classification(path: Path) -> dict[str, tuple[str, ...]]:
    """Fail-closed: reuses ``tax.validate_taxonomy`` so a malformed value
    (a bare string instead of a list, an unknown dimension/value, a
    missing dimension) is rejected outright rather than silently coerced
    (e.g. ``tuple("core")`` -> ``('c', 'o', 'r', 'e')``)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        return tax.validate_taxonomy(raw)
    except tax.TaxonomyError as exc:
        raise ValueError(f"{path}: {exc}") from exc


def render_step_summary(explainability: dict[str, Any]) -> str:
    outcome = explainability["outcome"]
    lines = [
        "## Benchmark selection (#334)",
        "",
        f"**Outcome:** `{outcome}`  ",
        f"**Selection Coverage:** {explainability['selection_coverage']:.2f}% "
        f"(threshold {explainability['coverage_threshold']:.0f}%)  ",
        f"**Candidate pool size:** {explainability['candidate_pool_size']}  ",
        f"**Top-K bound:** {explainability['top_k_bound']}",
        "",
    ]
    if explainability["selected_cases"]:
        lines.append("| Case | Relevance | Band | Marginal gain |")
        lines.append("| --- | --- | --- | --- |")
        for case in explainability["selected_cases"]:
            lines.append(
                f"| `{case['case_id']}` | {case['relevance_score']} | "
                f"{case['band']} | {case['marginal_coverage_gain']:.2f} |"
            )
        lines.append("")
    else:
        lines.append("_No cases selected._")
        lines.append("")
    if outcome == sel.OUTCOME_INSUFFICIENT_COVERAGE:
        lines.append("**Uncovered `(dimension, value)` pairs:**")
        for dim, value in explainability["uncovered_pairs"]:
            lines.append(f"- `{dim}`: `{value}`")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr-classification", type=Path, required=True)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--k", type=int, default=sel.K_DEFAULT)
    parser.add_argument(
        "--output", type=Path, default=None, help="write the explainability JSON here (default: stdout)"
    )
    parser.add_argument(
        "--step-summary",
        type=Path,
        default=None,
        help="append a Markdown summary here (e.g. $GITHUB_STEP_SUMMARY)",
    )
    args = parser.parse_args(argv)

    pr_classification = load_pr_classification(args.pr_classification)
    index = json.loads(args.index_path.read_text(encoding="utf-8"))

    result = sel.select_cases(index, pr_classification, k=args.k)
    explainability = sel.build_explainability(result)
    rendered = json.dumps(explainability, indent=2, sort_keys=False) + "\n"

    if args.output is not None:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)

    if args.step_summary is not None:
        with args.step_summary.open("a", encoding="utf-8") as fh:
            fh.write(render_step_summary(explainability))

    # Informational only (runtime_platform/benchmark/selection.md §6): insufficient
    # coverage is reported, never made a failing exit status here.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
