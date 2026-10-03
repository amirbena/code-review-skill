#!/usr/bin/env python3
"""Route a change set to the DOCS, PARTIAL, FAST, or FULL validation tier (CI and local).

FULL is the default and the fallback. FAST omits only `tests.integration.*`;
DOCS runs only the static documentation validations; PARTIAL runs an explicit
set of test modules derived from a static test-impact graph. Unknown or
ambiguous impact always fails upward. See policies/validation-and-clean-exit.md.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import re
import subprocess
import sys
import unittest
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

DOCS = "docs"
PARTIAL = "partial"
FAST = "fast"
FULL = "full"
TIER_ORDER = (DOCS, PARTIAL, FAST, FULL)

PURE_DOCS = "PURE_DOCS"
CONSUMED_DOCS = "CONSUMED_DOCS"
FAST_ALLOWLIST = "FAST_ALLOWLIST"
PARTIAL_TESTS = "PARTIAL_TESTS"
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
    "tests.policy.governance.test_canonical_homes",
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
    "tests/unit/governance/test_partial_routing.py",
    "tests/policy/governance/test_ci_test_routing.py",
)
# Tree-guard tests over tests/ (layout and routing tripwires). An explicit
# registry, added to every PARTIAL set; a missing one fails upward to FULL.
TREE_GUARD_MODULES = (
    "tests.repository.test_review_bucket_layout",
    "tests.repository.test_scripts_layout",
    "tests.policy.governance.test_ci_test_routing",
    "tests.unit.governance.test_ci_test_route",
    "tests.unit.governance.test_change_aware_routing",
    "tests.unit.governance.test_partial_routing",
)
LINK_VALIDATOR = "scripts/validation/validate-markdown-links.py"
# Files that enumerate trees but were reviewed: they enumerate non-docs roots, or only docs dirs already indexed by a literal ref.
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
        "scripts/release/release_lib/distribution.py",
        "scripts/sandbox/process_exec.py",
        "scripts/sandbox/workspace.py",
        "tests/integration/packaging/_shared.py",
        "tests/integration/packaging/test_hidden_runtime_dependency.py",
        "tests/integration/packaging/test_ordinary_packaging_version.py",
        "tests/integration/packaging/test_skill_tree_output.py",
        "tests/policy/benchmark/test_benchmark_publish_workflow.py",
        "tests/policy/benchmark/test_execution_no_github_writes.py",
        "tests/policy/review/findings/test_review_result_docs.py",
        "tests/policy/review/presentation/test_severity_description_option_275.py",
        "tests/policy/review/test_review_base_policy_wiring.py",
        "tests/policy/review/test_review_scope_core_wiring.py",
        "tests/repository/test_review_bucket_layout.py",
        "tests/repository/test_scripts_layout.py",
        "tests/unit/benchmark/test_benchmark_runner.py",
        "tests/unit/benchmark/test_benchmark_runner_multi_repo.py",
        "tests/unit/benchmark/test_benchmark_seal.py",
        "tests/unit/benchmark/test_run_benchmark_routine.py",
        "tests/unit/release/test_distribution.py",
    }
)

_LITERAL_REF = re.compile(r"(?<!\w)docs/([A-Za-z0-9_.\-/*{}$<>]*)")
_JOINED_REF = re.compile(
    r"""(?:/\s*|(?<![=!<>])=\s*|(?:Path|joinpath|join)\((?:[^()]*,)?\s*)["']docs["']((?:\s*[/,]\s*["'][^"']*["'])*)"""
)
_TREE_READER = re.compile(
    r"""\b(?:r|i)?glob\(\s*(?!["'][^"']*\.(?:ya?ml|json|py|sh|ps1|toml|txt|csv)["'])"""
    r"""|iterdir|(?<!ast)\.walk\(|os\.walk|scandir|listdir|ls-files|ls-tree|git["',\s]+grep|tracked_markdown_files"""
)
_QUOTED = re.compile(r"""["']([^"']*)["']""")
_DYNAMIC = re.compile(r"[*{}$<>]")


@dataclass(frozen=True)
class Route:
    tier: str
    reason: str
    first_full_path: str | None = None
    change_class: str = UNKNOWN
    # PARTIAL: the whole module set to run. FAST: only the extra integration modules FAST would drop.
    modules: tuple[str, ...] = ()
    docs_links: bool = False


@dataclass(frozen=True)
class ConsumerIndex:
    refs: frozenset[tuple[str, ...]]
    wildcard_files: tuple[str, ...]
    scanned: int
    unreadable: tuple[str, ...] = ()


# --- Test-impact graph (PARTIAL tier) -----------------------------------------
# Derived by static scan of `tests/`; nothing here is declared by hand except the
# registered companions above. A consumer is a test file that imports another or
# reads it by literal or directory path. Anything the scan cannot resolve fails
# upward to FULL.

# Directories a test may legitimately load code from that are not under tests/.
NON_TEST_ROOTS = frozenset(
    {"scripts", "runtime_platform", "benchmark", "capabilities", "distribution", "skills", "shared", "docs", ".github", "policies"}
)
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
_MODULE_ID = re.compile(r"tests(\.[A-Za-z_][A-Za-z0-9_]*)+$")
_STR_REF = re.compile(r"(?<![A-Za-z0-9_])tests/([^\s\"'`)\]>,;:|]*)")
_DOTTED_REF = re.compile(r"(?<![\w.])tests((?:\.[A-Za-z_]\w*)+)")
_GLOB_CHARS = re.compile(r"[*?\[\]{}$<>]")
_PATH_CALLS = frozenset({"Path", "PurePath", "PosixPath", "PurePosixPath", "WindowsPath"})
_PASSTHROUGH_CALLS = frozenset({"resolve", "absolute", "expanduser", "as_posix"})
_PASSTHROUGH_FUNCS = frozenset({"str", "fspath", "realpath", "abspath"})
_LOADER_CALLS = frozenset(
    {"import_module", "__import__", "spec_from_file_location", "spec_from_loader", "run_path", "run_module", "load_source", "load_module"}
)
_PATH_MUTATORS = frozenset({"insert", "append", "extend"})


@dataclass(frozen=True)
class TreeScan:
    """The `tests/` files of one tree, their dependencies, and what could not be resolved."""

    files: frozenset[str]
    deps: Mapping[str, frozenset[str]]
    dynamic: Mapping[str, str] = field(default_factory=dict)  # file -> "line N: why" for unresolvable loads/reads
    problems: tuple[str, ...] = ()


@dataclass(frozen=True)
class ImpactGraph:
    """Union of the base and head scans, so removed and added edges are both covered."""

    files: frozenset[str]
    head_files: frozenset[str]
    base_files: frozenset[str]
    deps: Mapping[str, frozenset[str]]
    dynamic: Mapping[str, str]
    problems: tuple[str, ...]
    consumers: Mapping[str, frozenset[str]]  # file -> the files that import or read it


def module_id(path: str) -> str | None:
    """`tests/a/b.py` -> `tests.a.b`; None when the path cannot be a module ID."""
    if not path.endswith(".py"):
        return None
    parts = path[:-3].split("/")
    if parts[0] != "tests" or len(parts) < 2 or not all(_IDENT.match(p) for p in parts):
        return None
    return ".".join(parts)


def is_test_module(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return name.startswith("test") and name.endswith(".py") and module_id(path) is not None


def _file_for_module(dotted: str, files: frozenset[str]) -> str | None:
    base = dotted.replace(".", "/")
    for candidate in (base + ".py", base + "/__init__.py"):
        if candidate in files:
            return candidate
    return None


def _module_chain(dotted: str, files: frozenset[str]) -> set[str]:
    # Importing `a.b.c` executes `a`, `a.b`, and `a.b.c`.
    found: set[str] = set()
    parts = dotted.split(".")
    for end in range(1, len(parts) + 1):
        file = _file_for_module(".".join(parts[:end]), files)
        if file is not None:
            found.add(file)
    return found


def _ancestor_inits(path: str, files: frozenset[str]) -> set[str]:
    parts = path.split("/")[:-1]
    return {"/".join(parts[:end] + ["__init__.py"]) for end in range(1, len(parts) + 1)} & files


def _expand(comps: Sequence[str], files: frozenset[str]) -> set[str]:
    path = "/".join(comps)
    if path in files:
        return {path}
    prefix = path + "/"
    return {f for f in files if f.startswith(prefix)}


def _truncate(comps: Iterable[str]) -> list[str]:
    kept: list[str] = []
    for comp in comps:
        if not comp or comp in (".", "..") or _GLOB_CHARS.search(comp):
            break
        kept.append(comp)
    return kept


def _up(parts: list[str | None], count: int) -> list[str | None]:
    if count > len(parts) or any(p is None for p in parts[len(parts) - count :]):
        return [None]
    return parts[: len(parts) - count]


def _call_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_os_path(func: ast.Attribute) -> bool:
    return isinstance(func.value, ast.Attribute) and func.value.attr == "path"


def _parts(node: ast.AST, here: list[str]) -> list[str | None]:
    """Path components of an expression; None marks an opaque or dynamic component."""
    if isinstance(node, ast.Constant):
        return [node.value] if isinstance(node.value, str) else [None]
    if isinstance(node, ast.Name):
        return list(here) if node.id == "__file__" else [None]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _parts(node.left, here) + _parts(node.right, here)
    if isinstance(node, ast.Call):
        name = _call_name(node.func)
        joins = name == "join" and isinstance(node.func, ast.Attribute) and _is_os_path(node.func)
        if name in _PATH_CALLS or joins:
            out: list[str | None] = []
            for arg in node.args:
                out += _parts(arg, here)
            return out
        if name in _PASSTHROUGH_FUNCS and len(node.args) == 1:
            return _parts(node.args[0], here)
        if name == "dirname" and len(node.args) == 1:
            return _up(_parts(node.args[0], here), 1)
        if isinstance(node.func, ast.Attribute):
            if name == "joinpath":
                out = _parts(node.func.value, here)
                for arg in node.args:
                    out += _parts(arg, here)
                return out
            if name in _PASSTHROUGH_CALLS:
                return _parts(node.func.value, here)
        return [None]
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        return _up(_parts(node.value, here), 1)
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "parents"
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, int)
    ):
        return _up(_parts(node.value.value, here), node.slice.value + 1)
    return [None]


