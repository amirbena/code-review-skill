#!/usr/bin/env python3
"""Maintainer-run measurement of dependency tree inspection (Issue #732).

Runs the ``dependency-tree-inspection`` sub-corpus under a baseline arm (the
pre-#730 skill checkout, diff only) and a candidate arm (this checkout, with the
tree evidence), alternating arms, once per review adapter, and writes one JSON
record with the pre-registered disposition per adapter. Decision record,
pre-registration, and gate:
runtime_platform/benchmark/dependency-tree-inspection-measurement.md.

Usage::

    python3 runtime_platform/benchmark/scripts/measure_dependency_tree.py \\
        --baseline-skill-root /path/to/checkout-at-baseline-sha --out measurement.json
    python3 runtime_platform/benchmark/scripts/measure_dependency_tree.py \\
        --baseline-skill-root ... --github-repo-reviewer pkg.mod:make_repo \\
        --github-api-reviewer pkg.mod:make_api --runs 3 --out measurement.json

The script refuses to run unless the pre-registration is committed, its fixture
digest matches the sub-corpus, the baseline checkout is at the registered SHA, and
this checkout descends from the pre-registration commit and is clean. Local runs use
the production adapter with verified isolation. The two GitHub adapters are
caller-supplied ``module:factory`` callables (no arguments, taking a ``skill_root`` keyword
(the skill checkout the arm must run: the registered baseline for the baseline arm, this checkout
for the candidate; a factory that cannot accept it is refused) and returning a reviewer
accepting the optional ``dependency_trees`` keyword, exposing ``last_report`` and,
optionally, ``last_usage``); an adapter that is not supplied is recorded ``not-run``.

Exit code reflects execution health only: 0 when every run executed, 1 when any
errored, 2 when the protocol preconditions or runtime are not met. The disposition
never changes it. An existing ``--out`` is never overwritten.
"""

from __future__ import annotations

import argparse
import importlib
import inspect
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from runtime_platform.benchmark.reference import benchmark_dependency_tree as bdt  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_fixture as bf  # noqa: E402
from runtime_platform.benchmark.reference import benchmark_runner as br  # noqa: E402
from runtime_platform.benchmark.scripts import benchmark_run_evidence as bre  # noqa: E402
from runtime_platform.benchmark.scripts.benchmark_review_adapter import (  # noqa: E402
    ProductionReviewerAdapter,
    RuntimeUnavailableError,
    check_runtime_available,
    resolve_cli_executable,
)

CORPUS_DIR = REPO_ROOT / "benchmark" / "corpus" / "dependency-tree-inspection"
PREREGISTRATION = CORPUS_DIR / "pre-registration.json"
DEFAULT_RUNS = 3
DEFAULT_TIMEOUT_SECONDS = 600.0
HARNESS_INVALID_CATEGORIES = ("isolation-failed", "stream-parse-failure")


class HarnessInvalid(RuntimeError):
    """The run cannot be interpreted (isolation not established); stop and keep the evidence."""


class ArmAdapter:
    """The baseline withholds the tree evidence (the diff-only review the original
    miss had); the candidate forwards it. Both see identical materialized inputs."""

    def __init__(self, inner: Callable[..., Any], *, trees: bool) -> None:
        self.inner, self.trees = inner, trees

    def __call__(self, workspace: Any, **kwargs: Any) -> Any:
        if not self.trees:
            kwargs.pop("dependency_trees", None)
        return self.inner(workspace, **kwargs)

    @property
    def last_report(self) -> str | None:
        return getattr(self.inner, "last_report", None)

    @property
    def last_evidence(self) -> bre.RunEvidence | None:
        return getattr(self.inner, "last_evidence", None)

    @property
    def last_tokens(self) -> int | None:
        usage = getattr(self.inner, "last_usage", None)
        return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0)) if usage else None


def load_cases(corpus_dir: Path = CORPUS_DIR) -> list[bf.BenchmarkCase]:
    return [bf.parse_case(yaml.safe_load(p.read_text(encoding="utf-8"))) for p in sorted(corpus_dir.glob("*.yaml"))]


