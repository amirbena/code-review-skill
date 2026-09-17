#!/usr/bin/env python3
"""Class 2 Cloud Routine entrypoint (Issue #415).

Invoked by the maintainer-controlled Claude Cloud Routine prompt described
in `docs/benchmark/cloud-routine-integration.md` — never by contributor PR
automation. Wraps the unmodified `run_benchmark.py` pipeline with the three
things a Cloud Routine cannot get for free: positive completion
verification (never trust the Routine's own "green" status), explicit
runtime/model/SHA metadata (neither is automatic in a Cloud Routine), and
durable evidence persistence as a comment on a tracking GitHub Issue
(outside the Routine's own transcript/run history).

Modes (docs/benchmark/cloud-routine-integration.md §2, two-tier scheduled
execution contract: docs/benchmark/corpus/README.md, Issue #431):

- ``smoke``    — one or a few fixed case ids, to sanity-check the Routine.
- ``selected`` — whatever case ids are handed to it (e.g. a future Top-K
  output); this script computes no selection itself.
- ``sentinel`` — the fixed, permanent 4-case canonical corpus
  (``--corpus-dir``'s own top-level, non-recursive ``*.yaml`` glob) —
  never rotated, sampled, or Top-K'd. Scheduled every 3 days.
- ``comprehensive`` — every ``benchmark-case/v2`` fixture in the corpus
  tree under ``--corpus-dir``, discovered recursively and programmatically
  (``benchmark_corpus_membership.discover_comprehensive_fixtures`` —
  never a hard-coded count or list). Scheduled weekly (Friday).
- ``full``     — **deprecated fixed synonym for ``sentinel``** (Issue
  #431): before this issue, ``full`` ambiguously meant "the whole
  --corpus-dir glob", which in practice only ever resolved to the 4
  top-level canonical cases because that glob is non-recursive. It is
  kept, unchanged in behavior, for backward compatibility with existing
  Cloud Routine prompt configurations, and emits a deprecation notice to
  stderr; new configuration should use ``--mode sentinel`` explicitly.
  ``full`` is never made to mean "comprehensive".
- ``auth-check`` — no benchmark run; only proves GitHub issue
  create/comment permissions work from inside the Routine's own
  execution context.

Both scheduled lanes (``sentinel``, ``comprehensive``) are maintainer-
controlled Cloud Routine invocations, configured for a 01:00 Israel-local
start / 04:00 maximum-completion window
(``docs/benchmark/cloud-routine-integration.md`` §9,
``docs/benchmark/nightly-history-and-baseline.md`` §2) — timezone/DST
handling is a Cloud Routine scheduling-configuration responsibility, never
repository runtime logic; nothing in this module reads or computes a
timezone.

Usage::

    python3 scripts/benchmark/run_benchmark_routine.py --mode smoke \\
        --case-id correctness-off-by-one-pagination \\
        --evidence-issue 420 --model-id claude-opus-5

    python3 scripts/benchmark/run_benchmark_routine.py --mode sentinel \\
        --evidence-issue 420 --model-id claude-opus-5

    python3 scripts/benchmark/run_benchmark_routine.py --mode comprehensive \\
        --evidence-issue 420 --model-id claude-opus-5

    python3 scripts/benchmark/run_benchmark_routine.py --mode auth-check \\
        --evidence-issue 420
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.benchmark import run_benchmark as rb  # noqa: E402
from scripts.benchmark.benchmark_corpus_membership import (  # noqa: E402
    COMPREHENSIVE_LANE,
    SENTINEL_LANE,
    canonical_lane,
    discover_comprehensive_fixtures,
)
from scripts.benchmark.benchmark_review_adapter import resolve_cli_executable  # noqa: E402
from scripts.benchmark.benchmark_routine_verify import verify_benchmark_output  # noqa: E402

AUTH_CHECK_MARKER = "<!-- benchmark-routine-auth-check -->"
EVIDENCE_MARKER = "<!-- benchmark-routine-evidence -->"


class RoutineExecutionError(RuntimeError):
    """A Routine-level failure: never persisted as passing evidence."""


@dataclass(frozen=True)
class RunMetadata:
    mode: str
    repo_sha: str
    runtime_name: str
    runtime_version: str
    model_id: str
    timestamp: str

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "repo_sha": self.repo_sha,
            "runtime_name": self.runtime_name,
            "runtime_version": self.runtime_version,
            "model_id": self.model_id,
            "timestamp": self.timestamp,
        }


def _git_sha(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(repo_root), capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def _runtime_version(executable: str) -> str:
    """Best-effort CLI version probe; the Routine prompt may override it."""
    try:
        proc = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=30)
        return proc.stdout.strip() or proc.stderr.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        required=True,
        choices=["smoke", "selected", "sentinel", "comprehensive", "full", "auth-check"],
    )
    parser.add_argument(
        "--case-id",
        action="append",
        default=[],
        help="Case id to run (repeatable). Required for smoke/selected; ignored for "
        "sentinel/comprehensive/full/auth-check.",
    )
    parser.add_argument("--corpus-dir", default=str(rb.DEFAULT_CORPUS_DIR))
    parser.add_argument("--cli", default=None, help="Override the review CLI executable.")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--evidence-issue",
        type=int,
        default=None,
        help="Existing tracking Issue number to comment evidence/auth-check results onto. "
        "If omitted, a new tracking Issue is created and its number printed to stdout.",
    )
    parser.add_argument(
        "--runtime-name", default=None, help="Explicit runtime/CLI name (else the resolved CLI executable)."
    )
    parser.add_argument(
        "--runtime-version", default=None, help="Explicit runtime/CLI version (else a best-effort probe)."
    )
    parser.add_argument(
        "--model-id",
        default="unknown",
        help="Explicit model/backend identifier. Not auto-detectable in a Cloud Routine — "
        "the Routine prompt should always set this explicitly (contract §5).",
    )
    parser.add_argument(
        "--results-out",
        default=None,
        type=Path,
        help="Issue #338: write the concatenated raw per-invocation run_benchmark.py output "
        "here, for nightly-history persistence. Only written on a verified run, mirroring "
        "the fail-closed evidence-posting rule below.",
    )
    return parser


def _gh(*args: str) -> str:
    proc = subprocess.run(["gh", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RoutineExecutionError(f"gh {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def _post_evidence(issue: int | None, marker: str, title: str, body: str) -> int:
    """Create the tracking Issue if none is given, else comment on it.

    Returns the Issue number used, so a caller can persist it for future
    runs (the Routine prompt is expected to pass it back in on subsequent
    invocations rather than creating a fresh tracking Issue every run).
    """
    full_body = f"{marker}\n\n{body}"
    # --body-file, not --body: a full-corpus evidence payload can exceed the
    # OS argv-size limit if passed as a literal command-line argument.
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
        handle.write(full_body)
        body_path = handle.name
    try:
        if issue is None:
            url = _gh("issue", "create", "--title", title, "--body-file", body_path)
            return int(url.rstrip("/").rsplit("/", 1)[-1])
        _gh("issue", "comment", str(issue), "--body-file", body_path)
        return issue
    finally:
        Path(body_path).unlink(missing_ok=True)


def run_auth_check(args: argparse.Namespace) -> int:
    timestamp = datetime.now(timezone.utc).isoformat()
    body = f"Auth/issue-permission smoke check at {timestamp} — GitHub create/comment succeeded."
    issue = _post_evidence(args.evidence_issue, AUTH_CHECK_MARKER, "Benchmark routine auth check", body)
    print(json.dumps({"passed": True, "evidence_issue": issue, "timestamp": timestamp}, indent=2))
    return 0


def _resolve_invocations(args: argparse.Namespace) -> tuple[str, list[tuple[str | None, str]]]:
    """Resolve `--mode` to (effective_mode, [(case_id, corpus_dir), ...]).

    `full` is a deprecated, fixed synonym for `sentinel` (Issue #431,
    `benchmark_corpus_membership.py`): the returned effective mode is
    always the canonical lane name, so persisted metadata never carries
    the ambiguous legacy value.
    """
    if args.mode in ("smoke", "selected"):
        if not args.case_id:
            raise RoutineExecutionError(f"--mode {args.mode} requires at least one --case-id")
        return args.mode, [(cid, args.corpus_dir) for cid in args.case_id]

    if args.mode == "full":
        print(
            "warning: --mode full is a deprecated fixed synonym for --mode sentinel "
            "(Issue #431); pass --mode sentinel explicitly in new configuration.",
            file=sys.stderr,
        )

    effective_mode = canonical_lane(args.mode)

    if effective_mode == SENTINEL_LANE:
        return effective_mode, [(None, args.corpus_dir)]

    if effective_mode == COMPREHENSIVE_LANE:
        fixtures = discover_comprehensive_fixtures(Path(args.corpus_dir))
        if not fixtures:
            raise RoutineExecutionError(
                f"--mode comprehensive found no benchmark-case/v2 fixtures under {args.corpus_dir}"
            )
        return effective_mode, [(fx.case_id, str(fx.corpus_dir)) for fx in fixtures]

    raise RoutineExecutionError(f"unhandled --mode {args.mode!r}")  # pragma: no cover - argparse guards choices


def run_benchmark_mode(args: argparse.Namespace) -> int:
    effective_mode, invocations = _resolve_invocations(args)

    executable = args.cli or resolve_cli_executable()
    metadata = RunMetadata(
        mode=effective_mode,
        repo_sha=_git_sha(REPO_ROOT),
        runtime_name=args.runtime_name or executable,
        runtime_version=args.runtime_version or _runtime_version(executable),
        model_id=args.model_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    overall_ok = True
    verifications: list[dict] = []
    raw_invocations: list[dict] = []
    for case_id, corpus_dir in invocations:
        argv = ["--corpus-dir", corpus_dir, "--cli", executable, "--timeout", str(args.timeout)]
        if case_id is not None:
            argv += ["--case-id", case_id]
        proc = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts" / "benchmark" / "run_benchmark.py"), *argv],
            capture_output=True,
            text=True,
        )
        verification = verify_benchmark_output(proc.stdout, proc.returncode)
        verifications.append(verification.as_dict())
        if not verification.passed:
            overall_ok = False
            continue
        try:
            raw_invocations.append({"case_id": case_id, "run": json.loads(proc.stdout)["run"]})
        except (json.JSONDecodeError, KeyError, TypeError):
            overall_ok = False

    result = {
        "metadata": metadata.as_dict(),
        "overall_verified": overall_ok,
        "runs": verifications,
    }

    if not overall_ok:
        print(json.dumps(result, indent=2), file=sys.stderr)
        raise RoutineExecutionError(
            "fail-closed: at least one run did not pass positive completion verification"
        )

    if args.results_out is not None:
        args.results_out.parent.mkdir(parents=True, exist_ok=True)
        args.results_out.write_text(json.dumps(raw_invocations, indent=2), encoding="utf-8")

    body = "```json\n" + json.dumps(result, indent=2) + "\n```"
    title = f"Benchmark evidence — {metadata.mode} — {metadata.repo_sha[:12]}"
    issue = _post_evidence(args.evidence_issue, EVIDENCE_MARKER, title, body)
    result["evidence_issue"] = issue
    print(json.dumps(result, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        if args.mode == "auth-check":
            return run_auth_check(args)
        return run_benchmark_mode(args)
    except RoutineExecutionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