def _path_children(node: ast.AST) -> list[ast.AST] | None:
    """The operands of a path-building node, or None when the node does not build a path.

    Only these operands are folded into the node's path; everything else (an argument of an
    unrelated call, say) is evaluated on its own so no `tests/` read is hidden inside it.
    """
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return [node.left, node.right]
    if isinstance(node, ast.Call):
        name = _call_name(node.func)
        func = node.func
        if name in _PATH_CALLS or (name == "join" and isinstance(func, ast.Attribute) and _is_os_path(func)):
            return list(node.args)
        if name in _PASSTHROUGH_FUNCS and len(node.args) == 1 and isinstance(func, ast.Name):
            return list(node.args)
        if name == "dirname" and len(node.args) == 1:
            return list(node.args)
        if isinstance(func, ast.Attribute) and name == "joinpath":
            return [func.value, *node.args]
        if isinstance(func, ast.Attribute) and name in _PASSTHROUGH_CALLS:
            return [func.value]
        return None
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        return [node.value]
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "parents"
        and isinstance(node.slice, ast.Constant)
        and isinstance(node.slice.value, int)
    ):
        return [node.value.value]
    return None


def _tests_ref(parts: list[str | None]) -> list[str] | None:
    """Components under `tests/` that a path expression names, or None when it names none."""
    for index, part in enumerate(parts):
        if part == "tests" and all(p is None for p in parts[:index]):
            tail: list[str] = []
            for comp in parts[index:]:
                if comp is None:
                    break
                tail += comp.split("/")
            return _truncate(tail) or None
        if part is not None:
            return None
    return None


