#!/usr/bin/env python3
"""TEMPORARY entrypoint: bounded-parallel fixture execution measurement (Issue #681).

Runs a deterministic fixture subset at 1, 2 and/or 4 workers through the same per-fixture
`run_benchmark.py` path the lanes use, and seals the diagnostics to a `claude/concurrency-experiment-*`
ref. It has no lane, baseline, drift, seal-for-publication or GitHub write path, and its result is
never a lane record. Spec, evidence format, isolation audit, stop condition and removal path:
`runtime_platform/benchmark/concurrency-experiment.md`.

Usage::

    python3 runtime_platform/benchmark/scripts/run_concurrency_experiment.py \\
        --trigger scheduled --model-id <the model backend this Routine session runs as>
    python3 runtime_platform/benchmark/scripts/run_concurrency_experiment.py \\
        --arms 1,2 --seal-dir /tmp/experiment      # local dry run: nothing is pushed
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.reference.benchmark_runner import capture_repo_state  # noqa: E402
from runtime_platform.benchmark.scripts import benchmark_concurrency_workers as workers_mod  # noqa: E402
from runtime_platform.benchmark.scripts import benchmark_seal as seal  # noqa: E402
from runtime_platform.benchmark.scripts import run_benchmark as rb  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_concurrency_workers import (  # noqa: E402
    ArmResult,
    Fixture,
    LiveChildren,
    Violation,
)
from runtime_platform.benchmark.scripts.benchmark_corpus_membership import COMPREHENSIVE_LANE  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_lane_run import (  # noqa: E402
    RoutineExecutionError,
    git_ref,
    git_sha,
    lane_corpus,
    runtime_version,
    utc_now,
)
from runtime_platform.benchmark.scripts.benchmark_progress import ProgressLog  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_review_adapter import resolve_cli_executable  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_termination import Terminated, terminate_on_signal, terminated_line  # noqa: E402

SPEC_PATH = REPO_ROOT / "runtime_platform" / "benchmark" / "schedule" / "concurrency-experiment-spec.json"
EXPERIMENT_SCHEMA = "concurrency-experiment/v1"
EXPERIMENT_REF_PREFIX = "claude/concurrency-experiment-"
TRIAL_REF_PREFIX = "claude/concurrency-trial-"  # not matched by the experiment prefix: never counted
EXPERIMENT_FILE = "concurrency-experiment.json"
RAW_FILE = "raw-output.json"
GIT_TIMEOUT_S = 60

SHARED_SURFACES = {
    "review_cli_state": "shared and not isolated: redirecting it would drop the Routine's authentication; recorded as a before/after fingerprint",
    "git_config": "hermetic in every child (no system or global config); the global and repository config digests are checked unchanged",
    "temp_dirs": "one scratch directory per worker slot, set as the child's temp directory; a workspace left behind is a violation",
    "progress_and_signals": "per child process (own ProgressLog and main-thread handlers); the parent only waits, and on termination stops every child tree",
    "stderr": "captured per fixture and forwarded as worker-tagged START/DONE lines, never interleaved raw",
}


def load_spec(path: Path = SPEC_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def experiment_ref(run_id: str, trigger: str = "scheduled") -> str:
    """Only a scheduled run is an experiment; anything else is a trial that is never counted."""
    return f"{EXPERIMENT_REF_PREFIX if trigger == 'scheduled' else TRIAL_REF_PREFIX}{run_id}"


def confined_ref(ref: str) -> str:
    """The seal is confined to this experiment's two prefixes; anything else is refused."""
    if not ref.startswith((EXPERIMENT_REF_PREFIX, TRIAL_REF_PREFIX)) or ref.startswith(seal.STAGING_REF_PREFIX):
        raise RoutineExecutionError(f"refusing to write {ref!r}: only {EXPERIMENT_REF_PREFIX}* and {TRIAL_REF_PREFIX}* are allowed")
    return ref


def make_run_id(timestamp: str, repo_sha: str) -> str:
    return f"{timestamp.replace('-', '').replace(':', '')}-{repo_sha[:12]}"


