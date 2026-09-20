#!/usr/bin/env python3
"""Executes one scheduled lane and assembles its sealed result (no hand-off, no GitHub).

Contract: `docs/benchmark/cloud-routine-integration.md` §2-§3. Order: verify every invocation,
evaluate drift with in-run confirmation, assemble and validate the record.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.scripts import benchmark_result as res  # noqa: E402
from runtime_platform.benchmark.scripts import benchmark_seal as seal  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_baseline import HistorySource, load_baseline  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_corpus_membership import (  # noqa: E402
    SENTINEL_LANE,
    discover_comprehensive_fixtures,
)
from runtime_platform.benchmark.scripts.benchmark_drift_evaluation import (  # noqa: E402
    ConfirmationPolicy,
    evaluate_drift,
)
from runtime_platform.benchmark.scripts.benchmark_history import corpus_digest_for_lane  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_routine_verify import verify_benchmark_output  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_run_record import (  # noqa: E402
    RecordAssemblyError,
    build_body,
    cases_from_output,
)

ROUTINE_DOC = REPO_ROOT / "docs" / "benchmark" / "cloud-routine-integration.md"
RUN_BENCHMARK = REPO_ROOT / "runtime_platform" / "benchmark" / "scripts" / "run_benchmark.py"
NONDETERMINISM = "Model output is nondeterministic; a rerun may differ."
PROMPT_SECTION = "## 9. Routine prompt template"


class RoutineExecutionError(RuntimeError):
    """A Routine-level failure: never sealed, never passing evidence."""


@dataclass(frozen=True)
class LaneCorpus:
    """A sealed lane's membership: where each case lives and its fixture digest."""

    case_dirs: dict[str, str]
    digests: dict[str, str]
    corpus_id: str


@dataclass(frozen=True)
class Invocation:
    verification: dict
    output: dict
    duration_s: float


@dataclass(frozen=True)
class LaneRun:
    """Everything fixed at the start of a lane run."""

    lane: str
    mode: str
    trigger: str
    executable: str
    timeout: float
    runtime: dict[str, str]
    repo_sha: str
    repo_ref: str
    started_at: str
    started_mono: float
    confirmation_budget_s: float | None = None


@dataclass(frozen=True)
class SealedRun:
    run_id: str
    ref: str
    record: dict[str, Any]
    files: dict[str, bytes]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def invoke(executable: str, timeout: float, case_id: str | None, corpus_dir: str) -> Invocation:
    """One `run_benchmark.py` invocation, positively verified; anything else raises."""
    argv = ["--corpus-dir", corpus_dir, "--cli", executable, "--timeout", str(timeout)]
    if case_id is not None:
        argv += ["--case-id", case_id]
    started = time.monotonic()
    proc = subprocess.run([sys.executable, str(RUN_BENCHMARK), *argv], capture_output=True, text=True)
    duration = round(time.monotonic() - started, 3)
    verification = verify_benchmark_output(proc.stdout, proc.returncode)
    if not verification.passed:
        raise RoutineExecutionError(
            f"fail-closed: an invocation did not pass positive completion verification: {verification.reason}"
        )
    return Invocation(verification.as_dict(), json.loads(proc.stdout), duration)


def _yaml_case_paths(corpus_dir: Path) -> dict[str, Path]:
    import yaml

    return {yaml.safe_load(p.read_text(encoding="utf-8"))["id"]: p for p in sorted(corpus_dir.glob("*.yaml"))}


def lane_corpus(lane: str, corpus_dir: str) -> LaneCorpus:
    root = Path(corpus_dir)
    if lane == SENTINEL_LANE:
        located = {cid: (str(root), path) for cid, path in _yaml_case_paths(root).items()}
    else:
        located = {fx.case_id: (str(fx.corpus_dir), fx.fixture_path) for fx in discover_comprehensive_fixtures(root)}
    if not located:
        raise RoutineExecutionError(f"--mode {lane} found no benchmark-case fixtures under {corpus_dir}")
    return LaneCorpus(
        case_dirs={cid: where for cid, (where, _) in located.items()},
        digests={cid: res.fixture_digest(path) for cid, (_, path) in located.items()},
        corpus_id=corpus_digest_for_lane(lane, root),
    )


def _excerpt(case_run: Mapping[str, Any]) -> str:
    data = json.dumps(case_run, indent=2, sort_keys=True).encode("utf-8")
    return data[: res.EVIDENCE_MAX_BYTES].decode("utf-8", errors="ignore")