def _first_literal(parts: list[str | None]) -> str | None:
    for part in parts:
        if part is not None:
            return part.split("/", 1)[0]
    return None


def _loader_is_dynamic(node: ast.Call, here: list[str], assignments: Mapping[str, list[ast.AST]]) -> bool:
    """True unless the call provably loads from a known non-tests root or a literal module name."""
    if _call_name(node.func) in ("import_module", "__import__"):
        first = node.args[0] if node.args else None
        return not (isinstance(first, ast.Constant) and isinstance(first.value, str) and not first.value.startswith("."))
    safe = False
    for arg in [*node.args, *(kw.value for kw in node.keywords)]:
        candidates = list(assignments[arg.id]) if isinstance(arg, ast.Name) and arg.id in assignments else [arg]
        for candidate in candidates:
            parts = _parts(candidate, here)
            if _tests_ref(parts) is not None:
                return True
            if _first_literal(parts) in NON_TEST_ROOTS:
                safe = True
    return not safe


def _is_sys_path_mutation(node: ast.Call) -> bool:
    func = node.func
    return (
        isinstance(func, ast.Attribute)
        and func.attr in _PATH_MUTATORS
        and isinstance(func.value, ast.Attribute)
        and func.value.attr == "path"
    )


def _string_refs(value: str, files: frozenset[str], directories: bool = False) -> set[str]:
    """Files a string names. A directory counts only as a filesystem-call argument (`directories`):
    elsewhere it is a CLI argument, a doc link, or prose ("pytest tests/unit"), not a read."""
    found: set[str] = set()
    for match in _STR_REF.finditer(value):
        comps = _truncate(["tests", *match.group(1).rstrip(".,").split("/")])
        if len(comps) > 1:
            expanded = _expand(comps, files)
            if directories or "/".join(comps) in files:
                found |= expanded
    for match in _DOTTED_REF.finditer(value):
        found |= _module_chain("tests" + match.group(1), files)
    return found


