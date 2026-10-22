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
import shutil
import subprocess
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


OUTCOME_RANK = {"ok": 0, "skip": 1, "fail": 2, "error": 3}


class TimingResult(unittest.TestResult):
    """Collects duration and outcome per test; class/module fixture outcomes are kept apart from tests."""

    def __init__(self) -> None:
        super().__init__()
        self.seconds: dict[str, float] = {}
        self.outcome: dict[str, str] = {}
        self.detail: dict[str, str] = {}
        self.fixtures: dict[str, dict] = {}
        self._started: dict[str, float] = {}

    def startTest(self, test: unittest.TestCase) -> None:
        super().startTest(test)
        self._started[test.id()] = time.perf_counter()

    def stopTest(self, test: unittest.TestCase) -> None:
        super().stopTest(test)
        test_id = test.id()
        self.seconds[test_id] = time.perf_counter() - self._started.pop(test_id)
        self.outcome.setdefault(test_id, "ok")

    def _record(self, test, outcome: str, detail: str = "") -> None:
        """Keep the worst outcome per test; a holder that never started is a fixture, recorded apart from tests."""
        test_id = test.id()
        if test_id in self._started:
            if OUTCOME_RANK[outcome] > OUTCOME_RANK[self.outcome.get(test_id, "ok")]:
                self.outcome[test_id] = outcome
                self.detail[test_id] = detail
            return
        if OUTCOME_RANK[outcome] > OUTCOME_RANK[self.fixtures.get(test_id, {"outcome": "ok"})["outcome"]]:
            self.fixtures[test_id] = {"outcome": outcome, **({"detail": detail} if detail else {})}

    def addFailure(self, test, err) -> None:  # noqa: N802
        super().addFailure(test, err)
        self._record(test, "fail", self._last_line(self.failures[-1][1]))

    def addError(self, test, err) -> None:  # noqa: N802
        super().addError(test, err)
        self._record(test, "error", self._last_line(self.errors[-1][1]))

    def addSubTest(self, test, subtest, err) -> None:  # noqa: N802
        super().addSubTest(test, subtest, err)
        if err is not None:
            failed = issubclass(err[0], test.failureException)
            entry = self.failures[-1] if failed else self.errors[-1]
            self._record(test, "fail" if failed else "error", self._last_line(entry[1]))

    def addUnexpectedSuccess(self, test) -> None:  # noqa: N802
        super().addUnexpectedSuccess(test)
        self._record(test, "fail", "unexpected success")

    @staticmethod
    def _last_line(traceback_text: str) -> str:
        lines = [line for line in traceback_text.strip().splitlines() if line.strip()]
        return lines[-1][:300] if lines else ""

    def addSkip(self, test, reason) -> None:  # noqa: N802
        super().addSkip(test, reason)
        self._record(test, "skip")


