#!/usr/bin/env python3
"""Nightly full-corpus history persistence and baseline policy (Issue #338).

Consumes a verified run already produced by the Class 2 Cloud Routine
vehicle (`run_benchmark_routine.py --results-out ...`, Issue #415) and
persists it into a `benchmark-history`-branch checkout keyed by date and
commit SHA, plus maintains a single pinned baseline artifact that only an
explicit `promote-baseline` call ever moves. Full contract:
`runtime_platform/benchmark/nightly-history-and-baseline.md`.

This module never runs the reviewer, never verifies a run's completion
(that is `benchmark_routine_verify.py`), and never decides whether a run
regressed (that is Issue #339). It only stores and retrieves.

Usage::

    python3 runtime_platform/benchmark/scripts/benchmark_history.py record \\
        --history-root ./benchmark-history-checkout \\
        --results-file /tmp/benchmark-nightly-results.json \\
        --routine-metadata-file /tmp/benchmark-nightly-metadata.json

    python3 runtime_platform/benchmark/scripts/benchmark_history.py promote-baseline \\
        --history-root ./benchmark-history-checkout

    python3 runtime_platform/benchmark/scripts/benchmark_history.py show-baseline \\
        --history-root ./benchmark-history-checkout
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.scripts import run_benchmark as rb  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_corpus_membership import (  # noqa: E402
    DEFAULT_LANE,
    canonical_lane,
    discover_comprehensive_fixtures,
)

DEFAULT_RETENTION = 90
HISTORY_SUBDIR = "history"
BASELINE_FILENAME = "baseline.json"


class HistoryError(RuntimeError):
    """A history/baseline operation could not complete safely."""


def corpus_digest(corpus_dir: Path) -> str:
    """regression-report.md §2's `corpus_id`: every fixture id + a content digest.

    Mirrors `runtime_platform/benchmark/reference/benchmark_report.py::corpus_digest`
    (test-only) so values computed here are directly comparable once #339
    installs that report against real history.
    """
    h = hashlib.sha256()
    for path in sorted(corpus_dir.glob("*.yaml")):
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def comprehensive_corpus_digest(corpus_root: Path) -> str:
    """The comprehensive lane's own `corpus_id` (Issue #431).

    Same identity shape as `corpus_digest` (every fixture id/path +
    content digest, so a corpus change is detected rather than silently
    accepted — regression-report.md §2/§3), but computed over the
    recursively-discovered `benchmark-case/v2` membership
    (`benchmark_corpus_membership.discover_comprehensive_fixtures`)
    instead of `corpus_dir`'s own non-recursive top-level glob. This
    deliberately produces a *different* `corpus_id` than `corpus_digest`
    for the same `corpus_root` (89 fixtures vs. 4), which is exactly what
    lets `compare()`'s existing `corpus_id` fail-closed guard
    (`runtime_platform/benchmark/reference/benchmark_report.py::compare`) refuse a
    sentinel-vs-comprehensive cross-comparison automatically, with no new
    guard code.
    """
    h = hashlib.sha256()
    for fixture in discover_comprehensive_fixtures(corpus_root):
        relative = fixture.fixture_path.relative_to(corpus_root)
        h.update(str(relative).encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(fixture.fixture_path.read_bytes()).digest())
    return h.hexdigest()


def corpus_digest_for_lane(lane: str, corpus_root: Path) -> str:
    """Dispatch to the right `corpus_id` derivation for a lane (Issue #431)."""
    if lane == DEFAULT_LANE:
        return corpus_digest(corpus_root)
    return comprehensive_corpus_digest(corpus_root)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_raw_cases(results_file: Path) -> list[dict]:
    """Flatten `run_benchmark_routine.py --results-out`'s payload into the
    runner's per-case result list (`runner-contract.md` §6).

    Re-validates every case's ``status`` here rather than trusting the
    file's provenance: the vehicle only ever writes this file after
    `benchmark_routine_verify.py` passes, but `record` is a general CLI
    that can be pointed at any file, and a corrupted/partial run must
    never silently become a persisted baseline (regression-report.md §2's
    `BaselineArtifact.from_run` applies the same `run.ok` guard).
    """
    data = json.loads(results_file.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise HistoryError(f"malformed or empty results file: {results_file}")
    cases: list[dict] = []
    for invocation in data:
        run = invocation.get("run") if isinstance(invocation, dict) else None
        if not isinstance(run, dict) or not isinstance(run.get("cases"), list):
            raise HistoryError(f"malformed results-file invocation entry: {invocation!r}")
        cases.extend(run["cases"])
    if not cases:
        raise HistoryError("results file carries no cases — refusing to persist an empty run")
    for case in cases:
        if not isinstance(case, dict) or case.get("status") != "executed":
            raise HistoryError(f"refusing to persist a non-executed case: {case!r}")
    return cases


@dataclass(frozen=True)
class HistoryEntry:
    date: str
    repo_sha: str
    corpus_id: str
    adapter_id: str
    recorded_at: str
    routine_metadata: dict
    results: tuple[dict, ...]
    # Keyed/named-baseline identity (Issue #431): which scheduled lane this
    # entry belongs to. Reuses the existing `routine_metadata["mode"]`
    # value (canonicalized via `canonical_lane`) rather than inventing a
    # new identity concept — see `_cmd_record` below, the only place a
    # `HistoryEntry` is constructed from a real run. Defaults to the
    # pre-#431 single-lane behavior so existing callers/tests are
    # unaffected.
    lane: str = DEFAULT_LANE

    def filename(self) -> str:
        return f"{self.date}-{self.repo_sha[:12]}.json"

    def as_dict(self) -> dict:
        return {
            "date": self.date,
            "repo_sha": self.repo_sha,
            "corpus_id": self.corpus_id,
            "adapter_id": self.adapter_id,
            "recorded_at": self.recorded_at,
            "routine_metadata": self.routine_metadata,
            "results": list(self.results),
            "lane": self.lane,
        }

    def to_baseline_artifact(self, source_entry: str) -> dict:
        """regression-report.md §2 baseline artifact shape."""
        return {
            "results": list(self.results),
            "corpus_id": self.corpus_id,
            "adapter_id": self.adapter_id,
            "created_at": _utc_now_iso(),
            "source_entry": source_entry,
        }


@dataclass(frozen=True)
class RecordOutcome:
    entry_path: Path
    is_bootstrap: bool
    pruned: tuple[Path, ...]

    def as_dict(self) -> dict:
        return {
            "entry_path": str(self.entry_path),
            "is_bootstrap": self.is_bootstrap,
            "pruned": [str(p) for p in self.pruned],
        }


def _history_dir(root: Path, lane: str = DEFAULT_LANE) -> Path:
    """Per-lane history directory (Issue #431).

    The default lane (`sentinel`, including the deprecated `full` alias)
    keeps the pre-#431 path (`<root>/history`) unchanged, so existing
    `benchmark-history` branch content and consumers are unaffected. Any
    other lane (`comprehensive`) gets its own sibling directory, which
    isolates retention/pruning per lane without filename parsing: a
    comprehensive run can never prune, overwrite, or be counted against
    the sentinel lane's retention budget, and vice versa.
    """
    directory = root / HISTORY_SUBDIR if lane == DEFAULT_LANE else root / f"{HISTORY_SUBDIR}-{lane}"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _baseline_path(root: Path, lane: str = DEFAULT_LANE) -> Path:
    """Per-lane baseline artifact path (Issue #431).

    The default lane keeps the pre-#431 `baseline.json` path unchanged;
    any other lane gets its own `baseline-<lane>.json`, so sentinel and
    comprehensive each pin and compare against their own baseline
    (`nightly-history-and-baseline.md` §4) and can never be mixed up by
    path collision.
    """
    if lane == DEFAULT_LANE:
        return root / BASELINE_FILENAME
    return root / f"baseline-{lane}.json"


def load_baseline(root: Path, lane: str = DEFAULT_LANE) -> dict | None:
    path = _baseline_path(root, lane)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def record_run(root: Path, entry: HistoryEntry, *, retention: int = DEFAULT_RETENTION) -> RecordOutcome:
    if retention < 1:
        raise HistoryError("retention must keep at least 1 entry")

    entry_path = _history_dir(root, entry.lane) / entry.filename()
    if entry_path.exists():
        raise HistoryError(f"history entry already exists (refusing to overwrite): {entry_path}")
    entry_path.write_text(json.dumps(entry.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    baseline_path = _baseline_path(root, entry.lane)
    is_bootstrap = not baseline_path.exists()
    if is_bootstrap:
        source_entry = str(entry_path.relative_to(root))
        baseline_path.write_text(
            json.dumps(entry.to_baseline_artifact(source_entry), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    pruned = _prune_history(root, entry.lane, retention=retention)
    return RecordOutcome(entry_path=entry_path, is_bootstrap=is_bootstrap, pruned=pruned)


def _protected_entry_path(root: Path, lane: str) -> Path | None:
    baseline = load_baseline(root, lane)
    if baseline is None:
        return None
    return root / baseline["source_entry"]


def _prune_history(root: Path, lane: str, *, retention: int) -> tuple[Path, ...]:
    """Keep the newest `retention` entries *for this lane*; that lane's
    current baseline source entry is always kept regardless of age
    (nightly-history-and-baseline.md §3.3) so a promoted baseline can
    never be pruned out from under #339. Lanes are isolated by directory
    (`_history_dir`), so pruning one lane never touches another's entries
    or retention budget.

    Paths are compared by resolved identity, not string equality, since
    ``root`` may be reached through a symlinked tmp path (e.g. macOS's
    ``/var`` -> ``/private/var``) that differs syntactically but not
    physically from the paths ``glob`` returns.
    """
    entries = sorted(_history_dir(root, lane).glob("*.json"), reverse=True)
    protected = _protected_entry_path(root, lane)
    protected_resolved = protected.resolve() if protected is not None and protected.exists() else None
    keep_resolved = {p.resolve() for p in entries[:retention]}
    if protected_resolved is not None:
        keep_resolved.add(protected_resolved)
    pruned = tuple(p for p in entries if p.resolve() not in keep_resolved)
    for path in pruned:
        path.unlink()
    return pruned


def promote_baseline(root: Path, entry_path: Path | None = None, lane: str = DEFAULT_LANE) -> dict:
    entries = sorted(_history_dir(root, lane).glob("*.json"))
    if entry_path is None:
        if not entries:
            raise HistoryError("no history entries to promote — run `record` first")
        entry_path = entries[-1]
    if not entry_path.exists():
        raise HistoryError(f"history entry not found: {entry_path}")

    data = json.loads(entry_path.read_text(encoding="utf-8"))
    artifact = {
        "results": data["results"],
        "corpus_id": data["corpus_id"],
        "adapter_id": data["adapter_id"],
        "created_at": _utc_now_iso(),
        "source_entry": str(entry_path.relative_to(root)),
    }
    _baseline_path(root, lane).write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    record = sub.add_parser("record", help="Persist one verified run into history.")
    record.add_argument("--history-root", required=True, type=Path)
    record.add_argument("--results-file", required=True, type=Path)
    record.add_argument("--routine-metadata-file", required=True, type=Path)
    record.add_argument("--corpus-dir", default=str(rb.DEFAULT_CORPUS_DIR), type=Path)
    record.add_argument("--adapter-id", default=None, help="Defaults to the routine metadata's repo_sha.")
    record.add_argument("--retention", type=int, default=DEFAULT_RETENTION)
    record.add_argument("--date", default=None, help="Override the UTC date (testing only).")
    record.add_argument(
        "--lane",
        default=None,
        choices=["sentinel", "comprehensive"],
        help="Keyed/named-baseline lane (Issue #431). Defaults to the routine metadata's "
        "own `mode` field, canonicalized (`full` -> `sentinel`) — explicit override is "
        "rarely needed outside tests.",
    )

    promote = sub.add_parser(
        "promote-baseline", help="Explicit maintainer action: pin a history entry as the new baseline."
    )
    promote.add_argument("--history-root", required=True, type=Path)
    promote.add_argument("--entry", default=None, type=Path, help="Defaults to the most recent history entry.")
    promote.add_argument("--lane", default=DEFAULT_LANE, choices=["sentinel", "comprehensive"])

    show = sub.add_parser("show-baseline", help="Print the current baseline, or a bootstrap notice.")
    show.add_argument("--history-root", required=True, type=Path)
    show.add_argument("--lane", default=DEFAULT_LANE, choices=["sentinel", "comprehensive"])

    return parser


def _cmd_record(args: argparse.Namespace) -> int:
    routine_result = json.loads(args.routine_metadata_file.read_text(encoding="utf-8"))
    metadata = routine_result.get("metadata", routine_result)
    repo_sha = metadata["repo_sha"]
    cases = load_raw_cases(args.results_file)
    # Reuses the existing `mode` field as the lane identity (Issue #431)
    # rather than inventing a new one — `--lane` only exists to override
    # this for tests/edge cases.
    lane = args.lane or canonical_lane(metadata.get("mode", DEFAULT_LANE))
    entry = HistoryEntry(
        date=args.date or _utc_today(),
        repo_sha=repo_sha,
        corpus_id=corpus_digest_for_lane(lane, Path(args.corpus_dir)),
        adapter_id=args.adapter_id or repo_sha,
        recorded_at=_utc_now_iso(),
        routine_metadata=metadata,
        results=tuple(cases),
        lane=lane,
    )
    outcome = record_run(args.history_root, entry, retention=args.retention)
    print(json.dumps(outcome.as_dict(), indent=2))
    return 0


def _cmd_promote(args: argparse.Namespace) -> int:
    artifact = promote_baseline(args.history_root, args.entry, lane=args.lane)
    print(json.dumps({"promoted": True, "corpus_id": artifact["corpus_id"], "source_entry": artifact["source_entry"]}, indent=2))
    return 0


def _cmd_show_baseline(args: argparse.Namespace) -> int:
    baseline = load_baseline(args.history_root, lane=args.lane)
    if baseline is None:
        print(json.dumps({"baseline_exists": False, "lane": args.lane}, indent=2))
        return 0
    print(json.dumps({"baseline_exists": True, **baseline}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        if args.command == "record":
            return _cmd_record(args)
        if args.command == "promote-baseline":
            return _cmd_promote(args)
        return _cmd_show_baseline(args)
    except HistoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