def _prompt_template() -> str:
    """The literal Routine prompt template block of `cloud-routine-integration.md` §9."""
    text = ROUTINE_DOC.read_text(encoding="utf-8")
    section = text.split(PROMPT_SECTION, 1)[1].split("### 9.1", 1)[0] if PROMPT_SECTION in text else ""
    match = re.search(r"```text\n(.*?)```", section, re.S)
    if match is None:
        raise RoutineExecutionError(f"{ROUTINE_DOC.name} has no prompt template block under {PROMPT_SECTION!r}")
    return match.group(1)


def _spec_sha256(manifest: Mapping[str, Any]) -> str:
    """Digest of the prompt template and the manifest only, so unrelated doc edits do not change it."""
    template = hashlib.sha256(_prompt_template().encode("utf-8")).hexdigest()
    return res.sha256_hex(res.canonical_json({"manifest": manifest, "prompt_template_sha256": template}))


def build_sealed_run(
    run: LaneRun,
    corpus: LaneCorpus,
    invocations: list[Invocation],
    raw_invocations: list[dict],
    manifest: Mapping[str, Any],
    history: HistorySource,
    *,
    now: Callable[[], str] = utc_now,
) -> SealedRun:
    """Evaluate drift (re-running drifting cases to confirm them) and build the sealed record."""
    if run.lane not in manifest["lanes"]:
        raise RoutineExecutionError(f"lane {run.lane!r} is not in the expected-run manifest")
    try:
        cases = [c for inv in invocations for c in cases_from_output(inv.output, corpus.digests, inv.duration_s)]
    except RecordAssemblyError as exc:
        raise RoutineExecutionError(f"fail-closed: {exc}") from exc
    if sorted(c["id"] for c in cases) != sorted(corpus.digests):
        raise RoutineExecutionError("fail-closed: the run did not cover exactly the lane's membership")

    confirmation_raw: list[dict] = []

    def observe(case_id: str) -> Mapping[str, Any]:
        inv = invoke(run.executable, run.timeout, case_id, corpus.case_dirs[case_id])
        confirmation_raw.append({"case_id": case_id, "run": inv.output["run"]})
        return cases_from_output(inv.output, corpus.digests, inv.duration_s)[0]

    deadline = None if run.confirmation_budget_s is None else run.started_mono + run.confirmation_budget_s
    evaluation = evaluate_drift(
        cases,
        load_baseline(history, run.lane),
        ConfirmationPolicy(**manifest["confirmation"]),
        run.runtime,
        observe,
        deadline=deadline,
    )
    raw_by_case = {c["id"]: c for inv in invocations for c in inv.output["run"]["cases"]}
    drift = {
        **evaluation.drift,
        "evidence": {r["case_id"]: _excerpt(raw_by_case[r["case_id"]]) for r in evaluation.drift["confirmed"]},
    }

    run_id = res.make_run_id(run.lane, run.started_at, run.repo_sha)
    ref = seal.staging_ref(run_id)
    raw_bundle = seal.encode_json({"invocations": raw_invocations, "confirmation_reruns": confirmation_raw})
    body = build_body(
        lane=run.lane,
        mode=run.mode,
        trigger=run.trigger,
        started_at=run.started_at,
        finished_at=now(),
        sealed_at=now(),
        corpus_id=corpus.corpus_id,
        cases=cases,
        provenance={
            "repo": manifest["repository"],
            "repo_sha": run.repo_sha,
            "ref": run.repo_ref,
            "entrypoint_version": f"run_benchmark_routine.py@{run.repo_sha[:12]}",
            "spec_sha256": _spec_sha256(manifest),
        },
        runtime={**run.runtime, "adapter_id": f"production-review-adapter@{run.repo_sha[:12]}"},
        verification={"overall_verified": True, "runs": [i.verification for i in invocations]},
        baseline=evaluation.baseline,
        drift=drift,
        execution={
            "duration_s": round(time.monotonic() - run.started_mono, 3),
            "confirmation_reruns": evaluation.reruns_performed,
            "session_ref": None,
            "warnings": ["--mode full is a deprecated synonym for sentinel"] if run.mode == "full" else [],
        },
        reproduction={
            "command": f"python3 runtime_platform/benchmark/scripts/run_benchmark_routine.py --mode {run.mode}",
            "case_ids": sorted(corpus.digests),
            "python_version": platform.python_version(),
            "nondeterminism": NONDETERMINISM,
        },
        raw_bundle_sha256=hashlib.sha256(raw_bundle).hexdigest(),
        raw_location=f"{ref}:{seal.RAW_FILE}",
    )
    record = res.seal_record(body)
    errors = res.validate_record(record)
    if errors:
        raise RoutineExecutionError(f"fail-closed: the record does not conform to benchmark-result/v1: {errors[0]}")
    files = {seal.RAW_FILE: raw_bundle, seal.RECORD_FILE: seal.encode_json(record)}
    return SealedRun(run_id, ref, record, files)
