"""Flushed stderr progress, heartbeat, and child-timing helpers for benchmark runs (Issue #611).

Observability only: nothing here changes what runs, its order, its timeouts, or any stdout contract.
"""

from __future__ import annotations

import re
import sys
import threading
import time
from contextlib import contextmanager
from typing import Callable, Iterator, TextIO, TypeVar

T = TypeVar("T")

HEARTBEAT_INTERVAL_S = 60.0
CHILD_TIMING_PREFIX = "[child-timing]"
_TIMING_FIELDS = ("probe", "review", "total")
_TIMING_RE = re.compile(rf"^{re.escape(CHILD_TIMING_PREFIX)} (.*)$", re.M)


def format_clock(seconds: float) -> str:
    whole = int(seconds)
    return f"{whole // 60:02d}:{whole % 60:02d}"


def child_timing_line(probe_s: float, review_s: float, total_s: float) -> str:
    return f"{CHILD_TIMING_PREFIX} probe={probe_s:.1f}s review={review_s:.1f}s total={total_s:.1f}s"


def parse_child_timing(stderr: str) -> dict[str, float] | None:
    """The last child timing line as seconds, or None when the child emitted none."""
    matches = _TIMING_RE.findall(stderr or "")
    if not matches:
        return None
    pairs = dict(re.findall(r"(\w+)=([0-9.]+)s", matches[-1]))
    if not all(k in pairs for k in _TIMING_FIELDS):
        return None
    return {k: float(pairs[k]) for k in _TIMING_FIELDS}


def format_timing(timing: dict[str, float] | None) -> str:
    if timing is None:
        return ""
    other = max(timing["total"] - timing["probe"] - timing["review"], 0.0)
    return f" (probe={timing['probe']:.1f}s review={timing['review']:.1f}s other={other:.1f}s)"


class ProgressLog:
    """Timestamped progress lines on a stream, flushed immediately so a killed run keeps them."""

    def __init__(
        self,
        stream: TextIO | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        heartbeat_interval_s: float = HEARTBEAT_INTERVAL_S,
    ) -> None:
        self._stream = stream
        self._clock = clock
        self._interval = heartbeat_interval_s
        self._start = clock()
        self._lock = threading.Lock()
        self.completed = 0
        self.total: int | None = None
        self.phase_name = "init"

    def elapsed(self) -> float:
        return self._clock() - self._start

    def log(self, message: str) -> None:
        stream = self._stream if self._stream is not None else sys.stderr
        with self._lock:
            try:
                print(f"[+{format_clock(self.elapsed())}] {message}", file=stream, flush=True)
            except Exception:  # noqa: BLE001 - progress is diagnostics; a failed write must not fail the run (#659)
                pass

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        previous, self.phase_name = self.phase_name, name
        began = self._clock()
        self.log(f"[phase] {name} START")
        try:
            yield
        except BaseException:
            self.log(f"[phase] {name} FAILED after {self._clock() - began:.1f}s")
            raise
        else:
            self.log(f"[phase] {name} DONE {self._clock() - began:.1f}s")
        finally:
            self.phase_name = previous

    def item(self, tag: str, case_id: str, run: Callable[[], T], *, counted: bool = True) -> T:
        """Run one fixture invocation with START, heartbeat, and PASS/FAIL lines; re-raises failures."""
        began = self._clock()
        self.log(f"{tag} START {case_id}")
        stop = threading.Event()
        beat = threading.Thread(target=self._heartbeat, args=(stop, case_id, began), daemon=True)
        beat.start()
        try:
            result = run()
        except BaseException as exc:
            self.log(f"{tag} FAIL {case_id} {self._clock() - began:.1f}s reason={_one_line(exc)}")
            raise
        finally:
            stop.set()
            beat.join()
        if counted:
            self.completed += 1
        timing = getattr(result, "timing", None)
        self.log(f"{tag} PASS {case_id} {self._clock() - began:.1f}s{format_timing(timing)}")
        return result

    def _heartbeat(self, stop: threading.Event, case_id: str, began: float) -> None:
        while not stop.wait(self._interval):
            total = f"/{self.total}" if self.total is not None else ""
            self.log(
                f"[heartbeat] phase={self.phase_name} completed={self.completed}{total} current={case_id} "
                f"fixture_elapsed={int(self._clock() - began)}s total={format_clock(self.elapsed())}"
            )


def _one_line(exc: BaseException) -> str:
    return " ".join(str(exc).split()) or type(exc).__name__


class CaseLifecycle:
    """Per-case stage/terminal lines for one ``run_benchmark.py`` invocation (Issue #659).

    stderr diagnostics only. Lines carry the case id, ``i/n``, the stage and a bounded category;
    never model output, prompt text or child stderr bodies.
    """

    def __init__(self, log: ProgressLog, categorize: Callable[[BaseException], str]) -> None:
        self._log = log
        self._categorize = categorize
        self._began = 0.0
        self._tag = ""
        self._case = ""
        self._stage = "setup"
        self._category: str | None = None

    def observe(self, event: str, case_id: str, index: int, total: int, result: object) -> None:
        if event == "start":
            self._tag, self._case, self._stage, self._category = f"[case {index}/{total}]", case_id, "setup", None
            self._began = self._log._clock()
            self._log.log(f"{self._tag} START {case_id}")
            return
        took = f"{self._log._clock() - self._began:.1f}s"
        if getattr(result, "status", None) == "executed":
            count = len(getattr(result, "produced_findings", ()))
            self._log.log(f"{self._tag} DONE {case_id} {took} findings={count}")
        else:
            category = self._category or str(getattr(result, "error", None) or "unknown")
            self._log.log(f"{self._tag} ERROR {case_id} {took} stage={self._stage} category={category}")

    def stage(self, name: str) -> None:
        self._stage = name
        self._log.log(f"{self._tag} stage={name} START {self._case}")

    def adapter_failed(self, exc: BaseException) -> None:
        self._category = self._categorize(exc)