def measure_adapter(
    adapter: str,
    cases: Sequence[bf.BenchmarkCase],
    runs: int,
    make_reviewers: Callable[[str], Callable[..., Any]],
    evidence_dir: Path | None = None,
) -> list[bdt.RunObservation]:
    """Alternate baseline/candidate per run so drift lands on both arms. Each run's raw
    evidence is written first, success or failure, when the reviewer produces any."""
    observations: list[bdt.RunObservation] = []
    for case in (c for c in cases if bdt.applies_to(c, adapter)):
        for index in range(1, runs + 1):
            for arm in bdt.ARMS:
                wrapped = ArmAdapter(make_reviewers(arm), trees=arm == bdt.CANDIDATE)
                started = time.monotonic()
                result = br.run_case(case, wrapped)
                seconds = round(time.monotonic() - started, 3)
                evidence = wrapped.last_evidence
                evidence_file = None
                if evidence is not None and evidence_dir is not None:
                    evidence_file = bre.write_run_evidence(evidence_dir, f"{adapter}-{case.id}-{arm}-{index}", evidence)
                observations.append(
                    bdt.observe_run(
                        case, result, wrapped.last_report, arm=arm, seconds=seconds, tokens=wrapped.last_tokens,
                        error_category=evidence.error_category if evidence else None, evidence_file=evidence_file,
                    )
                )
                if evidence is not None and evidence.error_category in HARNESS_INVALID_CATEGORIES:
                    raise HarnessInvalid(f"{adapter}/{case.id}/{arm}/{index}: {evidence.error_message} (evidence: {evidence_file})")
    return observations


def _load_factory(spec: str) -> Callable[..., Callable[..., Any]]:
    """A supplied reviewer factory takes ``skill_root`` (the skill checkout an arm must run), so a
    baseline arm cannot silently run the candidate skill. One that cannot accept it is refused."""
    module_name, _, attr = spec.partition(":")
    if not module_name or not attr:
        raise ValueError("reviewer must be module:factory")
    factory = getattr(importlib.import_module(module_name), attr)
    params = inspect.signature(factory).parameters
    if "skill_root" not in params and not any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        raise ValueError(f"{spec} must accept a skill_root keyword so each arm runs its registered skill checkout")
    return factory


def skill_root_for(arm: str, baseline_root: Path) -> Path:
    return baseline_root if arm == bdt.BASELINE else REPO_ROOT


def _git(root: Path, *args: str) -> str | None:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    return done.stdout.strip() if done.returncode == 0 else None


def _registration_commit() -> str | None:
    try:
        rel = PREREGISTRATION.relative_to(REPO_ROOT)
    except ValueError:
        return None
    return _git(REPO_ROOT, "log", "-1", "--format=%H", "--", str(rel)) or None