def _has_docstring(node: ast.AST) -> bool:
    # Docstrings are prose, not reads: a "tests/policy/review/" mention in one must not make a reader of that directory.
    if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) or not node.body:
        return False
    first = node.body[0]
    return isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)


_FS_CALLS = frozenset(
    {
        "glob", "rglob", "iterdir", "listdir", "walk", "scandir", "copytree", "copy", "copyfile", "copy2", "move", "rmtree",
        "open", "read_text", "read_bytes", "exists", "is_file", "is_dir", "stat", "run", "check_output", "check_call", "call",
        "Popen", "discover", "loadTestsFromName", "loadTestsFromNames",
    }
)  # fmt: skip
_TESTS_PATH_TAIL = re.compile(r"(?:^|[\s\"'=(/])tests(?:/[\w./-]*)?$")


def _unresolved_tests_form(call: ast.Call, resolved: set[int]) -> str | None:
    """Describe a `tests` path handed to a filesystem or subprocess call outside a resolved path expression."""
    for node in ast.walk(call):
        if id(node) in resolved:
            continue
        if isinstance(node, ast.Constant) and node.value == "tests":
            return 'a bare "tests" argument to a filesystem or subprocess call'
        if isinstance(node, ast.JoinedStr):
            parts = node.values
            for index, part in enumerate(parts[:-1]):
                if (
                    isinstance(part, ast.Constant)
                    and isinstance(part.value, str)
                    and isinstance(parts[index + 1], ast.FormattedValue)
                    and _TESTS_PATH_TAIL.search(part.value)
                ):
                    return "an f-string builds a tests/ path from dynamic parts"
    return None


