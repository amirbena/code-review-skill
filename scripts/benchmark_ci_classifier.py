#!/usr/bin/env python3
"""Deterministic PR-applicability classifier for the benchmark CI check
(Issue #255).

Deliberately independent of ``scripts/release_lib/classification.py`` /
``scripts/release_worthiness.py``: a change set relevant to release
packaging is a different question from a change set that can affect
review-quality benchmark results, and the two must never route through
each other's decision logic or import each other's modules. Contract:
docs/benchmark/ci-integration.md.

Usage::

    python3 scripts/benchmark_ci_classifier.py --base-ref origin/main
    python3 scripts/benchmark_ci_classifier.py --changed-files-from changed.txt
    python3 scripts/benchmark_ci_classifier.py --base-ref origin/main --github-output "$GITHUB_OUTPUT"
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

# The minimum path set the issue calls review-behavior-affecting: shared
# review rules, either packaged Skill, the benchmark contract docs, the
# corpus/reference fixtures a benchmark run reads, and the two scripts that
# drive it. Extend this tuple/frozenset to broaden applicability; do not add
# branching logic at a call site.
APPLICABLE_PREFIXES = (
    "shared/",
    "skills/",
    "docs/benchmark/",
    "tests/reference/benchmark/",
)
APPLICABLE_EXACT_FILES = frozenset(
    {
        "scripts/run_benchmark.py",
        "scripts/benchmark_review_adapter.py",
    }
)


def _normalize(path: str) -> str:
    p = path.strip().replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def is_applicable_path(path: str) -> bool:
    """Whether one repository-relative path can affect benchmark results."""
    p = _normalize(path)
    if not p:
        return False
    return p in APPLICABLE_EXACT_FILES or p.startswith(APPLICABLE_PREFIXES)


@dataclass(frozen=True)
class BenchmarkApplicability:
    """Outcome of classifying a whole changed-paths set."""

    applicable_paths: tuple[str, ...]
    other_paths: tuple[str, ...]

    @property
    def applicable(self) -> bool:
        return bool(self.applicable_paths)

    @property
    def reason(self) -> str:
        if not self.applicable_paths:
            return "no review-behavior-affecting paths changed"
        sample = ", ".join(self.applicable_paths[:3])
        more = "" if len(self.applicable_paths) <= 3 else f" (+{len(self.applicable_paths) - 3} more)"
        return f"review-behavior-affecting paths changed: {sample}{more}"


def classify_changed_paths(paths: Iterable[str]) -> BenchmarkApplicability:
    """Pure function: changed repository-relative paths -> applicability."""
    applicable: list[str] = []
    other: list[str] = []
    for raw in paths:
        p = _normalize(raw)
        if not p:
            continue
        (applicable if is_applicable_path(p) else other).append(p)
    return BenchmarkApplicability(tuple(applicable), tuple(other))


def _changed_files_from_git(repo_root: Path, base_ref: str) -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _emit_output(path: str | None, **pairs: str) -> None:
    target = path or os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        for key, value in pairs.items():
            handle.write(f"{key}={value}\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Classify a PR's changed paths as benchmark-applicable or not."
    )
    parser.add_argument("--repo-root", default=".", help="repository root (default: cwd)")
    parser.add_argument(
        "--base-ref",
        default=None,
        help="diff HEAD against this ref (git diff --name-only <ref>...HEAD)",
    )
    parser.add_argument(
        "--changed-files-from",
        default=None,
        help="path to a newline-delimited file of changed paths (overrides --base-ref)",
    )
    parser.add_argument("--github-output", default=None, help="path for the applicable/reason outputs")
    parser.add_argument("--step-summary", default=None, help="append a Markdown summary here")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve()

    if args.changed_files_from:
        paths = Path(args.changed_files_from).read_text(encoding="utf-8").splitlines()
    elif args.base_ref:
        paths = _changed_files_from_git(repo_root, args.base_ref)
    else:
        build_arg_parser().error("one of --changed-files-from or --base-ref is required")
        return 2  # pragma: no cover - argparse.error already exits

    result = classify_changed_paths(paths)

    print(f"Benchmark CI applicability: {result.applicable} ({result.reason})")
    _emit_output(args.github_output, applicable=str(result.applicable).lower(), reason=result.reason)
    if args.step_summary:
        with open(args.step_summary, "a", encoding="utf-8") as handle:
            handle.write("## Benchmark CI applicability\n\n")
            handle.write(f"- Applicable: `{result.applicable}`\n")
            handle.write(f"- Reason: {result.reason}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
