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
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.scripts import benchmark_seal as seal  # noqa: E402
from runtime_platform.benchmark.scripts import run_benchmark as rb  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_evidence_destination import (  # noqa: E402
    Destination,
    DestinationMisconfigured,
    StoreUnavailable,
    add_remote_argument,
    exit_for,
    resolve_destination,
)
from runtime_platform.benchmark.scripts.benchmark_schedule_manifest import MANIFEST_PATH, load_valid_manifest  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_lane_run import (  # noqa: E402
    RoutineExecutionError,
    git_ref,
    git_sha,
    invoke,
    runtime_version,
    utc_now,
)
from runtime_platform.benchmark.scripts.benchmark_review_adapter import resolve_cli_executable  # noqa: E402

SPEC_PATH = REPO_ROOT / "runtime_platform" / "benchmark" / "schedule" / "severity-observation-spec.json"
OBSERVATION_SCHEMA = "severity-observation/v1"
OBSERVATION_REF_PREFIX = "claude/severity-observation-"
TRIAL_REF_PREFIX = "claude/severity-trial-"  # not matched by the observation prefix: never counted
OBSERVATION_FILE = "severity-observation.json"
RAW_FILE = "raw-output.json"


def load_spec(path: Path = SPEC_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def observation_ref(run_id: str, trigger: str = "scheduled") -> str:
    """Only a scheduled run is an observation; anything else is a trial that is never counted."""
    return f"{OBSERVATION_REF_PREFIX if trigger == 'scheduled' else TRIAL_REF_PREFIX}{run_id}"


def make_run_id(timestamp: str, repo_sha: str) -> str:
    return f"{timestamp.replace('-', '').replace(':', '')}-{repo_sha[:12]}"


def _required_entry(case_id: str, corpus_dir: str) -> tuple[str, str]:
    """(key, severity) of the fixture's single required finding; the observation is undefined otherwise."""
    import yaml

    fixture = yaml.safe_load((Path(corpus_dir) / f"{case_id}.yaml").read_text(encoding="utf-8"))
    required = [f for f in fixture["expected"]["findings"] if f.get("match") == "required"]
    if len(required) != 1 or not isinstance(required[0]["severity"], str):
        raise RoutineExecutionError(f"fail-closed: {case_id} must have exactly one required finding with one severity")
    return required[0]["key"], required[0]["severity"]


def resolved_severity(case_id: str, output: Mapping[str, Any], corpus_dir: str) -> dict[str, Any]:
    """The severity the reviewer produced for the required finding.

    The result does not expose the pairing's produced severity directly: the severity row lists
    only *mismatches* (each with the produced severity), and `matched` also counts optional
    entries. So the required entry's own state is read from `metrics.missed_keys` and the
    mismatch row for its key. When neither applies the comparison was exact, and the contract
    (`severity-accuracy.md` §3: exact iff produced is in the permitted set) makes produced equal
    the required entry's single severity. That invariant is cross-checked against the raw
    produced findings, and the run fails closed if it does not hold.
    """
    key, expected = _required_entry(case_id, corpus_dir)
    by_id = {sec: {r["id"]: r for r in output[sec]["cases"]} for sec in ("metrics", "severity")}
    if case_id not in by_id["metrics"] or case_id not in by_id["severity"]:
        raise RoutineExecutionError(f"fail-closed: the run output has no metric or severity row for {case_id!r}")
    raw_case = next((c for c in output["run"]["cases"] if c["id"] == case_id), None)
    if raw_case is None:
        raise RoutineExecutionError(f"fail-closed: the run output has no raw case for {case_id!r}")
    raw_severities = {f["severity"] for f in raw_case.get("produced_findings", [])}
    mismatches = by_id["severity"][case_id]["mismatches"]
    if key in by_id["metrics"][case_id]["missed_keys"]:
        return {"severity": None, "state": "not-produced", "expected": expected, "mismatches": mismatches}
    mismatch = next((m for m in mismatches if m["key"] == key), None)
    if mismatch is not None:
        produced, state = mismatch["produced"], mismatch["direction"]
    else:
        produced, state = expected, "exact"
    if produced not in raw_severities:
        raise RoutineExecutionError(
            f"fail-closed: recorded severity {produced} is not among the raw produced findings {sorted(raw_severities)}"
        )
    return {"severity": produced, "state": state, "expected": expected, "mismatches": mismatches}


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
        "ref": observation_ref(run_id, trigger),
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


def prior_observation_refs(dest: Destination) -> list[str]:
    """Observation ref names already on the evidence store; the stop condition's input (a failed read is no run)."""
    return dest.list_refs(OBSERVATION_REF_PREFIX)


def resolve_evidence_destination(args: argparse.Namespace, spec: Mapping[str, Any]) -> Destination:
    """The proven, preflighted evidence destination for this run (shared contract, §4.3)."""
    manifest = load_valid_manifest(args.manifest)
    dest = resolve_destination(manifest, evidence_remote=args.evidence_remote, repo_root=REPO_ROOT, source_repository=spec["repository"])
    dest.preflight()
    return dest


def skip_reason(refs: list[str], target: int, today: str) -> str | None:
    """Why this scheduled run must not record: the target is reached, or tonight's observation exists."""
    if len(refs) >= target:
        return "stop-condition-reached"
    if any(r.startswith(f"{OBSERVATION_REF_PREFIX}{today}") for r in refs):
        return "already-observed-today"
    return None


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
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="Expected-run manifest holding the evidence block.")
    add_remote_argument(parser)
    parser.add_argument("--seal-dir", type=Path, default=None, help="Dry run: write the files here; push nothing.")
    return parser