def _scan_python(rel: str, text: str, files: frozenset[str]) -> tuple[set[str], str | None]:
    tree = ast.parse(text)
    here = rel.split("/")
    package = here[:-1]
    deps = _ancestor_inits(rel, files)
    dynamic: str | None = None
    resolved: set[int] = set()
    assignments: dict[str, list[ast.AST]] = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            assignments[node.targets[0].id].append(node.value)
    docstrings = {id(n.body[0].value) for n in ast.walk(tree) if _has_docstring(n)}
    inner: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                deps |= _module_chain(alias.name, files)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = len(package) - (node.level - 1)
                anchor = package[:keep] if keep > 0 else []
                module = ".".join(anchor + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            if module:
                deps |= _module_chain(module, files)
                for alias in node.names:
                    deps |= _module_chain(f"{module}.{alias.name}", files)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            deps |= _string_refs(node.value, files)
        elif isinstance(node, ast.Call) and (_call_name(node.func) in _LOADER_CALLS or _is_sys_path_mutation(node)):
            if dynamic is None and _loader_is_dynamic(node, here, assignments):
                dynamic = f"line {node.lineno}: a loader or sys.path change that cannot be resolved to a known root"
        children = _path_children(node)
        if children is None:
            continue
        nested = id(node) in inner
        inner.update(id(child) for child in children)
        if nested:
            continue
        comps = _tests_ref(_parts(node, here))
        if comps:
            deps |= _expand(comps, files)
            resolved.update(id(inside) for inside in ast.walk(node))
    for node in ast.walk(tree):
        if dynamic is None and isinstance(node, ast.Call) and _call_name(node.func) in _FS_CALLS:
            reason = _unresolved_tests_form(node, resolved)
            if reason is not None:
                dynamic = f"line {node.lineno}: {reason}"
        if isinstance(node, ast.Call) and _call_name(node.func) in _FS_CALLS:
            for arg in ast.walk(node):
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and id(arg) not in docstrings:
                    deps |= _string_refs(arg.value, files, directories=True)
    deps.discard(rel)
    return deps, dynamic


def scan_tests(texts: Mapping[str, str | None]) -> TreeScan:
    """Scan one tree's `tests/` files (path -> text; None = unreadable) into a dependency map."""
    files = frozenset(texts)
    deps: dict[str, frozenset[str]] = {}
    dynamic: dict[str, str] = {}
    problems: list[str] = []
    for rel in sorted(files):
        if not rel.endswith(".py"):
            continue
        text = texts[rel]
        if text is None:
            problems.append(f"{rel}: could not be read")
            continue
        try:
            found, why_dynamic = _scan_python(rel, text, files)
        except (SyntaxError, ValueError, RecursionError) as exc:
            problems.append(f"{rel}: could not be parsed ({type(exc).__name__})")
            continue
        deps[rel] = frozenset(found)
        if why_dynamic is not None:
            dynamic[rel] = why_dynamic
    return TreeScan(files, deps, dynamic, tuple(problems))


def merge_scans(base: TreeScan, head: TreeScan) -> ImpactGraph:
    deps: dict[str, frozenset[str]] = {}
    for scan in (base, head):
        for consumer, found in scan.deps.items():
            deps[consumer] = deps.get(consumer, frozenset()) | found
    consumers: dict[str, set[str]] = defaultdict(set)
    for consumer, found in deps.items():
        for dep in found:
            consumers[dep].add(consumer)
    return ImpactGraph(
        files=base.files | head.files,
        head_files=head.files,
        base_files=base.files,
        deps=deps,
        dynamic={**base.dynamic, **head.dynamic},
        problems=tuple(sorted({*base.problems, *head.problems})),
        consumers={dep: frozenset(found) for dep, found in consumers.items()},
    )


GIT_READ_TIMEOUT = 120  # seconds; a stalled lazy blob fetch routes FULL instead of hanging the job


def _git_bytes(repo: Path, *args: str, stdin: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args], input=stdin, capture_output=True, check=True, timeout=GIT_READ_TIMEOUT
    ).stdout


