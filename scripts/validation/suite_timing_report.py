#!/usr/bin/env python3
"""Record per-test wall-clock durations of the repository test suite.

Runs the same discovery CI uses (`unittest discover -s tests -t .`) and writes
every test's duration, so timing claims about CI cost can cite measured data.
A single run is one sample; use --runs to expose run-to-run variance.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import sys
import time
import unittest
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCHEMA = "test-timing/v1"


class TimingResult(unittest.TestResult):
    """Collects duration and outcome per test; fixtures outside a test are not attributed."""

    def __init__(self) -> None:
        super().__init__()
        self.seconds: dict[str, float] = {}
        self.outcome: dict[str, str] = {}
        self.detail: dict[str, str] = {}
        self._started: dict[str, float] = {}

    def startTest(self, test: unittest.TestCase) -> None:
        super().startTest(test)
        self._started[test.id()] = time.perf_counter()

    def stopTest(self, test: unittest.TestCase) -> None:
        super().stopTest(test)
        test_id = test.id()
        self.seconds[test_id] = time.perf_counter() - self._started.pop(test_id)
        self.outcome.setdefault(test_id, "ok")

    def addFailure(self, test, err) -> None:  # noqa: N802
        super().addFailure(test, err)
        self.outcome[test.id()] = "fail"
        self.detail[test.id()] = self._last_line(self.failures[-1][1])

    def addError(self, test, err) -> None:  # noqa: N802
        super().addError(test, err)
        self.outcome[test.id()] = "error"
        self.detail[test.id()] = self._last_line(self.errors[-1][1])

    @staticmethod
    def _last_line(traceback_text: str) -> str:
        lines = [line for line in traceback_text.strip().splitlines() if line.strip()]
        return lines[-1][:300] if lines else ""

    def addSkip(self, test, reason) -> None:  # noqa: N802
        super().addSkip(test, reason)
        self.outcome[test.id()] = "skip"


def flatten(suite: unittest.TestSuite) -> Iterable[unittest.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def run_once(repo: Path, start_dir: str) -> dict:
    os.chdir(repo)
    started = time.perf_counter()
    suite = unittest.defaultTestLoader.discover(start_dir, top_level_dir=str(repo))
    discovery = time.perf_counter() - started
    result = TimingResult()
    wall_started = time.perf_counter()
    suite.run(result)
    wall = time.perf_counter() - wall_started
    return {
        "discovery_seconds": discovery,
        "wall_seconds": wall,
        "seconds": result.seconds,
        "outcome": result.outcome,
        "detail": result.detail,
    }


def collect(repo: Path, runs: int, start_dir: str = "tests") -> dict:
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    samples = [run_once(repo, start_dir) for _ in range(runs)]
    ids = sorted(samples[0]["seconds"])
    return {
        "schema": SCHEMA,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
        },
        "runs": runs,
        "discovery_seconds": [round(s["discovery_seconds"], 3) for s in samples],
        "wall_seconds": [round(s["wall_seconds"], 3) for s in samples],
        "tests": {
            tid: {
                "seconds": [round(s["seconds"].get(tid, 0.0), 4) for s in samples],
                "outcome": samples[0]["outcome"].get(tid, "ok"),
                **({"detail": samples[0]["detail"][tid]} if tid in samples[0]["detail"] else {}),
            }
            for tid in ids
        },
    }


def median_seconds(entry: Mapping) -> float:
    return statistics.median(entry["seconds"])


def group_key(test_id: str, depth: int) -> str:
    return ".".join(test_id.split(".")[:depth])


def module_of(test_id: str) -> str:
    return ".".join(test_id.split(".")[:-2])


def fast_dropped(test_id: str) -> bool | None:
    """Whether the CI router's FAST tier omits this test; None if the router cannot be imported."""
    try:
        from scripts.validation.ci_test_route import is_fast_dropped
    except ImportError:
        return None
    return is_fast_dropped(test_id)


