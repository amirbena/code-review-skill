#!/usr/bin/env python3
"""Capability-loading baseline measurement (issue #408).

Pre-`specialist-depth`-extraction baseline the capability-architecture
model (§I.2/§I.5) needs before any capability's loading becomes
conditional: the static instruction/resource surface each Skill loads
today, attributed to a capability via its `capability.yaml` (#404) and
the generated `package-manifest.json` (#405/#406), plus the current
values of the existing quality-metric contracts (#55/#56/#57) as the
stability baseline `specialist-depth` extraction must not regress.

Defines no new evaluator: word counts are `wc -w` over the files
`package-manifest.json` already ships, matching
`capability-architecture-model.md`'s own stated methodology ("word
counts are `wc -w` over the named files"); quality metrics are computed
by calling `tests/reference/benchmark/benchmark_metrics.py`,
`benchmark_severity.py`, and `benchmark_dupes.py` verbatim over a real
`scripts/benchmark/run_benchmark.py`-equivalent run.

Usage::

    python3 scripts/capability_architecture/capability_loading_baseline.py static
    python3 scripts/capability_architecture/capability_loading_baseline.py quality
    python3 scripts/capability_architecture/capability_loading_baseline.py all --out PATH
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

from scripts.packaging.generate_package_manifest import (  # noqa: E402
    _load_capability_files,
    build_manifest,
)

# words -> tokens: the ratio capability-architecture-model.md's executive
# summary itself reports (~108,000 tokens / ~81,300 words) for this
# repository's Markdown instruction prose. Not re-derived here; carried
# forward as the one documented conversion factor.
WORDS_TO_TOKENS = 108_000 / 81_300

ADAPTER_SECTIONS = ("local", "github")


def _word_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").split())


def _attribute(
    sources: list[str], capability_files: dict[str, list[str]]
) -> dict[str, Any]:
    owner_by_source: dict[str, str] = {
        source: capability
        for capability, files in capability_files.items()
        for source in files
    }

    by_capability: dict[str, int] = {}
    core_words = 0
    for source in sources:
        words = _word_count(REPO_ROOT / source)
        capability = owner_by_source.get(source)
        if capability is None:
            core_words += words
        else:
            by_capability[capability] = by_capability.get(capability, 0) + words

    total_words = core_words + sum(by_capability.values())
    return {
        "total_words": total_words,
        "total_tokens_est": round(total_words * WORDS_TO_TOKENS),
        "core_unattributed_words": core_words,
        "by_capability_words": dict(sorted(by_capability.items())),
    }


def measure_static_surface() -> dict[str, Any]:
    """Full always-loaded surface per adapter, per §A.9/§I.2: every file
    the generated `package-manifest.json` ships that adapter today
    (nothing is conditional yet), attributed by capability.yaml
    ownership. The remainder is the not-yet-manifested always-resident
    core (`review-kernel`, `finding-contract`, `capability-posture`,
    `review-context-core`, `review-router`, …) that issue #404 explicitly
    left out of scope.
    """
    manifest = build_manifest()
    capability_files = _load_capability_files()

    shared_sources = [e["source"] for e in manifest["shared_files"]]
    result: dict[str, Any] = {}
    for adapter in ADAPTER_SECTIONS:
        skill_sources = [e["source"] for e in manifest["skills"][adapter]["files"]]
        sources = shared_sources + skill_sources
        result[adapter] = _attribute(sources, capability_files)
    return result


def measure_quality_metrics(
    *, corpus_dir: Path, cli: str | None, timeout: float
) -> dict[str, Any]:
    """Current values of the existing quality-metric contracts (#55, #56,
    #57), run against today's corpus (the known non-recursive-glob gap —
    ~4 of ~180 cases — is #408's stated non-goal to fix)."""
    from scripts.benchmark.benchmark_review_adapter import (
        ProductionReviewerAdapter,
        RuntimeUnavailableError,
        check_runtime_available,
        resolve_cli_executable,
        resolve_cli_extra_args,
    )
    from tests.reference.benchmark import benchmark_dupes as bd
    from tests.reference.benchmark import benchmark_fixture as bf
    from tests.reference.benchmark import benchmark_metrics as bm
    from tests.reference.benchmark import benchmark_runner as br
    from tests.reference.benchmark import benchmark_severity as bs

    import yaml

    executable = cli or resolve_cli_executable()
    check_runtime_available(executable)

    adapter = ProductionReviewerAdapter(
        executable=executable,
        extra_args=resolve_cli_extra_args(),
        timeout=timeout,
    )
    run_result = br.run_corpus(corpus_dir, adapter)

    cases = [
        bf.parse_case(yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in sorted(corpus_dir.glob("*.yaml"))
    ]
    post_images = {
        r.id: r.post_image for r in run_result.case_results if r.post_image is not None
    }

    return {
        "run": run_result.as_dict(),
        "missed_and_incorrect": bm.compute_run_metrics(
            cases, run_result, post_images=post_images
        ).as_dict(),
        "severity_accuracy": bs.compute_run_severity_accuracy(
            cases, run_result, post_images=post_images
        ).as_dict(),
        "duplicate_noise": bd.compute_run_duplicate_noise(
            cases, run_result, post_images=post_images
        ).as_dict(),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("static", "quality", "all"))
    parser.add_argument(
        "--corpus-dir",
        default=str(REPO_ROOT / "docs" / "benchmark" / "corpus"),
        help="Corpus directory for the quality-metrics baseline (default: docs/benchmark/corpus).",
    )
    parser.add_argument("--cli", default=None, help="Override the review CLI executable.")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--out", default=None, help="Also write the result to this JSON file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    output: dict[str, Any] = {}
    if args.mode in ("static", "all"):
        output["static_surface"] = measure_static_surface()
    if args.mode in ("quality", "all"):
        try:
            output["quality_metrics"] = measure_quality_metrics(
                corpus_dir=Path(args.corpus_dir), cli=args.cli, timeout=args.timeout
            )
        except Exception as exc:  # noqa: BLE001 - report, never mask the static half
            output["quality_metrics_error"] = str(exc)
            print(f"error: {exc}", file=sys.stderr)

    text = json.dumps(output, indent=2, sort_keys=False)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    # Fail closed like run_benchmark.py's own exit-code contract: a
    # requested quality-metrics run that never executed is not success,
    # even though the static half (if requested) still printed/wrote fine.
    return 1 if "quality_metrics_error" in output else 0


if __name__ == "__main__":
    raise SystemExit(main())
