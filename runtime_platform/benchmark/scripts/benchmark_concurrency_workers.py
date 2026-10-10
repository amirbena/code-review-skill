"""TEMPORARY bounded-parallel fixture execution and isolation audit (Issue #681).

Runs one `run_benchmark.py` child per fixture, exactly as the official lane does, but N at a time
from a thread pool that only waits on child processes. Each child keeps its own main thread, signal
handling, `ProgressLog` and workspace; nothing in the review path is shared in-process. Contract:
`runtime_platform/benchmark/concurrency-experiment.md`.
"""

from __future__ import annotations

import json
import os
import queue
import re
import resource
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.scripts.benchmark_progress import parse_child_timing  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_routine_verify import verify_benchmark_output  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_termination import PARENT_GRACE_S, stop_process_tree  # noqa: E402

RUN_BENCHMARK = REPO_ROOT / "runtime_platform" / "benchmark" / "scripts" / "run_benchmark.py"
CHILD_OVERHEAD_S = 120.0  # probe, metrics and interpreter start on top of the per-case review timeout
STDERR_TAIL_CHARS = 4000
SAMPLE_INTERVAL_S = 5.0
RATE_LIMIT_RE = re.compile(r"\b429\b|rate[ _-]?limit|overloaded|throttl|too many requests", re.I)
CATEGORY_RE = re.compile(r"category=([\w-]+)")
TEMP_ENV_VARS = ("TMPDIR", "TEMP", "TMP")

INFRASTRUCTURE = "infrastructure"
BENCHMARK = "benchmark"
ISOLATION = "isolation"


@dataclass
class FixtureOutcome:
    case_id: str
    worker: int
    started_s: float
    duration_s: float
    exit_code: int | None
    status: str  # "ok" | "failed"
    failure_class: str | None = None
    failure_reason: str | None = None
    timed_out: bool = False
    rate_limit_hits: int = 0
    adapter_category: str | None = None  # the child's own bounded failure category, e.g. timeout or cli-exit-1
    timing: dict[str, float] | None = None  # the child's probe/review/total split, None when it emitted none
    stderr_tail: str = ""
    run: dict[str, Any] | None = None

    def evidence(self) -> dict[str, Any]:
        """Everything but the raw run block and stderr, which are sealed separately."""
        return {
            "case_id": self.case_id,
            "worker": self.worker,
            "started_s": self.started_s,
            "duration_s": self.duration_s,
            "exit_code": self.exit_code,
            "status": self.status,
            "failure_class": self.failure_class,
            "failure_reason": self.failure_reason,
            "timed_out": self.timed_out,
            "rate_limit_hits": self.rate_limit_hits,
            "adapter_category": self.adapter_category,
            "probe_s": None if self.timing is None else self.timing["probe"],
            "review_s": None if self.timing is None else self.timing["review"],
        }


@dataclass
class Violation:
    kind: str
    detail: str
    worker: int | None = None
    case_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "detail": self.detail, "worker": self.worker, "case_id": self.case_id}


@dataclass
class Fixture:
    case_id: str
    corpus_dir: str