def sum_by(tests: Mapping[str, Mapping], key) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for tid, entry in tests.items():
        totals[key(tid)] += median_seconds(entry)
    return dict(totals)


def top(totals: Mapping[str, float], n: int) -> list[tuple[str, float]]:
    return sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))[:n]


def render_markdown(data: Mapping, top_n: int = 15) -> str:
    tests = data["tests"]
    per_test = {tid: median_seconds(e) for tid, e in tests.items()}
    total = sum(per_test.values())
    dropped = {tid: fast_dropped(tid) for tid in tests}
    have_fast = all(v is not None for v in dropped.values())
    fast_total = sum(s for tid, s in per_test.items() if not dropped[tid]) if have_fast else None
    outcomes = defaultdict(int)
    for e in tests.values():
        outcomes[e["outcome"]] += 1
    wall = statistics.median(data["wall_seconds"])
    env = data["environment"]
    out = [
        f"Python {env['python']} on {env['platform']} ({env['cpu_count']} CPUs); "
        f"{data['runs']} run(s); per-test figures are the median over runs.",
        "",
        "| Measure | Seconds |",
        "| --- | ---: |",
        f"| Tests discovered | {len(tests):,} |",
        f"| Sum of per-test durations | {total:,.1f} |",
        f"| Suite wall time (median of runs) | {wall:,.1f} |",
        f"| Wall time not attributed to any test (fixtures, imports) | {max(wall - total, 0):,.1f} |",
        f"| Discovery time (median of runs) | {statistics.median(data['discovery_seconds']):,.1f} |",
    ]
    if fast_total is not None:
        out.append(f"| Sum of per-test durations the FAST tier still runs | {fast_total:,.1f} |")
    out.append(f"| Outcomes | {', '.join(f'{k} {v}' for k, v in sorted(outcomes.items()))} |")
    if data["runs"] > 1:
        out.append(f"| Wall time per run | {', '.join(f'{w:,.1f}' for w in data['wall_seconds'])} |")

    def table(title: str, rows: Sequence[tuple[str, float]], count: Mapping[str, int] | None = None) -> None:
        out.extend(["", title, "", "| Name | Seconds | Share |" if count is None else "| Name | Tests | Seconds | Share |"])
        out.append("| --- | ---: | ---: |" if count is None else "| --- | ---: | ---: | ---: |")
        for name, secs in rows:
            share = f"{100 * secs / total:.1f}%" if total else "-"
            if count is None:
                out.append(f"| `{name}` | {secs:,.2f} | {share} |")
            else:
                out.append(f"| `{name}` | {count[name]:,} | {secs:,.1f} | {share} |")

    for depth, label in ((2, "By tier directory"), (3, f"Largest areas (top {top_n})")):
        sums = sum_by(tests, lambda tid, d=depth: group_key(tid, d))
        counts: dict[str, int] = defaultdict(int)
        for tid in tests:
            counts[group_key(tid, depth)] += 1
        table(f"**{label}**", top(sums, top_n if depth == 3 else len(sums)), counts)
    table(f"**Slowest modules (top {top_n})**", top(sum_by(tests, module_of), top_n))
    table(f"**Slowest tests (top {top_n})**", top(per_test, top_n))
    out.append("")
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=1, help="repeat the suite N times (default 1)")
    parser.add_argument("--start-dir", default="tests", help="discovery directory relative to the repo (default tests)")
    parser.add_argument("--out", type=Path, help="write the raw timing JSON here")
    parser.add_argument("--from-json", type=Path, help="render a summary from stored JSON instead of running")
    parser.add_argument("--top", type=int, default=15, help="rows in the slowest-N tables")
    args = parser.parse_args(argv)
    if args.from_json:
        print(render_markdown(json.loads(args.from_json.read_text(encoding="utf-8")), args.top))
        return 0
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    data = collect(REPO_ROOT, args.runs, args.start_dir)
    if args.out:
        args.out.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(render_markdown(data, args.top))
    return 0 if all(e["outcome"] in ("ok", "skip") for e in data["tests"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