def read_tests_from_tree(tree: Path) -> dict[str, str | None]:
    out = _git_bytes(tree, "ls-files", "-z", "--", "tests").decode("utf-8", "surrogateescape")
    texts: dict[str, str | None] = {}
    for rel in (r for r in out.split("\0") if r):
        if not rel.endswith(".py"):
            texts[rel] = ""
            continue
        try:
            texts[rel] = (tree / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            texts[rel] = None
    return texts


def read_tests_from_rev(repo: Path, rev: str) -> dict[str, str | None]:
    out = _git_bytes(repo, "ls-tree", "-r", "-z", "--name-only", rev, "--", "tests").decode("utf-8", "surrogateescape")
    names = [r for r in out.split("\0") if r]
    texts: dict[str, str | None] = {n: "" for n in names if not n.endswith(".py")}
    wanted = [n for n in names if n.endswith(".py")]
    request = "".join(f"{rev}:{n}\n" for n in wanted).encode("utf-8", "surrogateescape")
    blob = _git_bytes(repo, "cat-file", "--batch", stdin=request)
    cursor = 0
    for name in wanted:
        end = blob.index(b"\n", cursor)
        header = blob[cursor:end].split()
        cursor = end + 1
        if len(header) != 3 or header[1] != b"blob":
            texts[name] = None
            continue
        size = int(header[2])
        try:
            texts[name] = blob[cursor : cursor + size].decode("utf-8")
        except UnicodeDecodeError:
            texts[name] = None
        cursor += size + 1
    return texts


def build_impact_graph(repo: Path, base: str, head: str, tree: Path) -> ImpactGraph:
    try:
        base = _git_bytes(repo, "merge-base", base, head).decode().strip() or base
    except (OSError, subprocess.CalledProcessError):
        pass
    return merge_scans(scan_tests(read_tests_from_rev(repo, base)), scan_tests(read_tests_from_tree(tree)))


def affected_closure(graph: ImpactGraph, seeds: Iterable[str]) -> set[str]:
    """Every file that transitively imports or reads a seed, seeds included."""
    seen = set(seeds)
    queue = deque(seen)
    while queue:
        for consumer in graph.consumers.get(queue.popleft(), ()):
            if consumer not in seen:
                seen.add(consumer)
                queue.append(consumer)
    return seen


def all_test_modules(graph: ImpactGraph) -> set[str]:
    return {module_id(f) or "" for f in graph.head_files if is_test_module(f)}


def _graph_problem(graph: ImpactGraph | None) -> str | None:
    if graph is None:
        return "no test-impact graph available"
    if graph.problems:
        return f"the test-impact graph is incomplete ({graph.problems[0]})"
    if not graph.head_files or not graph.deps:
        return "the test-impact graph is empty"
    return None


def _normalized(path: str) -> bool:
    return all(p not in ("", ".", "..") and "\\" not in p for p in path.split("/"))


def surface_of_test_path(path: str, graph: ImpactGraph) -> tuple[set[str] | None, str]:
    """Return (affected test modules, reason); None modules means this path forces FULL."""
    if not _normalized(path) or path in ROUTER_FILES:
        return None, "the router, its registries, and their tests are always FULL"
    if path not in graph.files:
        return None, "path is not in the test-impact graph"
    parts = path.split("/")
    if len(parts) > 2 and not any(f.startswith(f"tests/{parts[1]}/") for f in graph.base_files):
        return None, "path is in a new top-level tests/ directory"
    closure = affected_closure(graph, [path])
    unresolved = sorted(closure & set(graph.dynamic))
    if unresolved:
        return None, f"a consumer loads code or reads tests/ in a form the scan cannot resolve ({unresolved[0]}, {graph.dynamic[unresolved[0]]})"
    modules = {module_id(f) or "" for f in closure if f in graph.head_files and is_test_module(f)}
    if not modules:
        return None, "no test module imports or reads it"
    return modules, "test modules that import or read the changed test path"


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


def _tests_path(path: str, graph: ImpactGraph | None) -> tuple[set[str] | None, str]:
    """Return (affected test modules, reason) for a path under tests/; None modules forces FULL."""
    if path in ROUTER_FILES:
        return surface_of_test_path(path, graph) if graph is not None else (None, "the router and its tests are always FULL")
    problem = _graph_problem(graph)
    if problem is not None or graph is None:
        return None, problem or "no test-impact graph available"
    return surface_of_test_path(path, graph)


def classify(paths: Sequence[str], index: ConsumerIndex | None = None, graph: ImpactGraph | None = None) -> Route:
    if not paths:
        return Route(FULL, "empty change set")
    kinds: list[tuple[str, str, str]] = []
    surface: set[str] = set()
    full_reasons: dict[str, str] = {}
    for path in paths:
        if path.startswith("tests/"):
            modules, reason = _tests_path(path, graph)
            if modules is None:
                kinds.append((path, "tests", FULL))
                full_reasons[path] = reason
            else:
                kinds.append((path, "tests", PARTIAL))
                surface |= modules
        else:
            kinds.append((path, *_path_tier(path, index)))
    present = {kind for _, kind, _ in kinds}
    first_full = next((p for p, _, tier in kinds if tier == FULL), None)
    has_docs = bool(present & {"pure", "consumed", "unverified"})
    if first_full is not None:
        reason = full_reasons.get(first_full) or "a changed path is not a documentation file and not on the FAST allowlist"
        if "unverified" in present and not (present & {"other", "tests"}):
            reason = _index_problem(index) or reason
        mixed = has_docs and bool(present & {"other", "tests"})
        return Route(FULL, reason, first_full, MIXED if mixed else UNKNOWN)
    covered: set[str] = set()
    if "tests" in present and graph is not None:
        covered = surface | set(TREE_GUARD_MODULES) | (set(DOCS_SCANNER_MODULES) if has_docs else set())
        everything = all_test_modules(graph)
        first_test = next(p for p, kind, _ in kinds if kind == "tests")
        if not covered <= everything:
            return Route(FULL, f"a registered companion module is missing ({sorted(covered - everything)[0]})", first_test)
        if everything <= surface:
            return Route(FULL, "the affected test modules are the whole suite", first_test)
    if present == {"pure"}:
        return Route(DOCS, "every changed path is a documentation file no test or script consumes", None, PURE_DOCS)
    worst = next((p for p, _, tier in kinds if tier == FAST), None)
    if worst is None:
        modules = tuple(sorted(covered))
        change_class = PARTIAL_TESTS if present == {"tests"} else MIXED
        reason = "every changed path is a test path with a derived affected set"
        if has_docs:
            reason = "test paths with a derived affected set, plus documentation validation"
        return Route(PARTIAL, reason, None, change_class, modules, docs_links=has_docs)
    extras = tuple(sorted(m for m in surface if m.startswith(INTEGRATION_PREFIX)))
    if "tests" in present:
        reason = "test changes are mixed with FAST paths; FAST plus the affected integration modules"
        return Route(FAST, reason, worst, MIXED, extras)
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
    return classify(paths, _index_or_none(tree), _graph_or_none(paths, repo, base, head, tree))


def _index_or_none(tree: Path | None) -> ConsumerIndex | None:
    if tree is None:
        return None
    try:
        return consumer_index(tree)
    except (OSError, subprocess.CalledProcessError):
        return None


def _graph_or_none(paths: Sequence[str], repo: Path, base: str, head: str, tree: Path | None) -> ImpactGraph | None:
    # Built only when a test path changed; any failure leaves None, which routes those paths FULL.
    if tree is None or not any(p.startswith("tests/") for p in paths):
        return None
    try:
        return build_impact_graph(repo, base, head, tree)
    except (OSError, ValueError, subprocess.SubprocessError):
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
    if result.modules:
        label = "Modules" if result.tier == PARTIAL else "Extra integration modules"
        lines.append(f"- {label} ({len(result.modules)}): {' '.join(result.modules)}")
    if result.docs_links:
        lines.append("- Also runs: `scripts/validation/validate-markdown-links.py`")
    return "\n".join(lines) + "\n"


_ROUTER_CMD = "python3 scripts/validation/ci_test_route.py"
RUN_COMMANDS = {
    DOCS: f"{_ROUTER_CMD} run-docs",
    FAST: f"{_ROUTER_CMD} run-fast",
    FULL: "python3 -m unittest discover -s tests -t .",
}


def run_command(result: Route) -> str:
    """The exact command that runs the tier a Route selected."""
    if result.tier == PARTIAL:
        links = " --with-docs-links" if result.docs_links else ""
        return f"{_ROUTER_CMD} run-partial{links} --modules {' '.join(result.modules)}"
    if result.tier == FAST and result.modules:
        return f"{RUN_COMMANDS[FAST]} --modules {' '.join(result.modules)}"
    return RUN_COMMANDS[result.tier]


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


def validate_module_ids(modules: Sequence[str]) -> str | None:
    """Return a problem description, or None when every ID is a well-formed, resolvable test module."""
    if not modules:
        return "no test modules selected"
    for module in modules:
        if not _MODULE_ID.match(module):
            return f"not a test module ID: {module!r}"
    return None


def partial_suite(modules: Sequence[str]) -> unittest.TestSuite:
    return unittest.defaultTestLoader.loadTestsFromNames(list(modules))


def _cmd_route(args: argparse.Namespace) -> int:
    tree = Path(args.tree) if args.tree else None
    result = safe_route(args.event_name, Path(args.repo), args.base, args.head, tree)
    print(summary_markdown(result), end="")
    _append(args.step_summary, summary_markdown(result))
    # Last, so a failure anywhere above leaves the tier unset, which runs FULL.
    outputs = f"tier={result.tier}\nclass={result.change_class}\n"
    if result.modules:
        outputs += f"modules={' '.join(result.modules)}\n"
    if result.docs_links:
        outputs += "docs_links=true\n"
    _append(args.github_output, outputs)
    return 0


def _cmd_classify(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    result = safe_route("pull_request", repo, args.base, args.head, repo)
    print(summary_markdown(result), end="")
    print(f"- Run: `{run_command(result)}`")
    return 0


def _cmd_run_fast(args: argparse.Namespace) -> int:
    suite = fast_suite()
    if args.modules:
        # Integration modules a change affects: FAST alone would drop them.
        problem = validate_module_ids(args.modules)
        if problem is not None:
            print(f"run-fast: {problem}", file=sys.stderr)
            return 1
        suite.addTests(partial_suite(args.modules))
    if args.list:
        for test in _iter_tests(suite):
            print(test.id())
        return 0
    result = unittest.TextTestRunner().run(suite)
    return 0 if result.wasSuccessful() and result.testsRun > 0 else 1


def _cmd_run_partial(args: argparse.Namespace) -> int:
    root = Path(args.repo).resolve()
    problem = validate_module_ids(args.modules)
    if problem is not None:
        print(f"run-partial: {problem}", file=sys.stderr)
        return 1
    os.chdir(root)
    sys.path.insert(0, str(root))
    missing = [m for m in args.modules if importlib.util.find_spec(m) is None]
    if missing:
        print(f"run-partial: module does not resolve: {missing[0]}", file=sys.stderr)
        return 1
    if args.list:
        print(*args.modules, sep="\n")
        return 0
    links_ok = True
    if args.with_docs_links:
        links_ok = subprocess.run([sys.executable, LINK_VALIDATOR, "--repo-root", str(root)], check=False).returncode == 0
    result = unittest.TextTestRunner().run(partial_suite(args.modules))
    return 0 if links_ok and result.wasSuccessful() and result.testsRun > 0 else 1


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

    route_cmd = commands.add_parser("route", help="classify the change set and emit tier=docs|partial|fast|full")
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
    fast_cmd.add_argument("--modules", nargs="+", help="extra test modules to run besides the FAST set")
    fast_cmd.set_defaults(func=_cmd_run_fast)

    partial_cmd = commands.add_parser("run-partial", help="run only an explicit set of test modules")
    partial_cmd.add_argument("--modules", nargs="+", required=True, help="module IDs the router selected")
    partial_cmd.add_argument("--with-docs-links", action="store_true", help="also run the Markdown link validator")
    partial_cmd.add_argument("--repo", default=".")
    partial_cmd.add_argument("--list", action="store_true", help="print the selected modules instead of running them")
    partial_cmd.set_defaults(func=_cmd_run_partial)

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
