#!/usr/bin/env python3
"""Deterministic, non-LLM inverted-index build for the benchmark candidate
taxonomy (Issue #333). Contract: runtime_platform/benchmark/taxonomy.md §5.

Parses every corpus case's already-validated ``metadata.taxonomy`` and
produces ``{ (dimension, value) -> [case_id, ...] }``, serialized as
docs/benchmark/corpus-index.json. This is deliberately the only way the
index is produced: never hand-edited, always regenerated from the corpus.

Usage::

    python3 runtime_platform/benchmark/scripts/build_benchmark_index.py
    python3 runtime_platform/benchmark/scripts/build_benchmark_index.py --check
    python3 runtime_platform/benchmark/scripts/build_benchmark_index.py --corpus-dir path/to/corpus

``--check`` builds the index in memory and exits non-zero if it differs
from the committed file, without writing — the same computation
tests/policy/benchmark/test_benchmark_index_sync.py pins.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from runtime_platform.benchmark.reference import benchmark_fixture as bf  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_taxonomy as tax  # noqa: E402

DEFAULT_CORPUS_DIR = _REPO_ROOT / "docs" / "benchmark" / "corpus"
DEFAULT_INDEX_PATH = _REPO_ROOT / "docs" / "benchmark" / "corpus-index.json"


def _corpus_files(corpus_dir: Path) -> list[Path]:
    return sorted(corpus_dir.glob("**/*.yaml"))


def build_index(corpus_dir: Path = DEFAULT_CORPUS_DIR) -> dict[str, dict[str, list[str]]]:
    """Build ``{dimension: {value: [case_id, ...]}}`` from every case under
    ``corpus_dir``. Fails closed: a case that does not parse/validate is a
    hard error, not a skip — the index must never silently omit a case."""
    index: dict[str, dict[str, set[str]]] = {dim: {} for dim in tax.DIMENSIONS}

    for path in _corpus_files(corpus_dir):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        try:
            case = bf.parse_case(data)
        except bf.FixtureFormatError as exc:
            raise bf.FixtureFormatError(f"{path}: {exc}") from exc

        raw_taxonomy = case.metadata["taxonomy"]
        for dim in tax.DIMENSIONS:
            for value in raw_taxonomy[dim]:
                index[dim].setdefault(value, set()).add(case.id)

    return {
        dim: {value: sorted(case_ids) for value, case_ids in sorted(values.items())}
        for dim, values in index.items()
    }


def render_index(index: dict[str, dict[str, list[str]]]) -> str:
    # Deterministic: fixed dimension order (tax.DIMENSIONS is insertion-
    # ordered), sorted values, sorted case ids, stable indentation.
    ordered: dict[str, Any] = {dim: index[dim] for dim in tax.DIMENSIONS}
    return json.dumps(ordered, indent=2, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--index-path", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed index matches a fresh build; do not write",
    )
    args = parser.parse_args(argv)

    index = build_index(args.corpus_dir)
    rendered = render_index(index)

    if args.check:
        existing = args.index_path.read_text(encoding="utf-8") if args.index_path.is_file() else None
        if existing != rendered:
            sys.stderr.write(
                f"{args.index_path} is out of sync with the live corpus under "
                f"{args.corpus_dir} — run runtime_platform/benchmark/scripts/build_benchmark_index.py "
                "to regenerate it.\n"
            )
            return 1
        return 0

    args.index_path.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