def select_subset(spec: Mapping[str, Any], corpus_dir: str) -> tuple[list[Fixture], dict[str, Any]]:
    """The subset's fixtures (sorted by case id) and the manifest identity recorded with the run."""
    corpus = lane_corpus(COMPREHENSIVE_LANE, corpus_dir)
    subset = spec["subset"]
    if subset.get("case_ids"):
        chosen = sorted(subset["case_ids"])
        missing = [c for c in chosen if c not in corpus.digests]
        if missing:
            raise RoutineExecutionError(f"fail-closed: subset case ids not in the comprehensive corpus: {missing}")
    else:
        ranked = sorted(corpus.digests, key=lambda c: hashlib.sha256(f"{subset['seed']}:{c}".encode()).hexdigest())
        chosen = sorted(ranked[: subset["size"]])
    entries = [{"case_id": c, "fixture_digest": corpus.digests[c]} for c in chosen]
    identity = hashlib.sha256(json.dumps(entries, sort_keys=True).encode()).hexdigest()
    manifest = {"corpus_id": corpus.corpus_id, "subset_id": identity, "method": subset["method"], "fixtures": entries}
    return [Fixture(c, corpus.case_dirs[c]) for c in chosen], manifest


def prior_experiment_refs(remote: str) -> list[str]:
    """Experiment ref names already on `remote` (read-only `ls-remote`); the stop condition's input."""
    try:
        proc = subprocess.run(
            ["git", "ls-remote", "--heads", remote, f"refs/heads/{EXPERIMENT_REF_PREFIX}*"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_S,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RoutineExecutionError(f"cannot list prior experiments on {remote}: {exc}") from exc
    if proc.returncode != 0:
        raise RoutineExecutionError(f"cannot list prior experiments on {remote}: {proc.stderr.strip()}")
    return [line.split()[1].removeprefix("refs/heads/") for line in proc.stdout.splitlines() if line.strip()]


def local_today(spec: Mapping[str, Any], now: datetime | None = None) -> str:
    zone = ZoneInfo(spec["intended_start"]["timezone"])
    return (now or datetime.now(zone)).astimezone(zone).strftime("%Y-%m-%d")


def skip_reason(spec: Mapping[str, Any], refs: list[str], local_date: str, utc_date: str) -> str | None:
    """Why a scheduled run must not execute; evaluated from the spec and the refs alone, so the Routine's state is irrelevant."""
    stop = spec["stop_condition"]
    end = stop.get("window_end")
    if end is not None and local_date > end:
        return "window-ended"
    if len(refs) >= stop["max_experiments"]:
        return "stop-condition-reached"
    if end is None or not stop.get("experiments"):
        return "not-activated"
    if local_date not in {e["date"] for e in stop["experiments"]}:
        return "not-an-experiment-day"
    if any(r.startswith(f"{EXPERIMENT_REF_PREFIX}{utc_date.replace('-', '')}") for r in refs):
        return "already-experimented-today"
    return None


def scheduled_arms(spec: Mapping[str, Any], local_date: str) -> list[int]:
    return next(e["arms"] for e in spec["stop_condition"]["experiments"] if e["date"] == local_date)


def parse_arms(text: str, allowed: list[int]) -> list[int]:
    try:
        arms = [int(part) for part in text.split(",")]
    except ValueError as exc:
        raise RoutineExecutionError(f"--arms must be a comma-separated list of worker counts, got {text!r}") from exc
    if not arms or any(a not in allowed for a in arms):
        raise RoutineExecutionError(f"--arms {text!r}: every arm must be one of {allowed}")
    return arms


def _digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def git_config_digests() -> dict[str, str | None]:
    return {"global": _digest(Path.home() / ".gitconfig"), "repository": _digest(REPO_ROOT / ".git" / "config")}


def cli_state_fingerprint() -> dict[str, Any]:
    """Entry count and newest mtime of the review CLI's top-level state directory; unavailable is recorded as such."""
    root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    try:
        entries = list(root.iterdir())
        return {"available": True, "entries": len(entries), "newest_mtime": max((e.stat().st_mtime for e in entries), default=None)}
    except OSError as exc:
        return {"available": False, "reason": type(exc).__name__}


def shared_temp_strays(before: set[str]) -> list[str]:
    """`benchmark-*` workspaces that appeared in the shared temp directory: a child that ignored its scratch directory."""
    return sorted(set(p.name for p in Path(tempfile.gettempdir()).glob("benchmark-*")) - before)


def isolation_audit(
    arms: list[ArmResult],
    fixtures: list[Fixture],
    *,
    repo_before: Any,
    repo_after: Any,
    config_before: dict,
    config_after: dict,
    strays: list[str],
    cli_before: dict,
    cli_after: dict,
) -> dict[str, Any]:
    violations: list[Violation] = [v for arm in arms for v in arm.violations]
    if repo_before != repo_after:
        violations.append(Violation("source-repo-mutated", "the protected checkout changed during the run"))
    if config_before != config_after:
        violations.append(Violation("git-config-mutated", "a git config file changed during the run"))
    if strays:
        violations.append(Violation("shared-temp-workspace", f"benchmark workspaces outside the scratch dirs: {strays[:5]}"))
    expected = sorted(f.case_id for f in fixtures)
    for arm in arms:
        done = sorted(o.case_id for o in arm.outcomes)
        if not arm.cancelled and done != expected:
            violations.append(Violation("coverage", f"arm {arm.workers} attempted {len(done)} of {len(expected)} fixtures, or one twice"))
    return {
        "violations": [v.as_dict() for v in violations],
        "passed": not violations,
        "shared_surfaces": SHARED_SURFACES,
        "cli_state": {"before": cli_before, "after": cli_after},
    }


def build_experiment(
    spec: Mapping[str, Any],
    arms: list[ArmResult],
    manifest: dict,
    audit: dict,
    *,
    status_hint: str | None,
    abort: dict[str, str] | None = None,
    trigger: str,
    runtime: Mapping[str, str],
    repo_sha: str,
    repo_ref: str,
    started_at: str,
    finished_at: str,
    planned_arms: list[int],
) -> dict[str, Any]:
    run_id = make_run_id(started_at, repo_sha)
    complete = status_hint is None and len(arms) == len(planned_arms) and all(a.complete for a in arms) and audit["passed"]
    classes = sorted(
        {c for a in arms for c in a.failure_classes()}
        | ({"isolation"} if not audit["passed"] else set())
        | ({"infrastructure"} if abort else set())
    )
    return {
        "schema": EXPERIMENT_SCHEMA,
        "temporary": True,
        "run_id": run_id,
        "ref": experiment_ref(run_id, trigger),
        "trigger": trigger,
        "status": "complete" if complete else (status_hint or "incomplete"),
        "failure_classes": classes,
        "abort": abort,
        "started_at": started_at,
        "finished_at": finished_at,
        "planned_arms": planned_arms,
        "runtime": {**runtime, "adapter_id": f"production-review-adapter@{repo_sha[:12]}"},
        "provenance": {"repo": spec["repository"], "repo_sha": repo_sha, "ref": repo_ref, "spec_issue": spec["issue"]},
        "manifest": manifest,
        "isolation": audit,
        "diagnostics": {
            "tokens": {"available": False, "reason": "run_benchmark.py does not surface the review CLI's token usage"},
            "rate_limit_evidence": "counted per fixture from what the child surfaces (its stderr lines and failure reason); the review CLI's own stderr is not surfaced, so zero is not proof of no throttling",
        },
        "arms": [a.evidence() for a in arms],
        "raw_file": RAW_FILE,
    }


def raw_evidence(arms: list[ArmResult]) -> dict[str, Any]:
    return {
        str(a.workers): {o.case_id: {"run": o.run, "stderr_tail": o.stderr_tail} for o in sorted(a.outcomes, key=lambda o: o.case_id)}
        for a in arms
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus-dir", default=str(rb.DEFAULT_CORPUS_DIR))
    parser.add_argument("--cli", default=None, help="Override the review CLI executable.")
    parser.add_argument("--timeout", type=float, default=300.0, help="Per-case review timeout in seconds.")
    parser.add_argument("--runtime-name", default=None)
    parser.add_argument("--runtime-version", default=None)
    parser.add_argument("--model-id", default="unknown", help="Model backend identifier; the Routine prompt sets it.")
    parser.add_argument("--trigger", choices=["scheduled", "manual", "api"], default="manual")
    parser.add_argument("--arms", default=None, help="Worker counts to run in order, e.g. 1,2; scheduled runs take them from the spec.")
    parser.add_argument("--spec", type=Path, default=SPEC_PATH)
    parser.add_argument("--seal-remote", default="origin", help="Git remote the evidence is pushed to.")
    parser.add_argument("--seal-dir", type=Path, default=None, help="Dry run: write the files here; push nothing.")
    return parser


def run(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    dry = args.seal_dir is not None
    arms_planned: list[int]
    if args.trigger == "scheduled" and not dry:
        if args.arms is not None:
            raise RoutineExecutionError("a scheduled run takes its arms from the spec; --arms is for trials and dry runs")
        refs = prior_experiment_refs(args.seal_remote)
        local, utc = local_today(spec), utc_now()[:10]
        reason = skip_reason(spec, refs, local, utc)
        if reason is not None:
            print(json.dumps({"skipped": reason, "experiments": len(refs), "action": "disable the Routine (see the spec's removal path)"}, indent=2))
            return 0
        arms_planned = scheduled_arms(spec, local)
    elif args.arms is None:
        raise RoutineExecutionError("--arms is required outside a scheduled run")
    else:
        arms_planned = parse_arms(args.arms, spec["allowed_workers"])
    fixtures, manifest = select_subset(spec, args.corpus_dir)
    executable = args.cli or resolve_cli_executable()
    runtime = {
        "runtime_name": args.runtime_name or executable,
        "runtime_version": args.runtime_version or runtime_version(executable),
        "model_id": args.model_id,
    }
    repo_sha, started_at = git_sha(REPO_ROOT), utc_now()
    progress = ProgressLog(stream=sys.stderr)
    scratch_root = Path(tempfile.mkdtemp(prefix="concurrency-experiment-"))
    temp_before = {p.name for p in Path(tempfile.gettempdir()).glob("benchmark-*")}
    repo_before, config_before, cli_before = capture_repo_state(REPO_ROOT), git_config_digests(), cli_state_fingerprint()
    arms: list[ArmResult] = []
    status_hint: str | None = None
    abort: dict[str, str] | None = None
    exit_code = 0
    cancel, children = threading.Event(), LiveChildren()
    try:
        with terminate_on_signal(lambda: (progress.phase_name, progress.current_case)):
            for count in arms_planned:
                progress.phase_name = f"arm-{count}"
                progress.log(f"[arm {count}] START {len(fixtures)} fixtures")
                arm = ArmResult(workers=count, planned=len(fixtures), wall_s=0.0)
                arms.append(arm)  # recorded before it runs, so an abort keeps what finished
                workers_mod.run_arm(
                    count, fixtures, executable=executable, timeout=args.timeout, scratch_root=scratch_root,
                    log=progress.log, cancel=cancel, children=children, result=arm,
                )
                progress.log(f"[arm {count}] {'DONE' if arm.complete else 'INCOMPLETE'} {arm.wall_s:.1f}s completed={arm.completed}/{arm.planned}")
    except Terminated as exc:
        progress.log(terminated_line(exc))
        if arms:
            arms[-1].cancelled = True  # the interrupted arm is partial, not a coverage failure
        status_hint, exit_code = "terminated", exc.exit_code
    except Exception as exc:  # noqa: BLE001 - an unexpected fault is infrastructure; the evidence so far is still sealed
        if arms:
            arms[-1].cancelled = True
        progress.log(f"[run] aborted: {type(exc).__name__}: {' '.join(str(exc).split())[:300]}")
        status_hint, abort = "aborted", {"error": type(exc).__name__, "message": " ".join(str(exc).split())[:500]}
    finally:
        children.stop_all()
        stray = shared_temp_strays(temp_before)
        shutil.rmtree(scratch_root, ignore_errors=True)
    audit = isolation_audit(
        arms, fixtures, repo_before=repo_before, repo_after=capture_repo_state(REPO_ROOT),
        config_before=config_before, config_after=git_config_digests(), strays=stray,
        cli_before=cli_before, cli_after=cli_state_fingerprint(),
    )
    experiment = build_experiment(
        spec, arms, manifest, audit, status_hint=status_hint, abort=abort, trigger=args.trigger, runtime=runtime,
        repo_sha=repo_sha, repo_ref=git_ref(), started_at=started_at, finished_at=utc_now(), planned_arms=arms_planned,
    )
    files = {RAW_FILE: seal.encode_json(raw_evidence(arms)), EXPERIMENT_FILE: seal.encode_json(experiment)}
    try:
        if dry:
            where = str(seal.seal_to_directory(args.seal_dir, files, EXPERIMENT_FILE))
        else:
            ref = confined_ref(experiment["ref"])
            commit = seal.seal_to_ref(REPO_ROOT, args.seal_remote, ref, files, f"concurrency experiment {experiment['run_id']}")
            where = f"{args.seal_remote}:{ref}@{commit}"
    except seal.SealError:
        print(json.dumps(experiment, indent=2))  # the partial evidence survives in the transcript when nothing could be pushed
        raise
    print(json.dumps({"run_id": experiment["run_id"], "handoff": where, "status": experiment["status"],
                      "failure_classes": experiment["failure_classes"], "isolation_passed": audit["passed"]}, indent=2))
    return exit_code or (0 if experiment["status"] == "complete" else 1)


def main(argv: list[str] | None = None) -> int:
    try:
        return run(build_arg_parser().parse_args(argv))
    except (RoutineExecutionError, seal.SealError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
