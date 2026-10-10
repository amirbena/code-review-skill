"""Command line for the publication CLI: `sweep` and `watchdog`, with `--once` for a local or disaster-recovery pass."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Mapping, NoReturn, Sequence

from runtime_platform.benchmark.publisher import activity_probe, github_api
from runtime_platform.benchmark.publisher.memory import dry_run_overlay
from runtime_platform.benchmark.publisher.ports import FatalPublicationError
from runtime_platform.benchmark.publisher.public_log import PublicLog
from runtime_platform.benchmark.publisher.model import SCOPE_ALL, Ports, SweepConfig, WatchdogConfig
from runtime_platform.benchmark.publisher.sweep import run_sweep
from runtime_platform.benchmark.publisher.watchdog import run_watchdog
from runtime_platform.benchmark.scripts.benchmark_evidence_config import validate_evidence_block
from runtime_platform.benchmark.scripts.benchmark_result import parse_run_id
from runtime_platform.benchmark.scripts.benchmark_schedule_manifest import MANIFEST_PATH, ManifestError, load_manifest

PortsFactory = Callable[[Mapping[str, Any], str], Ports]
Clock = Callable[[], datetime]
EXIT_USAGE = 2


class _FixedErrorParser(argparse.ArgumentParser):
    """A usage error is a fixed code: argparse would echo the offending argument, and the phase is not yet known."""

    def error(self, message: str) -> NoReturn:
        PublicLog(None).error(message, "usage")
        raise SystemExit(EXIT_USAGE)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = _FixedErrorParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sweep = sub.add_parser("sweep", help="Publish every unpublished sealed result, oldest first.")
    sweep.add_argument("--once", action="store_true", help="A local or disaster-recovery pass outside GitHub Actions.")
    sweep.add_argument("--dry-run", action="store_true", help="Read and plan only: every write lands in memory.")
    sweep.add_argument("--run-id", help="Publish only this run_id.")
    sweep.add_argument(
        "--accept-unattributed", action="store_true",
        help="With --run-id: accept the run when the server cannot attribute its ref (never when it contradicts).",
    )
    sweep.add_argument("--run-url", help="URL recorded in receipts (default: the Actions run).")
    watchdog = sub.add_parser("watchdog", help="Open or close missed-run issues and refresh the health-status comment.")
    watchdog.add_argument("--once", action="store_true", help="A local or disaster-recovery pass outside GitHub Actions.")
    watchdog.add_argument("--dry-run", action="store_true", help="Read and plan only: every write lands in memory.")
    watchdog.add_argument("--sweep-report", type=Path, help="The `sweep` report (JSON): an ok report marks the sweep successful now.")
    resolve = sub.add_parser("resolve-evidence", help="Print `name=<evidence repository name>` for the workflow's token minting.")
    resolve.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    resolve.add_argument("--owner", required=True, help="The workflow's repository owner; the evidence repository must belong to it.")
    probe = sub.add_parser("probe-activity", help="Read-only X3 probe of origin attestation on the private evidence repository.")
    probe.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    for command in (sweep, watchdog):
        command.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
        command.add_argument("--app-slug", help="The publication App's slug (default: BENCHMARK_APP_SLUG).")
    return parser


def evidence_repository(manifest: Mapping[str, Any]) -> str:
    """The one repository every publisher request addresses; never the workflow's repository or an env value."""
    return manifest["evidence"]["repository"]


def _fail(message: str, code: str, log: PublicLog | None = None) -> int:
    """Every error line goes through the public-log writer: the message in `pre_cutover`, only `code` in `private`."""
    (log or PublicLog(None)).error(message, code)
    return EXIT_USAGE


def _in_actions(env: Mapping[str, str]) -> bool:
    return env.get("GITHUB_ACTIONS") == "true" and bool(env.get("GITHUB_RUN_ID"))


def _run_url(args: argparse.Namespace, env: Mapping[str, str], repository: str) -> str | None:
    if args.run_url:
        return args.run_url
    if _in_actions(env):
        server = env.get("GITHUB_SERVER_URL", "https://github.com")
        return f"{server}/{env.get('GITHUB_REPOSITORY', repository)}/actions/runs/{env['GITHUB_RUN_ID']}"
    return f"https://github.com/{repository}" if args.once else None


def _real_ports(env: Mapping[str, str], repository: str, *, read_only_history: bool = False) -> Ports:
    """The watchdog never writes history, so with a read token its history client carries that token alone."""
    read_token = env.get("BENCHMARK_READ_TOKEN")
    contents_name, contents_value = "BENCHMARK_CONTENTS_TOKEN", env.get("BENCHMARK_CONTENTS_TOKEN")
    if read_only_history and read_token:
        contents_name, contents_value = "BENCHMARK_READ_TOKEN", read_token
    contents = github_api.require_installation_token(contents_name, contents_value)
    issues = github_api.require_installation_token("BENCHMARK_ISSUES_TOKEN", env.get("BENCHMARK_ISSUES_TOKEN"))
    read = github_api.require_installation_token("BENCHMARK_READ_TOKEN", read_token or contents)
    return Ports(
        reader=github_api.GitHubHandoffReader(github_api.GitHubClient(read), repository),
        store=github_api.GitHubHistoryStore(github_api.GitHubClient(contents), repository),
        tracker=github_api.GitHubIssueTracker(github_api.GitHubClient(issues), repository),
    )


