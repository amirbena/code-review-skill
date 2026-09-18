#!/usr/bin/env python3
"""Behavioral proof for `scale` progressive loading (issue #447).

Issue #447 made ``scale`` load conditionally on its declared activation
predicate and proved the fail-closed contract at the text/manifest level
(``tests/policy/review/test_scale_447.py``), mirroring #410's proof for
``specialist-depth``. Issue #408 recorded the pre-extraction baseline:
today's packaged instruction/resource surface, attributed by capability.
Neither proves the *behavior* stayed stable once ``scale``'s loading
actually became conditional. This module is that proof, reusing every
existing corpus and evaluator rather than introducing a new one:

- **Static surface reduction** (mirrors #411 required case 4): reuses
  ``capability_loading_baseline.py``'s own committed ``static_surface``
  measurement unchanged; the "reduction" is ``scale``'s own attributed
  word count no longer being part of the surface an "unnecessary" review
  needs to apply.
- **Behavioral stability on #408's regression set** (mirrors #411
  required cases 1/2, matched against the baseline): re-runs the same 4
  top-level corpus cases #408's quality-metrics baseline already covers,
  through the same ``ProductionReviewerAdapter`` +
  ``benchmark_metrics.compute_run_metrics`` #408 used, and asserts the
  same 0-false-negative/0-false-positive outcome.
- **Activation correctness and fail-closed loading** (mirrors #411
  required cases 1-3): reuses
  ``repository-intelligence``'s control case ("not needed" — a resolved,
  compatible caller produces no finding) and its call-site positive case
  ("must activate" — an unresolved caller-side defect), plus this issue's
  own one net-new fixture (``docs/benchmark/corpus/
  scale-progressive-loading-proof/``) pinning an ambiguous
  trigger-evaluation that must still load (fail-closed) rather than skip.

Defines no new evaluator or matcher: every metric below is computed by
calling ``runtime_platform/benchmark/reference/benchmark_metrics.py`` verbatim,
exactly as ``capability_loading_baseline.py`` already does.

Usage::

    python3 scripts/capability_architecture/scale_progressive_loading_proof.py static
    python3 scripts/capability_architecture/scale_progressive_loading_proof.py behavioral
    python3 scripts/capability_architecture/scale_progressive_loading_proof.py all --out PATH
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.capability_architecture.capability_loading_baseline import (  # noqa: E402
    measure_static_surface,
)

SCALE = "scale"

# The 4 top-level corpus cases #408's quality-metrics baseline already
# covers (docs/benchmark/corpus/*.yaml, the known non-recursive-glob
# reach) -- re-run here as the regression set required cases 1/2 must
# match.
ROOT_CORPUS_DIR = REPO_ROOT / "docs" / "benchmark" / "corpus"

# The reused repository-intelligence cases (#129): the control case
# ("resolved, compatible caller" -- no escalation needed) and the
# call-site positive case ("must activate" -- an unresolved caller-side
# defect).
REPOSITORY_INTELLIGENCE_CORPUS_DIR = ROOT_CORPUS_DIR / "repository-intelligence"
CASE_NOT_NEEDED = "repo-intel-python-control-compatible-caller-no-finding"
CASE_MUST_ACTIVATE = "repo-intel-python-call-site-caller-null-deref"

# This issue's one net-new fixture: ambiguous trigger evaluation, must
# load (fail-closed).
PROOF_CORPUS_DIR = ROOT_CORPUS_DIR / "scale-progressive-loading-proof"
CASE_AMBIGUOUS = (
    "scale-progressive-loading-proof-ambiguous-public-export-forces-"
    "fail-closed-expansion"
)


def measure_static_surface_reduction() -> dict[str, Any]:
    """Reuses #408's own static-surface measurement unchanged (no new
    word count derived here) and isolates the number that moves out of
    the unconditional path once ``scale`` is not needed: its own
    attributed word count, per adapter."""
    surface = measure_static_surface()
    result: dict[str, Any] = {}
    for adapter, measured in surface.items():
        total = measured["total_words"]
        removed = measured["by_capability_words"].get(SCALE, 0)
        result[adapter] = {
            "total_words_with_scale": total,
            "scale_words": removed,
            "total_words_when_not_needed": total - removed,
            "reduction_pct": round(100 * removed / total, 2) if total else 0.0,
        }
    return result


def measure_behavioral_proof(
    *, cli: str | None, timeout: float
) -> dict[str, Any]:
    """Runs the regression set plus the three required activation cases
    through the real reviewer runtime and reports each case's missed/
    incorrect-findings outcome (#55), computed via the existing reference
    metrics -- never a bespoke pass/fail check."""
    from runtime_platform.benchmark.scripts.benchmark_review_adapter import (
        ProductionReviewerAdapter,
        check_runtime_available,
        resolve_cli_executable,
        resolve_cli_extra_args,
    )
    from runtime_platform.benchmark.reference import benchmark_fixture as bf
    from runtime_platform.benchmark.reference import benchmark_metrics as bm
    from runtime_platform.benchmark.reference import benchmark_runner as br

    import yaml

    def _load(path: Path) -> bf.BenchmarkCase:
        return bf.parse_case(yaml.safe_load(path.read_text(encoding="utf-8")))

    def _by_id(corpus_dir: Path, case_id: str) -> bf.BenchmarkCase:
        for path in sorted(corpus_dir.glob("*.yaml")):
            case = _load(path)
            if case.id == case_id:
                return case
        raise ValueError(f"case {case_id!r} not found under {corpus_dir}")

    regression_cases = [_load(p) for p in sorted(ROOT_CORPUS_DIR.glob("*.yaml"))]
    activation_cases = [
        _by_id(REPOSITORY_INTELLIGENCE_CORPUS_DIR, CASE_NOT_NEEDED),
        _by_id(REPOSITORY_INTELLIGENCE_CORPUS_DIR, CASE_MUST_ACTIVATE),
        _by_id(PROOF_CORPUS_DIR, CASE_AMBIGUOUS),
    ]
    all_cases = regression_cases + activation_cases

    executable = cli or resolve_cli_executable()
    check_runtime_available(executable)
    adapter = ProductionReviewerAdapter(
        executable=executable,
        extra_args=resolve_cli_extra_args(),
        timeout=timeout,
    )

    run_result = br.run_cases(all_cases, adapter)
    post_images = {
        r.id: r.post_image for r in run_result.case_results if r.post_image is not None
    }

    regression_metrics = bm.compute_run_metrics(
        regression_cases, run_result, post_images=post_images
    )
    activation_metrics = bm.compute_run_metrics(
        activation_cases, run_result, post_images=post_images
    )

    return {
        "run": run_result.as_dict(),
        "regression_vs_408_baseline": regression_metrics.as_dict(),
        "activation_required_cases": activation_metrics.as_dict(),
        "case_roles": {
            CASE_NOT_NEEDED: "not-needed",
            CASE_MUST_ACTIVATE: "must-activate",
            CASE_AMBIGUOUS: "ambiguous-fail-closed",
        },
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("static", "behavioral", "all"))
    parser.add_argument("--cli", default=None, help="Override the review CLI executable.")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--out", default=None, help="Also write the result to this JSON file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    output: dict[str, Any] = {}
    if args.mode in ("static", "all"):
        output["static_surface_reduction"] = measure_static_surface_reduction()
    if args.mode in ("behavioral", "all"):
        try:
            output["behavioral_proof"] = measure_behavioral_proof(
                cli=args.cli, timeout=args.timeout
            )
        except Exception as exc:  # noqa: BLE001 - report, never mask the static half
            output["behavioral_proof_error"] = str(exc)
            print(f"error: {exc}", file=sys.stderr)

    text = json.dumps(output, indent=2, sort_keys=False)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")

    if "behavioral_proof_error" in output:
        return 1
    proof = output.get("behavioral_proof")
    if proof is not None:
        regression = proof["regression_vs_408_baseline"]["aggregate"]
        activation_by_id = {
            c["id"]: c for c in proof["activation_required_cases"]["cases"]
        }
        ambiguous = activation_by_id.get(CASE_AMBIGUOUS, {})
        if (
            regression["total_false_negatives"]
            or regression["total_false_positives"]
            or ambiguous.get("false_negatives")
            or ambiguous.get("false_positives")
        ):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
