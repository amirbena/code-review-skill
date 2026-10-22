#!/usr/bin/env python3
"""Profile scripts/packaging/package-skills.sh on a scratch copy without modifying it.

An interposed `python3` shim timestamps every spawn; time is attributed to the
script or subcommand each spawn ran, and the remainder to shell work.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
IGNORED = shutil.ignore_patterns(".git", "dist", "__pycache__", ".claude", "node_modules")

SHIM = """#!/bin/sh
t0=$(perl -MTime::HiRes=time -e 'printf "%.6f", time')
"$REAL_PYTHON3" "$@"
rc=$?
t1=$(perl -MTime::HiRes=time -e 'printf "%.6f", time')
printf '%s\\t%s\\t%s\\n' "$t0" "$t1" "$*" >> "$SPAWN_LOG"
exit $rc
"""


def spawn_label(args: str) -> str:
    """Script basename plus the first subcommand-like word, so spawns group by purpose."""
    words = args.split()
    if not words:
        return "python3 (interactive/stdin)"
    script = Path(words[0]).name if not words[0].startswith("-") else words[0]
    sub = next((w for w in words[1:] if not w.startswith(("-", "/", "."))), "")
    return f"{script} {sub}".strip()


def read_spawns(log: Path) -> list[dict]:
    spawns = []
    for line in log.read_text(encoding="utf-8").splitlines() if log.exists() else []:
        start, end, args = line.split("\t", 2)
        spawns.append({"start": float(start), "end": float(end), "seconds": float(end) - float(start), "label": spawn_label(args)})
    return spawns


def baseline_python_start(runs: int = 20) -> float:
    """Median wall time of one bare interpreter start, to quantify spawn overhead."""
    times = []
    for _ in range(runs):
        started = time.perf_counter()
        subprocess.run([sys.executable, "-c", "pass"], check=True)
        times.append(time.perf_counter() - started)
    return statistics.median(times)


def profile_once(scratch: Path, mode: str, cold: bool) -> dict:
    dist = scratch / "dist"
    if cold and dist.exists():
        shutil.rmtree(dist)
    shim_dir = Path(tempfile.mkdtemp(prefix="pyshim-"))
    log = shim_dir / "spawns.tsv"
    shim = shim_dir / "python3"
    shim.write_text(SHIM, encoding="utf-8")
    shim.chmod(0o755)
    env = dict(os.environ, PATH=f"{shim_dir}{os.pathsep}{os.environ['PATH']}", REAL_PYTHON3=shutil.which("python3") or sys.executable, SPAWN_LOG=str(log))
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.perf_counter()
    proc = subprocess.run(["bash", "scripts/packaging/package-skills.sh", mode], cwd=scratch, env=env, capture_output=True, text=True)
    wall = time.perf_counter() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    spawns = read_spawns(log)
    shutil.rmtree(shim_dir)
    phases: dict[str, dict] = defaultdict(lambda: {"count": 0, "seconds": 0.0})
    for s in spawns:
        phases[s["label"]]["count"] += 1
        phases[s["label"]]["seconds"] += s["seconds"]
    spawn_total = sum(s["seconds"] for s in spawns)
    manifest = scratch / "dist" / "skills-manifest.json"
    return {
        "mode": mode,
        "cold": cold,
        "exit_code": proc.returncode,
        "wall_seconds": wall,
        "cpu_seconds": (after.ru_utime + after.ru_stime) - (before.ru_utime + before.ru_stime),
        "python_spawns": len(spawns),
        "python_spawn_seconds": spawn_total,
        "shell_other_seconds": wall - spawn_total,
        "phases": {k: dict(v) for k, v in sorted(phases.items(), key=lambda kv: -kv[1]["seconds"])},
        "manifest_sha256": subprocess.run(["shasum", "-a", "256", str(manifest)], capture_output=True, text=True).stdout.split()[0] if manifest.exists() else None,
    }


def render(report: Mapping) -> str:
    out = [
        f"bash {report['bash']}; python {report['python']}; {report['platform']}; python3 start-up median {report['python_start_seconds'] * 1000:.1f} ms",
        "",
        "| Mode | Cold | Wall s | CPU s | python3 spawns | Spawn s | Shell/other s | Manifest sha256 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in report["runs"]:
        out.append(f"| {r['mode']} | {r['cold']} | {r['wall_seconds']:.2f} | {r['cpu_seconds']:.2f} | {r['python_spawns']} | {r['python_spawn_seconds']:.2f} | {r['shell_other_seconds']:.2f} | {(r['manifest_sha256'] or '-')[:12]} |")
    for r in report["runs"]:
        if r["cold"]:
            out.extend(["", f"**Phases, {r['mode']} cold**", "", "| Spawn | Count | Seconds |", "| --- | ---: | ---: |"])
            out.extend(f"| `{k}` | {v['count']} | {v['seconds']:.2f} |" for k, v in r["phases"].items())
    out.append("")
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modes", nargs="+", default=["local", "github", "all"])
    parser.add_argument("--out", type=Path, help="write the raw JSON here")
    args = parser.parse_args(argv)
    bash_version = subprocess.run(["bash", "-c", "echo $BASH_VERSION"], capture_output=True, text=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="pkg-profile-") as tmp:
        scratch = Path(tmp) / "repo"
        shutil.copytree(REPO_ROOT, scratch, ignore=IGNORED)
        runs = []
        for mode in args.modes:
            runs.append(profile_once(scratch, mode, cold=True))
            runs.append(profile_once(scratch, mode, cold=False))
    import platform

    report = {"bash": bash_version, "python": platform.python_version(), "platform": platform.platform(), "python_start_seconds": baseline_python_start(), "runs": runs}
    if args.out:
        args.out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(render(report))
    return 0 if all(r["exit_code"] == 0 for r in runs) else 1


if __name__ == "__main__":
    sys.exit(main())