def _open_ports(
    args: argparse.Namespace, env: Mapping[str, str], manifest: Mapping[str, Any], identity: str, ports_factory: PortsFactory | None,
    log: PublicLog,
) -> Ports | int:
    """The ports for one pass (dry-run overlaid), or the usage-error exit code."""
    repository = evidence_repository(manifest)
    try:
        if ports_factory:
            ports = ports_factory(manifest, identity)
        else:
            ports = _real_ports(env, repository, read_only_history=args.command == "watchdog")
    except FatalPublicationError as exc:
        return _fail(str(exc), "evidence-unavailable", log)
    if args.dry_run:
        store, tracker = dry_run_overlay(ports.store, ports.tracker, repository, identity)
        ports = Ports(ports.reader, store, tracker)
        log.note("dry run: nothing is written to GitHub")
    log.acting_identity(identity)
    return ports


def _sweep(
    args: argparse.Namespace, manifest: Mapping[str, Any], identity: str, ports: Ports, run_url: str, clock: Clock | None, log: PublicLog
) -> int:
    config = SweepConfig(
        manifest=manifest, identity=identity, run_url=run_url, local_once=args.once,
        only_run_id=args.run_id, accept_unattributed=args.accept_unattributed, dry_run=args.dry_run, **({"clock": clock} if clock else {}),
    )
    report = run_sweep(ports, config)
    log.sweep(report)
    return 0 if report.ok else 1


def _sweep_succeeded(path: Path | None) -> bool | str:
    """Whether the given `sweep` report shows a successful full, real pass, or an error message.

    A `--run-id` or `--dry-run` pass, or a report that does not say which it was, never counts.
    """
    if path is None:
        return False
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return f"cannot read --sweep-report {path}: {exc}"
    if not isinstance(report, dict):
        return f"--sweep-report {path} is not a JSON object"
    return report.get("ok") is True and report.get("aborted") is None and report.get("scope") == SCOPE_ALL and report.get("dry_run") is False


def _watchdog(manifest: Mapping[str, Any], identity: str, ports: Ports, succeeded: bool, clock: Clock | None, log: PublicLog) -> int:
    config = WatchdogConfig(manifest=manifest, identity=identity, sweep_succeeded=succeeded, **({"clock": clock} if clock else {}))
    report = run_watchdog(ports, config)
    log.watchdog(report)
    return 0 if report.ok else 1


def main(
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    ports_factory: PortsFactory | None = None,
    clock: Clock | None = None,
    probe_reader: activity_probe.ReaderFactory | None = None,
) -> int:
    args = build_arg_parser().parse_args(argv)
    env = os.environ if env is None else env
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        return _fail(str(exc), "invalid-manifest")
    except Exception:  # noqa: BLE001 - no phase is known yet: an unreadable manifest is a fixed code, never a traceback
        return _fail("the manifest could not be read", "invalid-manifest")
    log = PublicLog(manifest)
    errors = validate_evidence_block(manifest.get("evidence"), manifest.get("repository"))
    if errors:
        return _fail(f"invalid evidence destination: {errors[0]}", "invalid-evidence-destination", log)
    try:
        return _run(args, env, manifest, log, ports_factory, clock, probe_reader)
    except Exception:  # noqa: BLE001 - in `private` an uncaught exception reaches the public log only as a fixed code (F13)
        if not log.private:
            raise
        log.internal_error()
        return 1


def _probe(env: Mapping[str, str], manifest: Mapping[str, Any], log: PublicLog, reader_factory: activity_probe.ReaderFactory | None) -> int:
    """Only the read token is consulted; the manifest supplies the allowlist and nothing else."""
    try:
        token = github_api.require_installation_token("BENCHMARK_READ_TOKEN", env.get("BENCHMARK_READ_TOKEN"))
    except FatalPublicationError as exc:
        return _fail(str(exc), "evidence-unavailable", log)
    reader = (reader_factory or activity_probe.GitHubProbeReader)(token)
    result = activity_probe.run_probe(reader, manifest["publication"]["pusher_allowlist"])
    log.probe(result)
    return 0 if result.passed else 1


def _run(
    args: argparse.Namespace, env: Mapping[str, str], manifest: Mapping[str, Any], log: PublicLog,
    ports_factory: PortsFactory | None, clock: Clock | None, probe_reader: activity_probe.ReaderFactory | None = None,
) -> int:
    if args.command == "resolve-evidence":
        owner, name = evidence_repository(manifest).split("/")
        if owner.lower() != args.owner.lower():
            return _fail("the evidence repository must belong to the workflow's owner", "usage", log)
        print(f"name={name}")
        return 0
    if args.command == "probe-activity":
        return _probe(env, manifest, log, probe_reader)
    slug = args.app_slug or env.get("BENCHMARK_APP_SLUG")
    if not slug:
        return _fail("the App slug is required (--app-slug or BENCHMARK_APP_SLUG): the acting identity must be known", "app-slug-required", log)
    succeeded: bool | str = False
    run_url: str | None = None
    if args.command == "sweep":
        if args.accept_unattributed and not args.run_id:
            return _fail("--accept-unattributed requires --run-id", "usage", log)
        if args.run_id and parse_run_id(args.run_id) is None:
            return _fail(f"--run-id {args.run_id!r} is not a valid run_id", "usage", log)
        run_url = _run_url(args, env, manifest.get("repository", ""))
        if run_url is None:
            return _fail("outside GitHub Actions a pass is a local one: use --once", "usage", log)
    else:
        succeeded = _sweep_succeeded(args.sweep_report)
        if isinstance(succeeded, str):
            return _fail(succeeded, "invalid-sweep-report", log)
        if not args.once and not _in_actions(env):
            return _fail("outside GitHub Actions a pass is a local one: use --once", "usage", log)

    identity = f"{slug}[bot]"
    ports = _open_ports(args, env, manifest, identity, ports_factory, log)
    if isinstance(ports, int):
        return ports
    if run_url is not None:
        return _sweep(args, manifest, identity, ports, run_url, clock, log)
    return _watchdog(manifest, identity, ports, bool(succeeded), clock, log)
