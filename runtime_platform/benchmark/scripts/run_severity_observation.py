#!/usr/bin/env python3
"""TEMPORARY entrypoint: one nightly severity observation of one benchmark case (Issue #652).

Runs `correctness-off-by-one-pagination` once through the normal production-adapter path
(`run_benchmark.py`, unmodified fixture and prompt) and seals one observation to a
`claude/severity-observation-*` ref, outside every namespace the lane machinery reads. It has no
lane, no baseline, no drift evaluation and no GitHub issue or comment write. Spec, evidence
format, stop condition and removal path: `runtime_platform/benchmark/severity-observation.md`.

Usage::

    python3 runtime_platform/benchmark/scripts/run_severity_observation.py \\
        --trigger scheduled --model-id <the model backend this Routine session runs as>
    python3 runtime_platform/benchmark/scripts/run_severity_observation.py \\
        --seal-dir /tmp/observation          # local dry run: nothing is pushed
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.scripts import benchmark_seal as seal  # noqa: E402
from runtime_platform.benchmark.scripts import run_benchmark as rb  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_lane_run import (  # noqa: E402
    RoutineExecutionError,
    invoke,
    utc_now,
)
from runtime_platform.benchmark.scripts.benchmark_review_adapter import resolve_cli_executable  # noqa: E402
from runtime_platform.benchmark.scripts.run_benchmark_routine import _git_ref, _git_sha, _runtime_version  # noqa: E402

SPEC_PATH = REPO_ROOT / "runtime_platform" / "benchmark" / "schedule" / "severity-observation-spec.json"
OBSERVATION_SCHEMA = "severity-observation/v1"
OBSERVATION_REF_PREFIX = "claude/severity-observation-"
OBSERVATION_FILE = "severity-observation.json"
RAW_FILE = "raw-output.json"
GIT_TIMEOUT_S = 60


def load_spec(path: Path = SPEC_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def observation_ref(run_id: str) -> str:
    return f"{OBSERVATION_REF_PREFIX}{run_id}"


def make_run_id(timestamp: str, repo_sha: str) -> str:
    return f"{timestamp.replace('-', '').replace(':', '')}-{repo_sha[:12]}"


def resolved_severity(case_id: str, output: Mapping[str, Any], corpus_dir: str) -> dict[str, Any]:
    """The severity the reviewer gave the required finding, from the verified run output.

    `matched == 0` means the finding was not produced (`severity` is null). A mismatch row carries
    the produced severity; an exact match carries the fixture's single permitted severity.
    """
    import yaml

    rows = {r["id"]: r for r in output["severity"]["cases"]}
    if case_id not in rows:
        raise RoutineExecutionError(f"fail-closed: the run output has no severity row for {case_id!r}")
    row = rows[case_id]
    if row["matched"] == 0:
        return {"severity": None, "state": "not-produced", "mismatches": row["mismatches"]}
    if row["mismatches"]:
        return {"severity": row["mismatches"][0]["produced"], "state": "mismatch", "mismatches": row["mismatches"]}
    fixture = yaml.safe_load((Path(corpus_dir) / f"{case_id}.yaml").read_text(encoding="utf-8"))
    permitted = [f["severity"] for f in fixture["expected"]["findings"] if f.get("match") == "required"]
    severity = permitted[0] if len(permitted) == 1 and isinstance(permitted[0], str) else None
    return {"severity": severity, "state": "exact", "mismatches": []}


def build_observation(
    spec: Mapping[str, Any],
    output: Mapping[str, Any],
    *,
    corpus_dir: str,
    trigger: str,
    runtime: Mapping[str, str],
    repo_sha: str,
    repo_ref: str,
    started_at: str,
    finished_at: str,
    duration_s: float,
) -> dict[str, Any]:
    case_id = spec["case_id"]
    run_id = make_run_id(started_at, repo_sha)
    per_case = {
        section: next((r for r in output[section]["cases"] if r["id"] == case_id), None)
        for section in ("metrics", "severity", "duplicate_noise")
    }
    return {
        "schema": OBSERVATION_SCHEMA,
        "temporary": True,
        "run_id": run_id,
        "ref": observation_ref(run_id),
        "case_id": case_id,
        "trigger": trigger,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_s": duration_s,
        "resolved": resolved_severity(case_id, output, corpus_dir),
        "runtime": {**runtime, "adapter_id": f"production-review-adapter@{repo_sha[:12]}"},
        "provenance": {"repo": spec["repository"], "repo_sha": repo_sha, "ref": repo_ref},
        "evidence": per_case,
        "raw_file": RAW_FILE,
    }


def prior_observation_count(remote: str) -> int:
    """Observation refs already on `remote` (read-only `ls-remote`); the stop condition's input."""
    proc = subprocess.run(
        ["git", "ls-remote", "--heads", remote, f"refs/heads/{OBSERVATION_REF_PREFIX}*"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_S,
    )
    if proc.returncode != 0:
        raise RoutineExecutionError(f"cannot count prior observations on {remote}: {proc.stderr.strip()}")
    return len([line for line in proc.stdout.splitlines() if line.strip()])


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus-dir", default=str(rb.DEFAULT_CORPUS_DIR))
    parser.add_argument("--cli", default=None, help="Override the review CLI executable.")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument("--runtime-name", default=None)
    parser.add_argument("--runtime-version", default=None)
    parser.add_argument("--model-id", default="unknown", help="Model backend identifier; the Routine prompt sets it.")
    parser.add_argument("--trigger", choices=["scheduled", "manual", "api"], default="manual")
    parser.add_argument("--spec", type=Path, default=SPEC_PATH)
    parser.add_argument("--seal-remote", default="origin", help="Git remote the observation is pushed to.")
    parser.add_argument("--seal-dir", type=Path, default=None, help="Dry run: write the files here; push nothing.")
    return parser


def run(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    if args.seal_dir is None:
        done = prior_observation_count(args.seal_remote)
        if done >= spec["stop_condition"]["target_observations"]:
            print(json.dumps({"stopped": True, "observations": done, "action": "disable the Routine (see the spec's removal path)"}, indent=2))
            return 0
    executable = args.cli or resolve_cli_executable()
    runtime = {
        "runtime_name": args.runtime_name or executable,
        "runtime_version": args.runtime_version or _runtime_version(executable),
        "model_id": args.model_id,
    }
    repo_sha, started_at = _git_sha(REPO_ROOT), utc_now()
    inv = invoke(executable, args.timeout, spec["case_id"], args.corpus_dir)
    observation = build_observation(
        spec,
        inv.output,
        corpus_dir=args.corpus_dir,
        trigger=args.trigger,
        runtime=runtime,
        repo_sha=repo_sha,
        repo_ref=_git_ref(),
        started_at=started_at,
        finished_at=utc_now(),
        duration_s=inv.duration_s,
    )
    files = {RAW_FILE: seal.encode_json(inv.output["run"]), OBSERVATION_FILE: seal.encode_json(observation)}
    if args.seal_dir is not None:
        where = str(seal.seal_to_directory(args.seal_dir, files, OBSERVATION_FILE))
    else:
        ref, run_id = observation["ref"], observation["run_id"]
        commit = seal.seal_to_ref(REPO_ROOT, args.seal_remote, ref, files, f"severity observation {run_id}")
        where = f"{args.seal_remote}:{ref}@{commit}"
    print(json.dumps({"run_id": observation["run_id"], "handoff": where, "resolved": observation["resolved"]}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(build_arg_parser().parse_args(argv))
    except (RoutineExecutionError, seal.SealError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
