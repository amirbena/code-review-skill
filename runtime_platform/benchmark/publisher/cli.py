"""Command line for the publication CLI: `sweep`, with `--once` for a local or disaster-recovery pass."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from runtime_platform.benchmark.publisher import github_api
from runtime_platform.benchmark.publisher.memory import dry_run_overlay
from runtime_platform.benchmark.publisher.ports import FatalPublicationError
from runtime_platform.benchmark.publisher.model import Ports, SweepConfig
from runtime_platform.benchmark.publisher.sweep import run_sweep
from runtime_platform.benchmark.scripts.benchmark_result import parse_run_id
from runtime_platform.benchmark.scripts.benchmark_schedule_manifest import MANIFEST_PATH, ManifestError, load_manifest

PortsFactory = Callable[[Mapping[str, Any], str], Ports]
EXIT_USAGE = 2


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sweep = sub.add_parser("sweep", help="Publish every unpublished sealed result, oldest first.")
    sweep.add_argument("--once", action="store_true", help="A local or disaster-recovery pass outside GitHub Actions.")
    sweep.add_argument("--dry-run", action="store_true", help="Read and plan only: every write lands in memory.")
    sweep.add_argument("--run-id", help="Publish only this run_id.")
    sweep.add_argument(
        "--accept-unattributed", action="store_true",
        help="With --run-id: accept the run when the server cannot attribute its ref (never when it contradicts).",
    )
    sweep.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    sweep.add_argument("--app-slug", help="The publication App's slug (default: BENCHMARK_APP_SLUG).")
    sweep.add_argument("--run-url", help="URL recorded in receipts (default: the Actions run).")
    return parser


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return EXIT_USAGE


def _run_url(args: argparse.Namespace, env: Mapping[str, str], repository: str) -> str | None:
    if args.run_url:
        return args.run_url
    if env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_RUN_ID"):
        server = env.get("GITHUB_SERVER_URL", "https://github.com")
        return f"{server}/{env.get('GITHUB_REPOSITORY', repository)}/actions/runs/{env['GITHUB_RUN_ID']}"
    return f"https://github.com/{repository}" if args.once else None


def _real_ports(env: Mapping[str, str], repository: str) -> Ports:
    contents = github_api.require_installation_token("BENCHMARK_CONTENTS_TOKEN", env.get("BENCHMARK_CONTENTS_TOKEN"))
    issues = github_api.require_installation_token("BENCHMARK_ISSUES_TOKEN", env.get("BENCHMARK_ISSUES_TOKEN"))
    read = github_api.require_installation_token("BENCHMARK_READ_TOKEN", env.get("BENCHMARK_READ_TOKEN") or contents)
    return Ports(
        reader=github_api.GitHubHandoffReader(github_api.GitHubClient(read), repository),
        store=github_api.GitHubHistoryStore(github_api.GitHubClient(contents), repository),
        tracker=github_api.GitHubIssueTracker(github_api.GitHubClient(issues), repository),
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    ports_factory: PortsFactory | None = None,
) -> int:
    args = build_arg_parser().parse_args(argv)
    env = os.environ if env is None else env
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        return _fail(str(exc))
    repository = manifest.get("repository", "")
    slug = args.app_slug or env.get("BENCHMARK_APP_SLUG")
    if not slug:
        return _fail("the App slug is required (--app-slug or BENCHMARK_APP_SLUG): the acting identity must be known")
    if args.accept_unattributed and not args.run_id:
        return _fail("--accept-unattributed requires --run-id")
    if args.run_id and parse_run_id(args.run_id) is None:
        return _fail(f"--run-id {args.run_id!r} is not a valid run_id")
    run_url = _run_url(args, env, repository)
    if run_url is None:
        return _fail("outside GitHub Actions a pass is a local one: use --once")

    identity = f"{slug}[bot]"
    try:
        ports = ports_factory(manifest, identity) if ports_factory else _real_ports(env, repository)
    except FatalPublicationError as exc:
        return _fail(str(exc))
    if args.dry_run:
        store, tracker = dry_run_overlay(ports.store, ports.tracker, repository, identity)
        ports = Ports(ports.reader, store, tracker)
        print("dry run: nothing is written to GitHub", file=sys.stderr)
    print(f"acting identity: {identity} (GitHub App installation tokens only; no personal identity is used)", file=sys.stderr)

    config = SweepConfig(
        manifest=manifest, identity=identity, run_url=run_url, local_once=args.once,
        only_run_id=args.run_id, accept_unattributed=args.accept_unattributed,
    )
    report = run_sweep(ports, config)
    for outcome in report.outcomes:
        if outcome.status in ("refused", "failed"):
            print(f"{outcome.status}: {outcome.ref}: [{outcome.gate or 'step'}] {outcome.detail}", file=sys.stderr)
    if report.aborted:
        print(f"aborted: {report.aborted}", file=sys.stderr)
    print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    return 0 if report.ok else 1
