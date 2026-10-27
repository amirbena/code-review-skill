#!/usr/bin/env python3
"""Summarize sealed benchmark results and their recorded provenance, read-only.

Reads `benchmark-result/v1` records from a `benchmark-history` git ref or a
checked-out directory, validates each, and reports quality metrics, runtime
provenance and which lanes have no sealed record. Never writes anywhere.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_platform.benchmark.scripts import benchmark_result as res  # noqa: E402

DEFAULT_REF = "origin/benchmark-history"
MANIFEST = REPO_ROOT / "runtime_platform" / "benchmark" / "schedule" / "expected-run-manifest.json"
GIT_TIMEOUT_S = 120
PROVENANCE_FIELDS = (
    ("provenance", "repo_sha"),
    ("provenance", "entrypoint_version"),
    ("provenance", "spec_sha256"),
    ("runtime", "model_id"),
    ("runtime", "runtime_name"),
    ("runtime", "runtime_version"),
    ("runtime", "adapter_id"),
    ("corpus", "corpus_id"),
)


class SummaryError(RuntimeError):
    """The history could not be read."""


class Source(Protocol):
    def record_paths(self) -> list[str]: ...

    def read(self, path: str) -> str | None: ...


class DirectorySource:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def record_paths(self) -> list[str]:
        return sorted(p.relative_to(self.root).as_posix() for p in (self.root / "records").rglob("*.json"))

    def read(self, path: str) -> str | None:
        target = self.root / path
        return target.read_text(encoding="utf-8") if target.is_file() else None


class GitRefSource:
    def __init__(self, ref: str, repo: Path = REPO_ROOT) -> None:
        self.ref, self.repo = ref, repo

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args], capture_output=True, text=True, timeout=GIT_TIMEOUT_S, check=False
        )

    def record_paths(self) -> list[str]:
        listing = self._git("ls-tree", "-r", "--name-only", self.ref, "records/")
        if listing.returncode != 0:
            raise SummaryError(f"cannot list records at {self.ref}: {listing.stderr.strip()}")
        return sorted(line for line in listing.stdout.splitlines() if line.endswith(".json"))

    def read(self, path: str) -> str | None:
        shown = self._git("show", f"{self.ref}:{path}")
        return shown.stdout if shown.returncode == 0 else None


def declared_lanes(manifest: Path = MANIFEST) -> list[str]:
    return sorted(json.loads(manifest.read_text(encoding="utf-8"))["lanes"])


def load(source: Source) -> tuple[dict[str, list[dict]], list[tuple[str, list[str]]]]:
    """Valid records grouped by lane (oldest first) and (path, errors) for each rejected record."""
    by_lane: dict[str, list[dict]] = {}
    rejected: list[tuple[str, list[str]]] = []
    for path in source.record_paths():
        try:
            record = json.loads(source.read(path) or "")
        except json.JSONDecodeError as exc:
            rejected.append((path, [f"unreadable: {exc}"]))
            continue
        errors = res.validate_record(record)
        if errors:
            rejected.append((path, errors))
        else:
            by_lane.setdefault(record["lane"], []).append(record)
    for records in by_lane.values():
        records.sort(key=lambda r: (r["started_at"], r["run_id"]))
    return by_lane, rejected


def pointer(source: Source, lane: str) -> dict | None:
    text = source.read(f"baselines/{lane}.json")
    return json.loads(text) if text else None


def provenance_gaps(record: Mapping[str, Any]) -> list[str]:
    return [f"{a}.{b}" for a, b in PROVENANCE_FIELDS if not (record.get(a) or {}).get(b)]


def summary_dict(source: Source, lanes: Sequence[str]) -> dict:
    by_lane, rejected = load(source)
    return {
        "lanes": {
            lane: {
                "records": by_lane.get(lane, []),
                "baseline_pointer": pointer(source, lane),
            }
            for lane in sorted(set(lanes) | set(by_lane))
        },
        "rejected": [{"path": p, "errors": e} for p, e in rejected],
    }


def execution_reliability(record: Mapping[str, Any]) -> dict[str, Any]:
    """Errored cases, and false-negative/positive totals over executed cases only (#819).

    The sealed `aggregate` counts every required finding of an errored case as missed; the
    per-case rows let the report separate that without touching the record."""
    cases = record["cases"]
    executed = [c for c in cases if c["status"] == "executed"]
    return {
        "errored_case_ids": sorted(c["id"] for c in cases if c["status"] != "executed"),
        "executed_cases": len(executed),
        "executed_false_negatives": sum(c["metrics"]["false_negatives"] for c in executed),
        "executed_false_positives": sum(c["metrics"]["false_positives"] for c in executed),
    }


def _row(record: Mapping[str, Any]) -> str:
    agg = record["aggregate"]
    m, s = agg["metrics"], agg["severity"]
    runtime, prov = record["runtime"], record["provenance"]
    drift = record["drift"]["outcome"]["status"]
    return (
        f"| `{record['run_id']}` | {record['finished_at'][:10]} | {record['corpus']['case_count']} "
        f"| {s['exact_rate']} | {m['total_false_negatives']} | {m['total_false_positives']} "
        f"| {m['total_near_misses']} | {m['errored_cases']} | {agg['duplicate_noise']['total_redundant_findings']} "
        f"| {drift} | {runtime['model_id']} | {runtime['runtime_version']} | `{prov['repo_sha'][:12]}` "
        f"| {record['execution']['duration_s']:.0f} | {record['verification']['overall_verified']} |"
    )


def render_markdown(data: Mapping[str, Any]) -> str:
    out: list[str] = []
    for lane, entry in data["lanes"].items():
        records = entry["records"]
        out += [f"### Lane `{lane}`", ""]
        if not records:
            out += ["No sealed record exists for this lane.", ""]
            continue
        out += [
            f"{len(records)} sealed record(s), oldest first. Rates are exact fractions over matched findings.",
            "",
            "| Run | Date | Corpus cases | Severity exact | FN | FP | Near-miss | Errored | Redundant | Drift status "
            "| Model | Runtime | Repo SHA | Seconds | Verified |",
            "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- | --- | ---: | --- |",
            *(_row(r) for r in records),
            "",
        ]
        newest = execution_reliability(records[-1])
        out.append(
            f"Execution reliability (newest record): {newest['executed_cases']} of {len(records[-1]['cases'])} "
            f"case(s) executed; FN {newest['executed_false_negatives']} / FP {newest['executed_false_positives']} "
            "over executed cases. Errored: "
            + (", ".join(f"`{c}`" for c in newest["errored_case_ids"]) or "none")
            + "."
        )
        ptr = entry["baseline_pointer"]
        out.append(
            f"Pinned baseline: `{ptr['run_id']}` (source `{ptr['source']}`)." if ptr else "No pinned baseline pointer."
        )
        gaps = provenance_gaps(records[-1])
        out.append(
            "Newest record carries every provenance field checked."
            if not gaps
            else f"Newest record is missing: {', '.join(gaps)}."
        )
        out.append("")
    if data["rejected"]:
        out += ["### Rejected records", ""]
        out += [f"- `{r['path']}`: {r['errors'][0]}" for r in data["rejected"]]
        out.append("")
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    where = parser.add_mutually_exclusive_group()
    where.add_argument("--ref", default=DEFAULT_REF, help=f"benchmark-history git ref (default {DEFAULT_REF})")
    where.add_argument("--history-dir", type=Path, help="a checked-out benchmark-history directory")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of Markdown")
    args = parser.parse_args(argv)
    source: Source = DirectorySource(args.history_dir) if args.history_dir else GitRefSource(args.ref)
    try:
        data = summary_dict(source, declared_lanes())
    except (SummaryError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(data, indent=2, sort_keys=True) if args.json else render_markdown(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
