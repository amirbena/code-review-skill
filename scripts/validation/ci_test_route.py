#!/usr/bin/env python3
"""Route a change set to the DOCS, FAST, or FULL validation tier (CI and local).

FULL is the default. FAST omits only `tests.integration.*`; DOCS runs only the
static documentation validations. See policies/validation-and-clean-exit.md.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Sequence

DOCS = "docs"
FAST = "fast"
FULL = "full"
TIER_ORDER = (DOCS, FAST, FULL)

PURE_DOCS = "PURE_DOCS"
CONSUMED_DOCS = "CONSUMED_DOCS"
FAST_ALLOWLIST = "FAST_ALLOWLIST"
MIXED = "MIXED"
UNKNOWN = "UNKNOWN"

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

# A docs path is pure only when no file under these roots can read it.
CONSUMER_ROOTS = ("tests", "scripts", "runtime_platform", "benchmark", "capabilities", "distribution", ".github")
# Content-agnostic documentation scanners: the whole DOCS-tier test set. They may
# enumerate docs/ without making every doc "consumed".
DOCS_SCANNER_MODULES = (
    "tests.policy.governance.test_forbidden_repository_terms",
    "tests.policy.governance.test_instruction_architecture",
    "tests.policy.benchmark.test_benchmark_root_migration",
    "tests.policy.review.test_shared_review_context",
    "tests.policy.review.presentation.test_senior_voice_contract_231",
)
# The router and its own tests name docs paths only as classification fixtures; they read none.
ROUTER_FILES = (
    "scripts/validation/ci_test_route.py",
    "tests/unit/governance/test_ci_test_route.py",
    "tests/unit/governance/test_change_aware_routing.py",
    "tests/policy/governance/test_ci_test_routing.py",
)
LINK_VALIDATOR = "scripts/validation/validate-markdown-links.py"
# Files that enumerate tracked or Markdown trees but were reviewed as never reading docs/ content.
# Any other tree enumerator makes every docs path unverified until it is registered or listed here.
REVIEWED_NON_DOCS_ENUMERATORS = frozenset(
    {
        "scripts/release/release_lib/gitgh.py",
        "runtime_platform/benchmark/reference/benchmark_runner.py",
        "runtime_platform/benchmark/scripts/build_benchmark_index.py",
        "scripts/packaging/package_domain/tree.py",
        "scripts/skill_metadata/links.py",
        LINK_VALIDATOR,
        "tests/unit/governance/test_validate_markdown_links.py",
        "tests/repository/test_gitignore.py",
        "tests/unit/review/test_staged_fingerprint.py",
        "tests/policy/review/test_latency_optimizations_docs.py",
        "tests/unit/review/findings/test_structured_output_contract.py",
        "tests/policy/review/presentation/test_github_pr_review_output_tightening_223.py",
        "tests/policy/review/stacked_pr/test_stacked_pr_review_docs.py",
        "tests/policy/review/stateful_review/test_reviewed_sha_state_docs.py",
        "tests/integration/packaging/test_distribution_consumer_install.py",
    }
)

_LITERAL_REF = re.compile(r"(?<!\w)docs/([A-Za-z0-9_.\-/*{}$<>]*)")
_JOINED_REF = re.compile(
    r"""(?:/\s*|(?<![=!<>])=\s*|(?:Path|joinpath|join)\((?:[^()]*,)?\s*)["']docs["']((?:\s*[/,]\s*["'][^"']*["'])*)"""
)
_TREE_READER = re.compile(
    r"""\bREPO_ROOT\.(?:rglob|glob|iterdir)\(|ls-files|tracked_markdown_files|os\.walk\(\s*REPO_ROOT"""
    r"""|\.rglob\(\s*["'][^"']*\.md["']|\.glob\(\s*["']\*\*"""
)
_QUOTED = re.compile(r"""["']([^"']*)["']""")
_DYNAMIC = re.compile(r"[*{}$<>]")


@dataclass(frozen=True)
class Route:
    tier: str
    reason: str
    first_full_path: str | None = None
    change_class: str = UNKNOWN


@dataclass(frozen=True)
class ConsumerIndex:
    refs: frozenset[tuple[str, ...]]
    wildcard_files: tuple[str, ...]
    scanned: int
    unreadable: tuple[str, ...] = ()


def is_fast_path(path: str) -> bool:
    return path in FAST_FILES or any(path.startswith(d) and len(path) > len(d) for d in FAST_DIRS)


def is_doc_candidate(path: str) -> bool:
    # Exact, normalized `docs/**/*.md` only; anything odd is never a pure-docs candidate.
    parts = path.split("/")
    return (
        parts[0] == "docs"
        and len(parts) > 1
        and path.endswith(".md")
        and all(p not in ("", ".", "..") and "\\" not in p for p in parts)
    )


def _scan_text(text: str) -> tuple[set[tuple[str, ...]], bool, bool]:
    """Return (resolved docs refs, unresolvable docs access, repo-tree enumeration)."""
    refs: set[tuple[str, ...]] = set()
    unresolved = False
    for match in _LITERAL_REF.finditer(text):
        kept: list[str] = []
        dynamic = False
        for part in match.group(1).split("/"):
            if part and _DYNAMIC.search(part):
                dynamic = True
                break
            if part:
                kept.append(part)
        if kept:
            refs.add(tuple(kept))
        elif dynamic:
            unresolved = True
    for match in _JOINED_REF.finditer(text):
        kept = []
        for part in _QUOTED.findall(match.group(1)):
            if not part or _DYNAMIC.search(part):
                break
            kept.append(part)
        if kept:
            refs.add(tuple(kept))
        else:
            unresolved = True
    return refs, unresolved, bool(_TREE_READER.search(text))


def _module_path(module: str) -> str:
    return module.replace(".", "/") + ".py"


def consumer_index(tree: Path) -> ConsumerIndex:
    out = subprocess.run(
        ["git", "-C", str(tree), "ls-files", "-z", "--", *CONSUMER_ROOTS], capture_output=True, check=True
    ).stdout
    refs: set[tuple[str, ...]] = set()
    wildcard_files: list[str] = []
    unreadable: list[str] = []
    scanners = {_module_path(m) for m in DOCS_SCANNER_MODULES}
    scanned = 0
    for rel in out.decode("utf-8", "surrogateescape").split("\0"):
        if not rel or rel.endswith(".md") or rel in ROUTER_FILES:
            continue
        try:
            text = (tree / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            unreadable.append(rel)
            continue
        scanned += 1
        found, unresolved, tree_reader = _scan_text(text)
        refs |= found
        if rel in scanners:
            continue
        if unresolved or (tree_reader and rel not in REVIEWED_NON_DOCS_ENUMERATORS):
            wildcard_files.append(rel)
    return ConsumerIndex(frozenset(refs), tuple(sorted(wildcard_files)), scanned, tuple(sorted(unreadable)))


def is_consumed(path: str, index: ConsumerIndex) -> bool:
    parts = tuple(path.split("/")[1:])
    return any(parts[: len(ref)] == ref for ref in index.refs)


def _index_problem(index: ConsumerIndex | None) -> str | None:
    if index is None:
        return "no consumer scan available"
    if index.scanned == 0:
        return "consumer scan found no files"
    if index.unreadable:
        return f"a consumer file could not be read ({index.unreadable[0]})"
    if index.wildcard_files:
        return f"a file reads docs/ in a way the scan cannot resolve ({index.wildcard_files[0]})"
    return None


def _path_tier(path: str, index: ConsumerIndex | None) -> tuple[str, str]:
    """Return (kind, tier) for one changed path."""
    if is_doc_candidate(path):
        if _index_problem(index) is not None:
            return "unverified", FULL
        return ("consumed", FAST) if is_consumed(path, index) else ("pure", DOCS)
    if is_fast_path(path):
        return "allowlist", FAST
    return "other", FULL


def classify(paths: Sequence[str], index: ConsumerIndex | None = None) -> Route:
    if not paths:
        return Route(FULL, "empty change set")
    kinds = [(path, *_path_tier(path, index)) for path in paths]
    present = {kind for _, kind, _ in kinds}
    first_full = next((p for p, _, tier in kinds if tier == FULL), None)
    has_docs = bool(present & {"pure", "consumed", "unverified"})
    if first_full is not None:
        reason = "a changed path is not a documentation file and not on the FAST allowlist"
        if "unverified" in present and "other" not in present:
            reason = _index_problem(index) or reason
        return Route(FULL, reason, first_full, MIXED if has_docs and "other" in present else UNKNOWN)
    if present == {"pure"}:
        return Route(DOCS, "every changed path is a documentation file no test or script consumes", None, PURE_DOCS)
    worst = next(p for p, _, tier in kinds if tier == FAST)
    if present <= {"pure", "consumed"}:
        return Route(FAST, "a changed documentation file is consumed by tests or scripts", worst, CONSUMED_DOCS)
    if has_docs:
        return Route(FAST, "documentation changes are mixed with FAST-allowlisted paths", worst, MIXED)
    return Route(FAST, "every changed path is on the FAST allowlist", None, FAST_ALLOWLIST)


def changed_paths(repo: Path, base: str, head: str) -> list[str]:
    # Three-dot: the PR's own changes since the merge-base; renames split into D + A.
    out = subprocess.run(
        ["git", "-C", str(repo), "diff", "--name-only", "--no-renames", "-z", f"{base}...{head}"],
        capture_output=True,
        check=True,
    ).stdout
    return [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]


def route(event_name: str, repo: Path, base: str | None, head: str | None, tree: Path | None = None) -> Route:
    if event_name != "pull_request":
        return Route(FULL, f"non-pull_request event ({event_name or 'unknown'})")
    if not base or not head:
        return Route(FULL, "missing base or head SHA")
    try:
        paths = changed_paths(repo, base, head)
    except (OSError, subprocess.CalledProcessError):
        return Route(FULL, "git diff failed")
    return classify(paths, _index_or_none(tree))


def _index_or_none(tree: Path | None) -> ConsumerIndex | None:
    if tree is None:
        return None
    try:
        return consumer_index(tree)
    except (OSError, subprocess.CalledProcessError):
        return None


def safe_route(event_name: str, repo: Path, base: str | None, head: str | None, tree: Path | None = None) -> Route:
    try:
        result = route(event_name, repo, base, head, tree)
    except Exception as exc:  # noqa: BLE001 - any router failure must resolve to FULL
        return Route(FULL, f"router exception ({type(exc).__name__})")
    if result.tier not in TIER_ORDER:
        return Route(FULL, f"unrecognized tier {result.tier!r}")
    return result


def summary_markdown(result: Route) -> str:
    lines = [
        "### CI test route",
        "",
        f"- Tier: **{result.tier.upper()}**",
        f"- Class: {result.change_class}",
        f"- Reason: {result.reason}",
    ]
    if result.first_full_path is not None:
        lines.append(f"- First path that forced {result.tier.upper()}: `{result.first_full_path}`")
    return "\n".join(lines) + "\n"


RUN_COMMANDS = {
    DOCS: "python3 scripts/validation/ci_test_route.py run-docs",
    FAST: "python3 scripts/validation/ci_test_route.py run-fast",
    FULL: "python3 -m unittest discover -s tests -t .",
}


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
    tree = Path(args.tree) if args.tree else None
    result = safe_route(args.event_name, Path(args.repo), args.base, args.head, tree)
    print(summary_markdown(result), end="")
    _append(args.step_summary, summary_markdown(result))
    # Last, so a failure anywhere above leaves the tier unset, which runs FULL.
    _append(args.github_output, f"tier={result.tier}\nclass={result.change_class}\n")
    return 0


def _cmd_classify(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    result = safe_route("pull_request", repo, args.base, args.head, repo)
    print(summary_markdown(result), end="")
    print(f"- Run: `{RUN_COMMANDS[result.tier]}`")
    return 0


def _cmd_run_fast(args: argparse.Namespace) -> int:
    suite = fast_suite()
    if args.list:
        for test in _iter_tests(suite):
            print(test.id())
        return 0
    result = unittest.TextTestRunner().run(suite)
    return 0 if result.wasSuccessful() and result.testsRun > 0 else 1


def _cmd_run_docs(args: argparse.Namespace) -> int:
    root = Path(args.repo).resolve()
    if args.list:
        print(LINK_VALIDATOR)
        print(*DOCS_SCANNER_MODULES, sep="\n")
        return 0
    os.chdir(root)
    sys.path.insert(0, str(root))
    links = subprocess.run([sys.executable, LINK_VALIDATOR, "--repo-root", str(root)], check=False)
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromNames(DOCS_SCANNER_MODULES))
    return 0 if links.returncode == 0 and result.wasSuccessful() and result.testsRun > 0 else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    route_cmd = commands.add_parser("route", help="classify the change set and emit tier=docs|fast|full")
    route_cmd.add_argument("--event-name", required=True)
    route_cmd.add_argument("--base")
    route_cmd.add_argument("--head")
    route_cmd.add_argument("--repo", default=".")
    route_cmd.add_argument("--tree", help="checkout whose tests and scripts are scanned for docs consumers")
    route_cmd.add_argument("--github-output", default=os.environ.get("GITHUB_OUTPUT"))
    route_cmd.add_argument("--step-summary", default=os.environ.get("GITHUB_STEP_SUMMARY"))
    route_cmd.set_defaults(func=_cmd_route)

    fast_cmd = commands.add_parser("run-fast", help="run tests/ from the repository root minus tests.integration.*")
    fast_cmd.add_argument("--list", action="store_true", help="print the FAST test IDs instead of running them")
    fast_cmd.set_defaults(func=_cmd_run_fast)

    docs_cmd = commands.add_parser("run-docs", help="run only the static documentation validations")
    docs_cmd.add_argument("--repo", default=".")
    docs_cmd.add_argument("--list", action="store_true", help="print the DOCS-tier validations instead of running them")
    docs_cmd.set_defaults(func=_cmd_run_docs)

    classify_cmd = commands.add_parser("classify", help="locally print the class, tier, reason, and command CI would use")
    classify_cmd.add_argument("--base", default="origin/main")
    classify_cmd.add_argument("--head", default="HEAD")
    classify_cmd.add_argument("--repo", default=".")
    classify_cmd.set_defaults(func=_cmd_classify)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
