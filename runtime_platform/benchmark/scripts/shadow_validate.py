#!/usr/bin/env python3
"""Shadow-validation burn-in report CLI (Issue #335).

Contract: runtime_platform/benchmark/shadow-validation.md. Reimplements no comparison
logic locally: every computation is
``runtime_platform/benchmark/reference/benchmark_shadow_validation.py``.

Usage::

    python3 runtime_platform/benchmark/scripts/shadow_validate.py \\
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

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from runtime_platform.benchmark.reference import benchmark_shadow_validation as sv  # noqa: E402


def _case_id_list(entry: dict[str, Any], key: str, path: Path, index: int) -> tuple[str, ...]:
    # Fail-closed like load_pr_classification in select_benchmark_cases.py:
    # tuple() on a bare string would silently split it into characters.
    if key not in entry:
        raise ValueError(f"{path}[{index}]: missing required key '{key}'")
    value = entry[key]
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValueError(f"{path}[{index}].{key}: expected a list of strings, got {value!r}")
    return tuple(value)


def load_samples(path: Path) -> list[sv.BurnInSample]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path}: expected a JSON array of burn-in samples")
    samples: list[sv.BurnInSample] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"{path}[{i}]: expected an object")
        if "sample_id" not in entry:
            raise ValueError(f"{path}[{i}]: missing required key 'sample_id'")
        samples.append(
            sv.BurnInSample(
                sample_id=entry["sample_id"],
                selected_case_ids=_case_id_list(entry, "selected_case_ids", path, i),
                regressed_case_ids=_case_id_list(entry, "regressed_case_ids", path, i),
            )
        )
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
        "runtime_platform/benchmark/shadow-validation.md §4's methodology — not a verdict "
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
