#!/usr/bin/env python3
"""Shadow-validation burn-in report CLI (Issue #335). Contract:
docs/benchmark/shadow-validation.md.

Turns a pre-joined burn-in window — one JSON file listing, per PR sample,
the #334 Top-K selection's case ids and the #339-classified nightly
regression case ids that PR's burn-in window overlapped — into the one
machine-readable report object the contract describes. Reimplements no
comparison logic locally: every computation is
``tests/reference/benchmark/benchmark_shadow_validation.py``.

This script never runs a selection, never classifies drift, and never
opens or mutates anything on GitHub — it is a pure, offline aggregation
over already-computed evidence, consistent with the contract's Non-goals.
It also never fails the process: like ``select_benchmark_cases.py``, this
is informational tooling with no exit-status gate of its own (docs/
benchmark/shadow-validation.md §6 — no promotion mechanism exists here).

Usage::

    python3 scripts/benchmark/shadow_validate.py \\
        --samples path/to/burn-in-window.json \\
        --window-description "2026-08-01..2026-09-01, 14 nightly comparisons"

Input shape (``--samples``)::

    [
      {"sample_id": "...", "selected_case_ids": ["..."], "regressed_case_ids": ["..."]},
      ...
    ]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.reference.benchmark import benchmark_shadow_validation as sv  # noqa: E402


def load_samples(path: Path) -> list[sv.BurnInSample]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a JSON array of burn-in samples")
    samples: list[sv.BurnInSample] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"{path}[{i}]: expected an object")
        try:
            samples.append(
                sv.BurnInSample(
                    sample_id=entry["sample_id"],
                    selected_case_ids=tuple(entry["selected_case_ids"]),
                    regressed_case_ids=tuple(entry["regressed_case_ids"]),
                )
            )
        except KeyError as exc:
            raise ValueError(f"{path}[{i}]: missing required key {exc}") from exc
    return samples


def render_step_summary(report: dict[str, Any]) -> str:
    lines = [
        "## Shadow-validation burn-in report (#335)",
        "",
        f"**Window:** {report['window_description']}  ",
        f"**Samples:** {report['sample_count']}  ",
    ]
    miss_rate = report["miss_rate"]
    if miss_rate is None:
        lines.append("**Miss rate:** no regressions observed in this window (vacuous)  ")
    else:
        lines.append(
            f"**Miss rate:** {report['total_missed']}/{report['total_regressions']} "
            f"({miss_rate['float']:.2%})  "
        )
    redundancy_rate = report["redundancy_rate"]
    if redundancy_rate is None:
        lines.append("**Redundancy rate:** no cases were ever selected in this window (vacuous)  ")
    else:
        lines.append(
            f"**Redundancy rate:** {len(report['cases_never_caught_a_regression'])}/"
            f"{len(report['distinct_selected_case_ids'])} ({redundancy_rate['float']:.2%})  "
        )
    lines.append("")
    lines.append(
        "This report states the observed figures only. Whether they clear an "
        "acceptable bar is a maintainer decision applying "
        "docs/benchmark/shadow-validation.md §4's methodology — not a verdict "
        "this tooling renders."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=Path, required=True)
    parser.add_argument(
        "--window-description",
        required=True,
        help="human-readable description of the burn-in window this report covers",
    )
    parser.add_argument(
        "--output", type=Path, default=None, help="write the report JSON here (default: stdout)"
    )
    parser.add_argument(
        "--step-summary",
        type=Path,
        default=None,
        help="append a Markdown summary here (e.g. $GITHUB_STEP_SUMMARY)",
    )
    args = parser.parse_args(argv)

    samples = load_samples(args.samples)
    aggregate = sv.aggregate_burn_in(samples)
    report = sv.build_burn_in_report(aggregate, window_description=args.window_description)
    rendered = json.dumps(report, indent=2, sort_keys=False) + "\n"

    if args.output is not None:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        sys.stdout.write(rendered)

    if args.step_summary is not None:
        with args.step_summary.open("a", encoding="utf-8") as fh:
            fh.write(render_step_summary(report))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
