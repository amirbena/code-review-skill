#!/usr/bin/env python3
"""Execution-side entrypoint for the scheduled benchmark lanes (Issues #415, #431, #470).

Runs a lane through `run_benchmark.py`, verifies every invocation, evaluates drift with
in-run confirmation, and seals the canonical result to the handoff. It performs no GitHub
write other than the seal; publication is the publisher's (Issue #471).

Contract: `benchmark/cloud-routine-integration.md`. Modes: `smoke` / `selected` (verified
output only, never sealed), `sentinel` / `comprehensive` (sealed lanes), `full` (deprecated
synonym for `sentinel`), `auth-check` (handoff smoke test, no benchmark).

Usage::

    python3 runtime_platform/benchmark/scripts/run_benchmark_routine.py --mode sentinel \\
        --trigger scheduled --model-id claude-opus-5
    python3 runtime_platform/benchmark/scripts/run_benchmark_routine.py --mode sentinel \\
        --seal-dir /tmp/sealed          # local dry run: nothing is pushed
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.scripts import benchmark_seal as seal  # noqa: E402
from runtime_platform.benchmark.scripts import run_benchmark as rb  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_baseline import DirectoryHistory, HistorySource  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_evidence_destination import (  # noqa: E402
    Destination,
    DestinationMisconfigured,
    StoreUnavailable,
    add_remote_argument,
    exit_for,
    resolve_destination,
)
from runtime_platform.benchmark.scripts.benchmark_corpus_membership import (  # noqa: E402
    SENTINEL_LANE,
    canonical_lane,
)
from runtime_platform.benchmark.scripts.benchmark_lane_run import (  # noqa: E402
    Invocation,
    LaneCorpus,
    LaneRun,
    RoutineExecutionError,
    build_sealed_run,
    git_ref as _git_ref,
    git_sha as _git_sha,
    invoke,
    lane_corpus,
    runtime_version as _runtime_version,
    spec_sha256,
    utc_now,
)
from runtime_platform.benchmark.scripts.benchmark_progress import ProgressLog  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_review_adapter import resolve_cli_executable  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_termination import (  # noqa: E402
    Terminated,
    terminate_on_signal,
    terminated_line,
)
from runtime_platform.benchmark.scripts.benchmark_schedule_manifest import (  # noqa: E402
    MANIFEST_PATH,
    ManifestError,
    load_manifest,
    validate_manifest,
)


@dataclass(frozen=True)
class RunMetadata:
    mode: str
    repo_sha: str
    runtime_name: str
    runtime_version: str
    model_id: str
    timestamp: str

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "repo_sha": self.repo_sha,
            "runtime_name": self.runtime_name,
            "runtime_version": self.runtime_version,
            "model_id": self.model_id,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class Plan:
    mode: str
    invocations: list[tuple[str | None, str]]
    corpus: LaneCorpus | None


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--mode",
        required=True,
        choices=["smoke", "selected", "sentinel", "comprehensive", "full", "auth-check"],
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Case id to run (repeatable). Required for smoke/selected; ignored otherwise.",
    )
    parser.add_argument("--corpus-dir", default=str(rb.DEFAULT_CORPUS_DIR))
    parser.add_argument("--cli", default=None, help="Override the review CLI executable.")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--runtime-name", default=None, help="Explicit runtime/CLI name (else the CLI executable).")
    parser.add_argument("--runtime-version", default=None, help="Explicit runtime/CLI version (else a probe).")
    parser.add_argument(
        "--model-id",
        default="unknown",
        help="Model backend identifier; not auto-detectable in a Cloud Routine, so the prompt sets it.",
    )
    parser.add_argument(
        "--trigger",
        choices=["scheduled", "manual", "api"],
        default="manual",
        help="How the run was started. Only the Routine prompt passes `scheduled`.",
    )
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="Expected-run manifest.")
    parser.add_argument(
        "--history-root",
        type=Path,
        default=None,
        help="Local benchmark-history checkout to read the baseline from (else the remote ref, read-only).",
    )
    add_remote_argument(parser)
    parser.add_argument(
        "--seal-dir",
        type=Path,
        default=None,
        help="Dry run: write the sealed files here instead of pushing a ref.",
    )
    parser.add_argument(
        "--confirmation-budget-s",
        type=float,
        default=None,
        help="Seconds from run start after which unfinished confirmations become unconfirmed-timeout.",
    )
    parser.add_argument(
        "--results-out",
        default=None,
        type=Path,
        help="Write the raw per-invocation output here (verified runs only); a local output, not the handoff.",
    )
    return parser


def _plan(args: argparse.Namespace) -> Plan:
    """Resolve `--mode` to its canonical mode and the `run_benchmark.py` invocations it needs.

    `full` is a deprecated fixed synonym for `sentinel` (Issue #431), so a sealed record never
    carries the ambiguous legacy name as its lane.
    """
    if args.mode in ("smoke", "selected"):
        if not args.case_id:
            raise RoutineExecutionError(f"--mode {args.mode} requires at least one --case-id")
        return Plan(args.mode, [(cid, args.corpus_dir) for cid in args.case_id], None)

    if args.mode == "full":
        print(
            "warning: --mode full is a deprecated fixed synonym for --mode sentinel "
            "(Issue #431); pass --mode sentinel explicitly in new configuration.",
            file=sys.stderr,
        )
    lane = canonical_lane(args.mode)
    corpus = lane_corpus(lane, args.corpus_dir)
    if lane == SENTINEL_LANE:
        return Plan(lane, [(None, args.corpus_dir)], corpus)
    return Plan(lane, [(cid, where) for cid, where in sorted(corpus.case_dirs.items())], corpus)


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = load_manifest(path)
    except ManifestError as exc:
        raise RoutineExecutionError(str(exc)) from exc
    errors = validate_manifest(manifest)
    if errors and errors[0].startswith("evidence"):
        raise DestinationMisconfigured(f"invalid manifest {path}: {errors[0]}")
    if errors:
        raise RoutineExecutionError(f"invalid manifest {path}: {errors[0]}")
    return manifest


def _destination(args: argparse.Namespace, manifest: dict[str, Any]) -> Destination | None:
    """The proven evidence destination, preflighted; `None` only for a fully local dry run."""
    if args.seal_dir is not None and args.history_root is not None:
        return None
    dest = resolve_destination(manifest, evidence_remote=args.evidence_remote, repo_root=REPO_ROOT)
    dest.preflight()
    return dest


def _destination_or_none(args: argparse.Namespace) -> Destination | None:
    return None if args.seal_dir is not None else _destination(args, _load_manifest(args.manifest))


def _history_source(args: argparse.Namespace, dest: Destination | None) -> HistorySource:
    if args.history_root is not None:
        return DirectoryHistory(args.history_root)
    assert dest is not None
    return dest.history()


def _write_results_out(path: Path | None, raw_invocations: list[dict]) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw_invocations, indent=2), encoding="utf-8")


def _hand_off(args: argparse.Namespace, dest: Destination | None, ref: str, files: Mapping[str, bytes], commit_file: str, message: str) -> str:
    if args.seal_dir is not None:
        return str(seal.seal_to_directory(args.seal_dir, files, commit_file))
    assert dest is not None
    return dest.location(ref, dest.seal(ref, files, message))


def run_handoff_check(args: argparse.Namespace) -> int:
    """Smoke-test that this runtime can seal (contract §5); runs no benchmark."""
    dest = _destination_or_none(args)
    repo_sha = _git_sha(REPO_ROOT)
    stamp = utc_now()
    ref = f"{seal.HANDOFF_CHECK_REF_PREFIX}{stamp.replace('-', '').replace(':', '')}-{repo_sha[:12]}"
    payload = {"purpose": "handoff smoke test; not a benchmark result", "repo_sha": repo_sha, "at": stamp}
    files = {seal.HANDOFF_CHECK_FILE: seal.encode_json(payload)}
    where = _hand_off(args, dest, ref, files, seal.HANDOFF_CHECK_FILE, f"benchmark handoff check {stamp}")
    print(json.dumps({"passed": True, "handoff": where, "ref": ref, "timestamp": stamp}, indent=2))
    return 0


def run_benchmark_mode(args: argparse.Namespace, progress: ProgressLog | None = None) -> int:
    progress = progress or ProgressLog()
    written: list[Path] = []
    try:
        return _run_benchmark_mode(args, progress, written)
    except Terminated:
        # A terminated run leaves no results file either (Issue #660); only a file this run wrote is removed.
        for path in written:
            path.unlink(missing_ok=True)
        raise


def _run_benchmark_mode(args: argparse.Namespace, progress: ProgressLog, written: list[Path]) -> int:
    with progress.phase("planning"):
        plan = _plan(args)
    progress.total = len(plan.invocations)
    progress.log(f"[{plan.mode}] discovered {progress.total} fixtures" if plan.corpus is not None else f"[{plan.mode}] {progress.total} invocations")
    manifest = _load_manifest(args.manifest) if plan.corpus is not None else None
    spec = spec_sha256(manifest) if manifest is not None else None  # fail before any invocation
    dest = _destination(args, manifest) if manifest is not None else None  # proven and preflighted before any model cost
    executable = args.cli or resolve_cli_executable()
    runtime = {
        "runtime_name": args.runtime_name or executable,
        "runtime_version": args.runtime_version or _runtime_version(executable),
        "model_id": args.model_id,
    }
    repo_sha, started_at, started_mono = _git_sha(REPO_ROOT), utc_now(), time.monotonic()

    invocations: list[Invocation] = []
    with progress.phase("fixtures"):
        for position, (cid, where) in enumerate(plan.invocations, start=1):
            invocations.append(
                progress.item(f"[{position}/{progress.total}]", cid or "<whole-corpus>", lambda: invoke(executable, args.timeout, cid, where))
            )
    raw_invocations = [
        {"case_id": cid, "run": inv.output["run"]} for (cid, _), inv in zip(plan.invocations, invocations)
    ]
    _write_results_out(args.results_out, raw_invocations)
    if args.results_out is not None:
        written.append(args.results_out)

    if plan.corpus is None:
        metadata = RunMetadata(plan.mode, repo_sha, *(runtime[k] for k in ("runtime_name", "runtime_version", "model_id")), started_at)
        print(json.dumps({"metadata": metadata.as_dict(), "overall_verified": True, "runs": [i.verification for i in invocations]}, indent=2))
        return 0

    run = LaneRun(
        lane=plan.mode,
        mode=args.mode,
        trigger=args.trigger,
        executable=executable,
        timeout=args.timeout,
        runtime=runtime,
        repo_sha=repo_sha,
        repo_ref=_git_ref(),
        started_at=started_at,
        started_mono=started_mono,
        spec_sha256=spec,
        confirmation_budget_s=args.confirmation_budget_s,
    )
    sealed = build_sealed_run(
        run, plan.corpus, invocations, raw_invocations, manifest, _history_source(args, dest), progress=progress
    )
    try:
        with progress.phase("seal-handoff"):
            where = _hand_off(args, dest, sealed.ref, sealed.files, seal.RECORD_FILE, f"benchmark result {sealed.run_id}")
    except StoreUnavailable as exc:  # the run stays unsealed; its files are kept locally for diagnosis
        return exit_for(exc, run_id=sealed.run_id, destination=dest, files=sealed.files, commit_file=seal.RECORD_FILE)
    record = sealed.record
    print(
        json.dumps(
            {
                "run_id": sealed.run_id,
                "handoff": where,
                "content_sha256": record["content_sha256"],
                "baseline_state": record["baseline"]["state"],
                "drift_outcome": record["drift"]["outcome"],
                "confirmed": len(record["drift"]["confirmed"]),
                "unconfirmed": len(record["drift"]["unconfirmed"]),
            },
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    progress = ProgressLog()
    try:
        with terminate_on_signal(lambda: (progress.phase_name, progress.current_case)):
            if args.mode == "auth-check":
                return run_handoff_check(args)
            return run_benchmark_mode(args, progress)
    except Terminated as exc:  # fail closed: non-zero, never a success line (Issue #660)
        progress.log(terminated_line(exc))
        return exc.exit_code
    except (DestinationMisconfigured, StoreUnavailable) as exc:
        return exit_for(exc)
    except (RoutineExecutionError, seal.SealError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
