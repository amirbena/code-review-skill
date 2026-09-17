#!/usr/bin/env python3
"""Nightly full-corpus history persistence and baseline policy (Issue #338).

Consumes a verified run already produced by the Class 2 Cloud Routine
vehicle (`run_benchmark_routine.py --results-out ...`, Issue #415) and
persists it into a `benchmark-history`-branch checkout keyed by date and
commit SHA, plus maintains a single pinned baseline artifact that only an
explicit `promote-baseline` call ever moves. Full contract:
`docs/benchmark/nightly-history-and-baseline.md`.

This module never runs the reviewer, never verifies a run's completion
(that is `benchmark_routine_verify.py`), and never decides whether a run
regressed (that is Issue #339). It only stores and retrieves.

Usage::

    python3 scripts/benchmark/benchmark_history.py record \\
        --history-root ./benchmark-history-checkout \\
        --results-file /tmp/benchmark-nightly-results.json \\
        --routine-metadata-file /tmp/benchmark-nightly-metadata.json

    python3 scripts/benchmark/benchmark_history.py promote-baseline \\
        --history-root ./benchmark-history-checkout

    python3 scripts/benchmark/benchmark_history.py show-baseline \\
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

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.benchmark import run_benchmark as rb  # noqa: E402

DEFAULT_RETENTION = 90
HISTORY_SUBDIR = "history"
BASELINE_FILENAME = "baseline.json"


class HistoryError(RuntimeError):
    """A history/baseline operation could not complete safely."""


def corpus_digest(corpus_dir: Path) -> str:
    """regression-report.md §2's `corpus_id`: every fixture id + a content digest.

    Mirrors `tests/reference/benchmark/benchmark_report.py::corpus_digest`
    (test-only) so values computed here are directly comparable once #339
    installs that report against real history.
    """
    h = hashlib.sha256()
    for path in sorted(corpus_dir.glob("*.yaml")):
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_raw_cases(results_file: Path) -> list[dict]:
    """Flatten `run_benchmark_routine.py --results-out`'s payload into the
    runner's per-case result list (`runner-contract.md` §6)."""
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


def _history_dir(root: Path) -> Path:
    directory = root / HISTORY_SUBDIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _baseline_path(root: Path) -> Path:
    return root / BASELINE_FILENAME


def load_baseline(root: Path) -> dict | None:
    path = _baseline_path(root)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def record_run(root: Path, entry: HistoryEntry, *, retention: int = DEFAULT_RETENTION) -> RecordOutcome:
    if retention < 1:
        raise HistoryError("retention must keep at least 1 entry")

    entry_path = _history_dir(root) / entry.filename()
    if entry_path.exists():
        raise HistoryError(f"history entry already exists (refusing to overwrite): {entry_path}")
    entry_path.write_text(json.dumps(entry.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    baseline_path = _baseline_path(root)
    is_bootstrap = not baseline_path.exists()
    if is_bootstrap:
        source_entry = str(entry_path.relative_to(root))
        baseline_path.write_text(
            json.dumps(entry.to_baseline_artifact(source_entry), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    pruned = _prune_history(root, retention=retention)
    return RecordOutcome(entry_path=entry_path, is_bootstrap=is_bootstrap, pruned=pruned)


def _protected_entry_path(root: Path) -> Path | None:
    baseline = load_baseline(root)
    if baseline is None:
        return None
    return root / baseline["source_entry"]


def _prune_history(root: Path, *, retention: int) -> tuple[Path, ...]:
    """Keep the newest `retention` entries; the current baseline's source
    entry is always kept regardless of age (nightly-history-and-baseline.md
    §3.3) so a promoted baseline can never be pruned out from under #339.

    Paths are compared by resolved identity, not string equality, since
    ``root`` may be reached through a symlinked tmp path (e.g. macOS's
    ``/var`` -> ``/private/var``) that differs syntactically but not
    physically from the paths ``glob`` returns.
    """
    entries = sorted(_history_dir(root).glob("*.json"), reverse=True)
    protected = _protected_entry_path(root)
    protected_resolved = protected.resolve() if protected is not None and protected.exists() else None
    keep_resolved = {p.resolve() for p in entries[:retention]}
    if protected_resolved is not None:
        keep_resolved.add(protected_resolved)
    pruned = tuple(p for p in entries if p.resolve() not in keep_resolved)
    for path in pruned:
        path.unlink()
    return pruned


def promote_baseline(root: Path, entry_path: Path | None = None) -> dict:
    entries = sorted(_history_dir(root).glob("*.json"))
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
    _baseline_path(root).write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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

    promote = sub.add_parser(
        "promote-baseline", help="Explicit maintainer action: pin a history entry as the new baseline."
    )
    promote.add_argument("--history-root", required=True, type=Path)
    promote.add_argument("--entry", default=None, type=Path, help="Defaults to the most recent history entry.")

    show = sub.add_parser("show-baseline", help="Print the current baseline, or a bootstrap notice.")
    show.add_argument("--history-root", required=True, type=Path)

    return parser


def _cmd_record(args: argparse.Namespace) -> int:
    routine_result = json.loads(args.routine_metadata_file.read_text(encoding="utf-8"))
    metadata = routine_result.get("metadata", routine_result)
    repo_sha = metadata["repo_sha"]
    cases = load_raw_cases(args.results_file)
    entry = HistoryEntry(
        date=args.date or _utc_today(),
        repo_sha=repo_sha,
        corpus_id=corpus_digest(Path(args.corpus_dir)),
        adapter_id=args.adapter_id or repo_sha,
        recorded_at=_utc_now_iso(),
        routine_metadata=metadata,
        results=tuple(cases),
    )
    outcome = record_run(args.history_root, entry, retention=args.retention)
    print(json.dumps(outcome.as_dict(), indent=2))
    return 0


def _cmd_promote(args: argparse.Namespace) -> int:
    artifact = promote_baseline(args.history_root, args.entry)
    print(json.dumps({"promoted": True, "corpus_id": artifact["corpus_id"], "source_entry": artifact["source_entry"]}, indent=2))
    return 0


def _cmd_show_baseline(args: argparse.Namespace) -> int:
    baseline = load_baseline(args.history_root)
    if baseline is None:
        print(json.dumps({"baseline_exists": False}, indent=2))
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