@dataclass
class ArmResult:
    workers: int
    planned: int
    wall_s: float
    outcomes: list[FixtureOutcome] = field(default_factory=list)
    violations: list[Violation] = field(default_factory=list)
    contention: dict[str, Any] = field(default_factory=dict)
    cancelled: bool = False

    @property
    def completed(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "ok")

    @property
    def complete(self) -> bool:
        return not self.cancelled and self.completed == self.planned and not self.violations

    def failure_classes(self) -> list[str]:
        classes = {o.failure_class for o in self.outcomes if o.failure_class}
        if self.violations:
            classes.add(ISOLATION)
        return sorted(classes)

    def evidence(self) -> dict[str, Any]:
        durations = sorted(o.duration_s for o in self.outcomes)
        return {
            "workers": self.workers,
            "planned": self.planned,
            "attempted": len(self.outcomes),
            "completed": self.completed,
            "errors": sum(1 for o in self.outcomes if o.status != "ok"),
            "timeouts": sum(1 for o in self.outcomes if o.timed_out or o.adapter_category == "timeout"),
            "rate_limit_hits": sum(o.rate_limit_hits for o in self.outcomes),
            "wall_s": self.wall_s,
            "fixture_seconds_sum": round(sum(durations), 3),
            "fixture_seconds_median": durations[len(durations) // 2] if durations else None,
            "fixture_seconds_max": durations[-1] if durations else None,
            "status": "complete" if self.complete else "incomplete",
            "failure_classes": self.failure_classes(),
            "violations": [v.as_dict() for v in self.violations],
            "contention": self.contention,
            "fixtures": [o.evidence() for o in sorted(self.outcomes, key=lambda o: o.case_id)],
        }


class LiveChildren:
    """The running children, so an abort can stop every process tree."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._procs: set[subprocess.Popen] = set()

    def add(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._procs.add(proc)

    def discard(self, proc: subprocess.Popen) -> None:
        with self._lock:
            self._procs.discard(proc)

    def stop_all(self) -> None:
        with self._lock:
            procs = list(self._procs)
        for proc in procs:
            stop_process_tree(proc, PARENT_GRACE_S)


def run_fixture_child(
    fixture: Fixture, *, worker: int, scratch: Path, executable: str, timeout: float, began: float, children: LiveChildren
) -> FixtureOutcome:
    """One verified `run_benchmark.py` invocation with its temp directory redirected to `scratch`."""
    argv = [sys.executable, str(RUN_BENCHMARK), "--corpus-dir", fixture.corpus_dir, "--cli", executable]
    argv += ["--timeout", str(timeout), "--case-id", fixture.case_id]
    env = {**os.environ, **{name: str(scratch) for name in TEMP_ENV_VARS}}
    started = time.monotonic()
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,  # own process group so a stop reaches the CLI's descendants
    )
    children.add(proc)
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout + CHILD_OVERHEAD_S)
    except subprocess.TimeoutExpired:
        timed_out = True
        stop_process_tree(proc, PARENT_GRACE_S)
        stdout, stderr = "", ""
    except BaseException:
        stop_process_tree(proc, PARENT_GRACE_S)
        raise
    finally:
        children.discard(proc)
    duration = round(time.monotonic() - started, 3)
    base = dict(
        case_id=fixture.case_id,
        worker=worker,
        started_s=round(started - began, 3),
        duration_s=duration,
        exit_code=None if timed_out else proc.returncode,
        timed_out=timed_out,
        rate_limit_hits=len(RATE_LIMIT_RE.findall(stderr)),
        adapter_category=(CATEGORY_RE.findall(stderr) or [None])[-1],
        timing=parse_child_timing(stderr),
        stderr_tail=" ".join(stderr.split())[-STDERR_TAIL_CHARS:],
    )
    if timed_out:
        return FixtureOutcome(
            **base, status="failed", failure_class=INFRASTRUCTURE, failure_reason="child exceeded its hard time limit"
        )
    verification = verify_benchmark_output(stdout, proc.returncode)
    run = _run_block(stdout)
    base["run"] = run
    if verification.passed:
        if verification.case_ids != (fixture.case_id,):
            return FixtureOutcome(
                **base, status="failed", failure_class=ISOLATION, failure_reason=f"child ran {list(verification.case_ids)}"
            )
        return FixtureOutcome(**base, status="ok")
    # A parsed run that did not execute the case is a benchmark outcome; anything else the infrastructure's.
    failure_class = BENCHMARK if run is not None and verification.case_count else INFRASTRUCTURE
    base["rate_limit_hits"] += len(RATE_LIMIT_RE.findall(verification.reason))
    return FixtureOutcome(**base, status="failed", failure_class=failure_class, failure_reason=verification.reason)


def _run_block(stdout: str) -> dict[str, Any] | None:
    try:
        data = json.loads(stdout)
    except (json.JSONDecodeError, TypeError):
        return None
    run = data.get("run") if isinstance(data, dict) else None
    return run if isinstance(run, dict) else None


class ResourceSampler:
    """Host load and child CPU while an arm runs; each reading is None where the platform lacks it."""

    def __init__(self, interval_s: float = SAMPLE_INTERVAL_S) -> None:
        self._interval = interval_s
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._peak_load: float | None = None
        self._cpu_before = self._children_cpu()

    @staticmethod
    def _children_cpu() -> float | None:
        try:
            usage = resource.getrusage(resource.RUSAGE_CHILDREN)
            return usage.ru_utime + usage.ru_stime
        except (OSError, ValueError):
            return None

    def _sample(self) -> None:
        try:
            load = os.getloadavg()[0]
        except (OSError, AttributeError):
            return
        self._peak_load = load if self._peak_load is None else max(self._peak_load, load)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._sample()
            self._stop.wait(self._interval)

    def __enter__(self) -> "ResourceSampler":
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join()
        self._sample()

    def summary(self) -> dict[str, Any]:
        after = self._children_cpu()
        cpu = None if after is None or self._cpu_before is None else round(after - self._cpu_before, 3)
        return {"peak_load_1m": self._peak_load, "children_cpu_s": cpu, "cpu_count": os.cpu_count()}


def run_arm(
    workers: int,
    fixtures: list[Fixture],
    *,
    executable: str,
    timeout: float,
    scratch_root: Path,
    log: Callable[[str], None],
    cancel: threading.Event,
    children: LiveChildren,
    result: ArmResult | None = None,
) -> ArmResult:
    """Run `fixtures` (in their given order) on `workers` slots; each slot owns one scratch directory.

    A caller that passes `result` keeps whatever finished even when this raises, so an abort never loses evidence.
    """
    slots: queue.Queue[int] = queue.Queue()
    for slot in range(workers):
        (scratch_root / f"w{workers}-{slot}").mkdir(parents=True, exist_ok=True)
        slots.put(slot)
    result = result if result is not None else ArmResult(workers=workers, planned=len(fixtures), wall_s=0.0)
    lock = threading.Lock()
    active: set[int] = set()
    began = time.monotonic()

    def task(fixture: Fixture) -> None:
        if cancel.is_set():
            result.cancelled = True
            return
        slot = slots.get()
        scratch = scratch_root / f"w{workers}-{slot}"
        with lock:
            if slot in active:  # a slot handed out twice would let two children share a workspace parent
                result.violations.append(Violation("slot-shared", f"slot {slot} held by two fixtures", slot, fixture.case_id))
            active.add(slot)
        try:
            log(f"[w{slot}] START {fixture.case_id}")
            try:
                outcome = run_fixture_child(
                    fixture, worker=slot, scratch=scratch, executable=executable, timeout=timeout, began=began, children=children
                )
            except BaseException:
                cancel.set()  # stop the other workers from starting fixtures the moment one faults
                raise
            leftovers = sorted(p.name for p in scratch.iterdir())
            with lock:
                result.outcomes.append(outcome)
                if leftovers:
                    result.violations.append(
                        Violation("workspace-not-cleaned", f"left in {scratch.name}: {leftovers[:5]}", slot, fixture.case_id)
                    )
            if outcome.failure_class == ISOLATION:
                with lock:
                    result.violations.append(Violation("coverage", outcome.failure_reason or "", slot, fixture.case_id))
            log(f"[w{slot}] {'DONE' if outcome.status == 'ok' else 'FAIL'} {fixture.case_id} {outcome.duration_s:.1f}s")
        finally:
            with lock:
                active.discard(slot)
            slots.put(slot)

    sampler = ResourceSampler()
    try:
        with sampler, ThreadPoolExecutor(max_workers=workers, thread_name_prefix="fixture") as pool:
            try:
                futures = [pool.submit(task, fixture) for fixture in fixtures]
                for future in futures:
                    future.result()
            except BaseException:
                cancel.set()  # no new fixture starts, queued ones are dropped, and the running children are stopped
                pool.shutdown(wait=False, cancel_futures=True)
                children.stop_all()
                raise
    finally:
        result.wall_s = round(time.monotonic() - began, 3)
        result.contention = sampler.summary()
    return result
