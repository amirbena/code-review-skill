#!/usr/bin/env python3
"""Execution-side entrypoint for the scheduled benchmark lanes (Issues #415, #431, #470).

Runs a lane through `run_benchmark.py`, verifies every invocation, evaluates drift with
in-run confirmation, and seals the canonical result to the handoff. It performs no GitHub
write other than the seal; publication is the publisher's (Issue #471).

Contract: `docs/benchmark/cloud-routine-integration.md`. Modes: `smoke` / `selected` (verified
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
from runtime_platform.benchmark.scripts.benchmark_baseline import (  # noqa: E402
    DirectoryHistory,
    GitRefHistory,
    HistorySource,
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
    invoke,
    lane_corpus,
    spec_sha256,
    utc_now,
)
from runtime_platform.benchmark.scripts.benchmark_review_adapter import resolve_cli_executable  # noqa: E402
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


def _git_sha(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def _git_ref() -> str:
    proc = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else "HEAD"


def _runtime_version(executable: str) -> str:
    """Best-effort CLI version probe; the Routine prompt may override it."""
    try:
        proc = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=30)
        return proc.stdout.strip() or proc.stderr.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


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
    parser.add_argument("--seal-remote", default="origin", help="Git remote the seal is pushed to.")
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
    if errors:
        raise RoutineExecutionError(f"invalid manifest {path}: {errors[0]}")
    return manifest


def _history_source(args: argparse.Namespace) -> HistorySource:
    if args.history_root is not None:
        return DirectoryHistory(args.history_root)
    return GitRefHistory(REPO_ROOT, remote=args.seal_remote)


def _write_results_out(path: Path | None, raw_invocations: list[dict]) -> None:
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(raw_invocations, indent=2), encoding="utf-8")


def _hand_off(args: argparse.Namespace, ref: str, files: Mapping[str, bytes], commit_file: str, message: str) -> str:
    if args.seal_dir is not None:
        return str(seal.seal_to_directory(args.seal_dir, files, commit_file))
    return f"{args.seal_remote}:{ref}@{seal.seal_to_ref(REPO_ROOT, args.seal_remote, ref, files, message)}"


def run_handoff_check(args: argparse.Namespace) -> int:
    """Smoke-test that this runtime can seal (contract §5); runs no benchmark."""
    repo_sha = _git_sha(REPO_ROOT)
    stamp = utc_now()
    ref = f"{seal.HANDOFF_CHECK_REF_PREFIX}{stamp.replace('-', '').replace(':', '')}-{repo_sha[:12]}"
    payload = {"purpose": "handoff smoke test; not a benchmark result", "repo_sha": repo_sha, "at": stamp}
    files = {seal.HANDOFF_CHECK_FILE: seal.encode_json(payload)}
    where = _hand_off(args, ref, files, seal.HANDOFF_CHECK_FILE, f"benchmark handoff check {stamp}")
    print(json.dumps({"passed": True, "handoff": where, "ref": ref, "timestamp": stamp}, indent=2))
    return 0


def run_benchmark_mode(args: argparse.Namespace) -> int:
    plan = _plan(args)
    manifest = _load_manifest(args.manifest) if plan.corpus is not None else None
    spec = spec_sha256(manifest) if manifest is not None else None  # fail before any invocation
    executable = args.cli or resolve_cli_executable()
    runtime = {
        "runtime_name": args.runtime_name or executable,
        "runtime_version": args.runtime_version or _runtime_version(executable),
        "model_id": args.model_id,
    }
    repo_sha, started_at, started_mono = _git_sha(REPO_ROOT), utc_now(), time.monotonic()

    invocations: list[Invocation] = [invoke(executable, args.timeout, cid, where) for cid, where in plan.invocations]
    raw_invocations = [
        {"case_id": cid, "run": inv.output["run"]} for (cid, _), inv in zip(plan.invocations, invocations)
    ]
    _write_results_out(args.results_out, raw_invocations)

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
        run, plan.corpus, invocations, raw_invocations, manifest, _history_source(args)
    )
    where = _hand_off(args, sealed.ref, sealed.files, seal.RECORD_FILE, f"benchmark result {sealed.run_id}")
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
    try:
        if args.mode == "auth-check":
            return run_handoff_check(args)
        return run_benchmark_mode(args)
    except (RoutineExecutionError, seal.SealError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