def run(args: argparse.Namespace) -> int:
    spec = load_spec(args.spec)
    dest = resolve_evidence_destination(args, spec) if args.seal_dir is None else None  # before any model cost
    if dest is not None and args.trigger == "scheduled":
        refs = prior_observation_refs(dest)
        reason = skip_reason(refs, spec["stop_condition"]["target_observations"], utc_now()[:10].replace("-", ""))
        if reason is not None:
            note = "disable the Routine (see the spec's removal path)" if reason == "stop-condition-reached" else "one observation per day"
            print(json.dumps({"skipped": reason, "observations": len(refs), "action": note}, indent=2))
            return 0
    executable = args.cli or resolve_cli_executable()
    runtime = {
        "runtime_name": args.runtime_name or executable,
        "runtime_version": args.runtime_version or runtime_version(executable),
        "model_id": args.model_id,
    }
    repo_sha, started_at = git_sha(REPO_ROOT), utc_now()
    inv = invoke(executable, args.timeout, spec["case_id"], args.corpus_dir)
    observation = build_observation(
        spec,
        inv.output,
        corpus_dir=args.corpus_dir,
        trigger=args.trigger,
        runtime=runtime,
        repo_sha=repo_sha,
        repo_ref=git_ref(),
        started_at=started_at,
        finished_at=utc_now(),
        duration_s=inv.duration_s,
    )
    files = {RAW_FILE: seal.encode_json(inv.output["run"]), OBSERVATION_FILE: seal.encode_json(observation)}
    if args.seal_dir is not None:
        where = str(seal.seal_to_directory(args.seal_dir, files, OBSERVATION_FILE))
    else:
        ref, run_id = observation["ref"], observation["run_id"]
        assert dest is not None
        try:
            where = dest.location(ref, dest.seal(ref, files, f"severity observation {run_id}"))
        except StoreUnavailable as exc:
            return exit_for(exc, run_id=run_id, destination=dest, files=files, commit_file=OBSERVATION_FILE)
    print(json.dumps({"run_id": observation["run_id"], "handoff": where, "resolved": observation["resolved"]}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(build_arg_parser().parse_args(argv))
    except (DestinationMisconfigured, StoreUnavailable) as exc:
        return exit_for(exc)
    except (RoutineExecutionError, seal.SealError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