def check_protocol(baseline_root: Path, *, smoke: bool, allow_dirty: bool) -> list[str]:
    """Why this run would not count, or an empty list. Pre-registration comes first: a run
    made before it, against other fixtures, or on an unregistered baseline is not counted."""
    problems: list[str] = []
    if not PREREGISTRATION.is_file():
        return ["pre-registration.json is missing"]
    prereg = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    if bdt.fixture_set_digest(CORPUS_DIR) != prereg.get("fixture_set_digest"):
        problems.append("the fixture set differs from the pre-registered digest: a changed set is a new pre-registration")
    elif bdt.build_preregistration(load_cases(), CORPUS_DIR) != prereg:
        problems.append("the thresholds, expectations or configuration in code differ from pre-registration.json: a changed protocol is a new pre-registration")
    commit = _registration_commit()
    if not commit:
        problems.append("pre-registration.json is not committed")
    elif _git(REPO_ROOT, "merge-base", "--is-ancestor", commit, "HEAD") is None:
        problems.append(f"this checkout does not descend from the pre-registration commit {commit}")
    head = _git(baseline_root, "rev-parse", "HEAD")
    if head != prereg.get("baseline_sha"):
        problems.append(f"the baseline checkout is at {head}, the pre-registration names {prereg.get('baseline_sha')}")
    if not (smoke or allow_dirty) and _git(REPO_ROOT, "status", "--porcelain", "--untracked-files=no") != "":
        problems.append("the skill checkout has uncommitted changes (or git cannot tell)")
    return problems


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure dependency tree inspection (issue #732).")
    parser.add_argument("--baseline-skill-root", required=True, help="A checkout of the pre-registered baseline SHA.")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS, help=f"Runs per arm per case (default {DEFAULT_RUNS}).")
    parser.add_argument("--cli", default=None, help="Review CLI executable (default: $BENCHMARK_REVIEW_CLI or claude).")
    parser.add_argument("--github-repo-reviewer", default=None, help="module:factory for the repository-backed GitHub adapter.")
    parser.add_argument("--github-api-reviewer", default=None, help="module:factory for the API-only GitHub adapter.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--model", default=None, help="Model label recorded in the metadata only.")
    parser.add_argument("--out", default=None, help="Write the JSON record here (default: stdout). Never overwritten.")
    parser.add_argument("--evidence-dir", default=None, help="Per-run raw evidence (default: <out>.evidence). Must be absent or empty.")
    parser.add_argument("--case", action="append", help="Restrict to this case id (repeatable).")
    parser.add_argument("--smoke", action="store_true", help="One run per arm for a harness check; records smoke=true, never a measurement.")
    parser.add_argument("--allow-dirty", action="store_true", help="Harness check only; the record cannot be tied to a revision.")
    parser.add_argument("--retry-of", default=None, help="Reference of the record this run follows.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.smoke and not args.case:
        print("--smoke needs at least one --case; it is not a measurement", file=sys.stderr)
        return 2
    if args.runs < bdt.MIN_RUNS_PER_ARM and not args.smoke:
        print(f"--runs must be at least {bdt.MIN_RUNS_PER_ARM}", file=sys.stderr)
        return 2
    baseline_root = Path(args.baseline_skill_root).resolve()
    problems = check_protocol(baseline_root, smoke=args.smoke, allow_dirty=args.allow_dirty)
    if problems and not args.smoke:
        print("protocol not met, this run would not count:\n- " + "\n- ".join(problems), file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else None
    if out is not None and out.exists():
        print(f"{out} exists; an earlier record is never overwritten", file=sys.stderr)
        return 2
    evidence_dir = Path(args.evidence_dir) if args.evidence_dir else (out.with_name(out.name + ".evidence") if out else Path.cwd() / f"dti-evidence-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}")
    if evidence_dir.exists() and any(evidence_dir.iterdir()):
        print(f"{evidence_dir} is not empty; earlier evidence is never overwritten", file=sys.stderr)
        return 2
    executable = args.cli or resolve_cli_executable()
    try:
        check_runtime_available(executable)
    except RuntimeUnavailableError as exc:
        print(f"runtime unavailable: {exc}", file=sys.stderr)
        return 2

    cases = load_cases()
    unknown = sorted(set(args.case or ()) - {c.id for c in cases})
    if unknown:
        print(f"unknown --case: {unknown}", file=sys.stderr)
        return 2
    selected = [c for c in cases if not args.case or c.id in args.case]

    def local_reviewers(arm: str) -> Callable[..., Any]:
        return ProductionReviewerAdapter(
            executable=executable, timeout=args.timeout, verified_isolation=True,
            plugin_dir=skill_root_for(arm, baseline_root),
        )

    def supplied(spec: str) -> Callable[[str], Callable[..., Any]]:
        factory = _load_factory(spec)
        return lambda arm: factory(skill_root=skill_root_for(arm, baseline_root))

    try:  # refuse an unusable factory before any run is spent
        repo_reviewers = supplied(args.github_repo_reviewer) if args.github_repo_reviewer else None
        api_reviewers = supplied(args.github_api_reviewer) if args.github_api_reviewer else None
    except (ValueError, AttributeError, ImportError) as exc:
        print(f"unusable reviewer factory: {exc}", file=sys.stderr)
        return 2

    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        runs: dict[str, list[bdt.RunObservation] | None] = {
            bdt.LOCAL: measure_adapter(bdt.LOCAL, selected, args.runs, local_reviewers, evidence_dir),
            bdt.GITHUB_REPO: measure_adapter(bdt.GITHUB_REPO, selected, args.runs, repo_reviewers, evidence_dir) if repo_reviewers else None,
            bdt.GITHUB_API_ONLY: measure_adapter(bdt.GITHUB_API_ONLY, selected, args.runs, api_reviewers, evidence_dir) if api_reviewers else None,
        }
    except HarnessInvalid as exc:
        print(f"harness invalid, stopping: {exc}\nevidence kept in {evidence_dir}", file=sys.stderr)
        return 2

    record = bdt.measurement_record(
        runs,
        {a: [c.id for c in selected if bdt.applies_to(c, a)] for a in bdt.ADAPTERS},
        runs_per_arm=args.runs,
        metadata={
            "candidate_sha": _git(REPO_ROOT, "rev-parse", "HEAD"),
            "baseline_sha": _git(baseline_root, "rev-parse", "HEAD"),
            "skill_tree_dirty": bool(_git(REPO_ROOT, "status", "--porcelain", "--untracked-files=no")),
            "preregistration_commit": _registration_commit(),
            "protocol_problems": problems,
            "fixture_set_digest": bdt.fixture_set_digest(CORPUS_DIR),
            "runtime": executable,
            "model": args.model,
            "github_repo_reviewer": args.github_repo_reviewer,
            "github_api_reviewer": args.github_api_reviewer,
            "evidence_dir": str(evidence_dir),
            "retry_of": args.retry_of,
            "started_at": started_at,
            "smoke": bool(args.smoke),
            "cases": [c.id for c in selected],
        },
    )
    text = json.dumps(record, indent=2, sort_keys=True) + "\n"
    if out is not None:
        with open(out, "x", encoding="utf-8") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)
    json.dump(record["summary"], sys.stderr, indent=2)
    sys.stderr.write("\n")
    errored = any(not r.executed for rs in runs.values() for r in (rs or []))
    return 1 if errored else 0


if __name__ == "__main__":
    sys.exit(main())
