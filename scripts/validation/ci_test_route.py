#!/usr/bin/env python3
"""Route a CI run to the FAST or FULL test tier from its changed paths.

FULL is the default. FAST omits only `tests.integration.*`, and only when every
changed path is on the allowlist below; see policies/validation-and-clean-exit.md.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

FAST = "fast"
FULL = "full"

# Exact, case-sensitive matches. Each entry needs positive evidence that no
# integration test copies, reads, or packages it (issue #533).
FAST_FILES = frozenset(
    {
        ".gitignore",
        "AGENTS.md",
        "CLAUDE.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "README.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/AUTOMATION.md",
    }
)
FAST_DIRS = ("policies/", ".github/ISSUE_TEMPLATE/")

INTEGRATION_PREFIX = "tests.integration."


@dataclass(frozen=True)
class Route:
    tier: str
    reason: str
    first_full_path: str | None = None


def is_fast_path(path: str) -> bool:
    return path in FAST_FILES or any(path.startswith(d) and len(path) > len(d) for d in FAST_DIRS)


def classify(paths: Sequence[str]) -> Route:
    if not paths:
        return Route(FULL, "empty change set")
    for path in paths:
        if not is_fast_path(path):
            return Route(FULL, "a changed path is not on the FAST allowlist", path)
    return Route(FAST, "every changed path is on the FAST allowlist")


def changed_paths(repo: Path, base: str, head: str) -> list[str]:
    # Three-dot: the PR's own changes since the merge-base; renames split into D + A.
    out = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", "--no-renames", "-z", f"{base}...{head}"],
        capture_output=True,
        check=True,
    ).stdout
    return [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]


def route(event_name: str, repo: Path, base: str | None, head: str | None) -> Route:
    if event_name != "pull_request":
        return Route(FULL, f"non-pull_request event ({event_name or 'unknown'})")
    if not base or not head:
        return Route(FULL, "missing base or head SHA")
    try:
        paths = changed_paths(repo, base, head)
    except (OSError, subprocess.CalledProcessError):
        return Route(FULL, "git diff failed")
    return classify(paths)


def safe_route(event_name: str, repo: Path, base: str | None, head: str | None) -> Route:
    try:
        result = route(event_name, repo, base, head)
    except Exception as exc:  # noqa: BLE001 - any router failure must resolve to FULL
        return Route(FULL, f"router exception ({type(exc).__name__})")
    if result.tier not in (FAST, FULL):
        return Route(FULL, f"unrecognized tier {result.tier!r}")
    return result


def summary_markdown(result: Route) -> str:
    lines = ["### CI test route", "", f"- Tier: **{result.tier.upper()}**", f"- Reason: {result.reason}"]
    if result.first_full_path is not None:
        lines.append(f"- First path that forced FULL: `{result.first_full_path}`")
    return "\n".join(lines) + "\n"


def _append(path: str | None, text: str) -> None:
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(text)


def _iter_tests(suite: unittest.TestSuite) -> Iterator[unittest.TestCase]:
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _iter_tests(item)
        else:
            yield item


def fast_suite(start_dir: str | Path = "tests", top_level_dir: str | Path = ".") -> unittest.TestSuite:
    # Same discovery as FULL, minus exactly the integration tests.
    discovered = unittest.defaultTestLoader.discover(str(start_dir), top_level_dir=str(top_level_dir))
    return unittest.TestSuite(t for t in _iter_tests(discovered) if not t.id().startswith(INTEGRATION_PREFIX))


def _cmd_route(args: argparse.Namespace) -> int:
    result = safe_route(args.event_name, Path(args.repo), args.base, args.head)
    print(summary_markdown(result), end="")
    _append(args.github_output, f"tier={result.tier}\n")
    _append(args.step_summary, summary_markdown(result))
    return 0


def _cmd_run_fast(args: argparse.Namespace) -> int:
    suite = fast_suite()
    if args.list:
        for test in _iter_tests(suite):
            print(test.id())
        return 0
    result = unittest.TextTestRunner().run(suite)
    return 0 if result.wasSuccessful() and result.testsRun > 0 else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    route_cmd = commands.add_parser("route", help="classify the change set and emit tier=fast|full")
    route_cmd.add_argument("--event-name", required=True)
    route_cmd.add_argument("--base")
    route_cmd.add_argument("--head")
    route_cmd.add_argument("--repo", default=".")
    route_cmd.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    route_cmd.add_argument("--step-summary", default=os.environ.get("GITHUB_STEP_SUMMARY"))
    route_cmd.set_defaults(func=_cmd_route)

    fast_cmd = commands.add_parser("run-fast", help="run tests/ from the repository root minus tests.integration.*")
    fast_cmd.add_argument("--list", action="store_true", help="print the FAST test IDs instead of running them")
    fast_cmd.set_defaults(func=_cmd_run_fast)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