def flatten(suite: unittest.TestSuite) -> Iterable[unittest.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


PROVENANCE_ENV = {
    "head_sha": "CI_HEAD_SHA",
    "merge_sha": "GITHUB_SHA",
    "base_sha": "CI_BASE_SHA",
    "run_id": "GITHUB_RUN_ID",
    "run_attempt": "GITHUB_RUN_ATTEMPT",
    "runner_image_version": "ImageVersion",
    "runner_os": "RUNNER_OS",
    "tier": "CI_TIER",
    "distribution_install_check": "DISTRIBUTION_INSTALL_CHECK",
}


def provenance(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Additive CI provenance read from the environment; unset values are omitted."""
    found = {key: os.environ[var] for key, var in PROVENANCE_ENV.items() if os.environ.get(var)}
    found.update({k: v for k, v in (extra or {}).items() if v})
    return dict(sorted(found.items()))


def cpu_seconds() -> float:
    """User plus system CPU of this process and its waited-for children."""
    t = os.times()
    return t.user + t.system + t.children_user + t.children_system


def run_once(repo: Path, start_dir: str) -> dict:
    os.chdir(repo)
    cpu_started = cpu_seconds()
    started = time.perf_counter()
    suite = unittest.defaultTestLoader.discover(start_dir, top_level_dir=str(repo))
    discovery = time.perf_counter() - started
    result = TimingResult()
    wall_started = time.perf_counter()
    suite.run(result)
    wall = time.perf_counter() - wall_started
    return {
        "cpu_seconds": cpu_seconds() - cpu_started,
        "counts": {
            "ran": result.testsRun,
            "skipped": len(result.skipped),
            "failed": len(result.failures) + len(result.unexpectedSuccesses),
            "errored": len(result.errors),
        },
        "discovery_seconds": discovery,
        "wall_seconds": wall,
        "seconds": result.seconds,
        "outcome": result.outcome,
        "detail": result.detail,
        "fixtures": result.fixtures,
    }


def merge_samples(samples: Sequence[Mapping]) -> dict[str, dict]:
    """Per-test entries over all runs: worst outcome wins; fixture errors, which have no duration, are kept."""
    ids = sorted({tid for s in samples for tid in (*s["seconds"], *s["outcome"])})
    tests: dict[str, dict] = {}
    for tid in ids:
        worst, detail = "ok", None
        for s in samples:
            outcome = s["outcome"].get(tid, "ok")
            if OUTCOME_RANK[outcome] > OUTCOME_RANK[worst]:
                worst, detail = outcome, s["detail"].get(tid)
        tests[tid] = {
            "seconds": [round(s["seconds"].get(tid, 0.0), 4) for s in samples],
            "outcome": worst,
            **({"detail": detail} if detail else {}),
        }
    return tests


def merge_fixtures(samples: Sequence[Mapping]) -> dict[str, dict]:
    """Class/module fixture outcomes over all runs, worst first; kept out of the per-test entries."""
    merged: dict[str, dict] = {}
    for s in samples:
        for name, entry in s.get("fixtures", {}).items():
            if OUTCOME_RANK[entry["outcome"]] > OUTCOME_RANK[merged.get(name, {"outcome": "ok"})["outcome"]]:
                merged[name] = dict(entry)
    return dict(sorted(merged.items()))


def passed(data: Mapping) -> bool:
    """True when no test failed or errored and no fixture errored; skips never fail a run."""
    tests_ok = all(e["outcome"] in ("ok", "skip") for e in data["tests"].values())
    fixtures_ok = all(f["outcome"] == "skip" for f in data.get("fixtures", {}).values())
    return tests_ok and fixtures_ok


def collect(repo: Path, runs: int, start_dir: str = "tests", extra_provenance: Mapping[str, str] | None = None) -> dict:
    if str(repo) not in sys.path:
        sys.path.insert(0, str(repo))
    origin = Path.cwd()
    try:
        samples = [run_once(repo, start_dir) for _ in range(runs)]
    finally:
        os.chdir(origin)
    return {
        "schema": SCHEMA,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "node": shutil.which("node") and subprocess.run(["node", "--version"], capture_output=True, text=True).stdout.strip(),
        },
        "provenance": provenance(extra_provenance),
        "counts": [s["counts"] for s in samples if "counts" in s],
        "cpu_seconds": [round(s["cpu_seconds"], 3) for s in samples if "cpu_seconds" in s],
        "runs": runs,
        "discovery_seconds": [round(s["discovery_seconds"], 3) for s in samples],
        "wall_seconds": [round(s["wall_seconds"], 3) for s in samples],
        "tests": merge_samples(samples),
        "fixtures": merge_fixtures(samples),
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
    fixtures = data.get("fixtures", {})
    if fixtures:
        counts = defaultdict(int)
        for f in fixtures.values():
            counts[f["outcome"]] += 1
        out.append(f"| Fixture outcomes (not tests) | {', '.join(f'{k} {v}' for k, v in sorted(counts.items()))} |")
    if data.get("cpu_seconds"):
        out.append(f"| Process CPU time incl. children (median of runs) | {statistics.median(data['cpu_seconds']):,.1f} |")
    for i, c in enumerate(data.get("counts", []), 1):
        out.append(f"| Run {i} counts | ran {c['ran']}, skipped {c['skipped']}, failed {c['failed']}, errored {c['errored']} |")
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
    if fixtures:
        out.extend(["", "**Fixture outcomes**", "", "| Fixture | Outcome | Detail |", "| --- | --- | --- |"])
        out.extend(f"| `{name}` | {f['outcome']} | {f.get('detail', '')} |" for name, f in fixtures.items())
    out.append("")
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=1, help="repeat the suite N times (default 1)")
    parser.add_argument("--start-dir", default="tests", help="discovery directory relative to the repo (default tests)")
    parser.add_argument("--out", type=Path, help="write the raw timing JSON here")
    parser.add_argument("--from-json", type=Path, help="render a summary from stored JSON instead of running")
    parser.add_argument("--provenance", action="append", default=[], metavar="KEY=VALUE", help="extra provenance field (repeatable)")
    parser.add_argument("--top", type=int, default=15, help="rows in the slowest-N tables")
    args = parser.parse_args(argv)
    if args.from_json:
        print(render_markdown(json.loads(args.from_json.read_text(encoding="utf-8")), args.top))
        return 0
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    out = args.out.resolve() if args.out else None
    extra = dict(item.split("=", 1) for item in args.provenance if "=" in item)
    data = collect(REPO_ROOT, args.runs, args.start_dir, extra)
    if out:
        out.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(render_markdown(data, args.top))
    return 0 if passed(data) else 1


if __name__ == "__main__":
    sys.exit(main())
