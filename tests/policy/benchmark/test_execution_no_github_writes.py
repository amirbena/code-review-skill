"""Execution-side benchmark code holds no GitHub write path (#470; amendments A2, A8, A13).

The scope is the import closure of the execution entrypoint. The only GitHub-adjacent
operation allowed inside it is the seal: a `git push` from `benchmark_seal.py`.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

SCRIPTS = REPO_ROOT / "runtime_platform" / "benchmark" / "scripts"
ENTRYPOINT = SCRIPTS / "run_benchmark_routine.py"
SEAL_MODULE = "benchmark_seal"
PUBLICATION_SIDE = {"publish_benchmark", "publisher"}

FORBIDDEN_IMPORTS = {
    "requests", "httpx", "aiohttp", "urllib3", "http.client", "urllib.request",
    "socket", "smtplib", "github", "ghapi", "pygithub", "octokit",
}
FORBIDDEN_NAMES = {"GhCliIssueClient", "GitHubIssueClient", "sync_regressions", "_post_evidence", "_gh"}
FORBIDDEN_TEXT = ("api.github.com", "GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PAT", "x-access-token")
FORBIDDEN_GIT_FLAGS = {"--force", "--force-with-lease", "--delete", "--mirror", "--tags", "--prune"}


def _docstring_nodes(tree: ast.AST) -> set[int]:
    nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                nodes.add(id(first.value))
    return nodes


def violations(source: str, *, allow_push: bool = False) -> list[str]:
    """Every GitHub-write signal in `source`: imports, names, credentials, `gh`, force flags."""
    tree = ast.parse(source)
    docstrings = _docstring_nodes(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [f"import {a.name}" for a in node.names if a.name in FORBIDDEN_IMPORTS or a.name.split(".")[0] in FORBIDDEN_IMPORTS]
        elif isinstance(node, ast.ImportFrom) and node.module:
            module_hit = node.module in FORBIDDEN_IMPORTS or node.module.split(".")[0] in FORBIDDEN_IMPORTS
            name_hits = [a.name for a in node.names if f"{node.module}.{a.name}" in FORBIDDEN_IMPORTS]
            if module_hit or name_hits:
                found.append(f"from {node.module} import ...")
            found += [f"import of {a.name}" for a in node.names if a.name in FORBIDDEN_NAMES]
            found += [f"import of {node.module}" for _ in [0] if PUBLICATION_SIDE & set(node.module.split("."))]
        elif isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            found.append(f"name {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
            found.append(f"attribute {node.attr}")
        elif isinstance(node, ast.FunctionDef) and node.name in FORBIDDEN_NAMES:
            found.append(f"def {node.name}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            text = node.value
            if text == "gh" or text.startswith("gh "):
                found.append("gh invocation")
            if any(marker in text for marker in FORBIDDEN_TEXT):
                found.append(f"credential or API reference {text!r}")
            if text in FORBIDDEN_GIT_FLAGS:
                found.append(f"git flag {text}")
            if text == "push" and not allow_push:
                found.append("git push outside the seal module")
    return found


def _module_path(dotted: str) -> Path | None:
    path = REPO_ROOT / (dotted.replace(".", "/") + ".py")
    return path if path.is_file() else None


def import_closure(entry: Path) -> dict[str, Path]:
    """Repository-local modules reachable from `entry`, keyed by file stem."""
    seen: dict[str, Path] = {}
    pending = [entry]
    while pending:
        path = pending.pop()
        if path.stem in seen:
            continue
        seen[path.stem] = path
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            dotted: list[str] = []
            if isinstance(node, ast.Import):
                dotted = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                dotted = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            for name in dotted:
                target = _module_path(name) if name.split(".")[0] in ("runtime_platform", "tests") else None
                if target is not None:
                    pending.append(target)
    return seen


class ScannerTests(unittest.TestCase):
    def assertFlags(self, source: str, needle: str, **kwargs: bool) -> None:
        self.assertTrue(any(needle in v for v in violations(source, **kwargs)), (needle, violations(source, **kwargs)))

    def test_flags_a_gh_call(self) -> None:
        self.assertFlags('import subprocess\nsubprocess.run(["gh", "issue", "create"])', "gh invocation")

    def test_flags_network_and_github_libraries(self) -> None:
        self.assertFlags("import requests", "import requests")
        self.assertFlags("from urllib import request\nimport urllib.request", "import urllib.request")
        self.assertFlags("from github import Github", "from github import")

    def test_flags_credentials_and_api_urls(self) -> None:
        self.assertFlags('import os\nos.environ["GITHUB_TOKEN"]', "GITHUB_TOKEN")
        self.assertFlags('URL = "https://api.github.com/repos"', "api.github.com")

    def test_flags_the_retired_write_helpers(self) -> None:
        self.assertFlags("def _post_evidence(): ...", "_post_evidence")
        self.assertFlags("from x.benchmark_drift import sync_regressions", "sync_regressions")
        self.assertFlags("from runtime_platform.benchmark.publisher import sweep", "publisher")

    def test_flags_force_and_delete_flags(self) -> None:
        self.assertFlags('cmd = ["git", "push", "--force"]', "git flag --force", allow_push=True)
        self.assertFlags('cmd = ["git", "push", "--delete", "origin", "x"]', "git flag --delete", allow_push=True)

    def test_flags_push_outside_the_seal_module_only(self) -> None:
        self.assertFlags('cmd = ["git", "push", "origin", "x"]', "git push outside the seal module")
        self.assertEqual(violations('cmd = ["git", "push", "origin", "x"]', allow_push=True), [])

    def test_ignores_docstrings_and_benign_code(self) -> None:
        self.assertEqual(violations('"""Never uses GITHUB_TOKEN or gh."""\nx = "ghost"\ny = ["git", "show"]'), [])


class ExecutionScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.closure = import_closure(ENTRYPOINT)

    def test_closure_covers_the_execution_pipeline(self) -> None:
        expected = {
            "run_benchmark_routine", "benchmark_lane_run", "benchmark_drift_evaluation", "benchmark_baseline",
            "benchmark_run_record", "benchmark_seal", "benchmark_drift", "benchmark_result", "run_benchmark",
            "benchmark_review_adapter", "benchmark_routine_verify",
        }
        self.assertLessEqual(expected, set(self.closure))

    def test_publication_side_code_is_not_reachable_from_execution(self) -> None:
        self.assertEqual(PUBLICATION_SIDE & set(self.closure), set())

    def test_no_execution_module_has_a_github_write_path(self) -> None:
        for stem, path in sorted(self.closure.items()):
            found = violations(path.read_text(encoding="utf-8"), allow_push=stem == SEAL_MODULE)
            self.assertEqual(found, [], f"{path.relative_to(REPO_ROOT)}: {found}")

    def test_only_the_seal_module_pushes(self) -> None:
        pushers = [
            stem for stem, path in self.closure.items() if violations(path.read_text(encoding="utf-8"), allow_push=True) == []
            and any(isinstance(n, ast.Constant) and n.value == "push" for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))))
        ]
        self.assertEqual(pushers, [SEAL_MODULE])

    def test_the_in_routine_gh_client_is_retired(self) -> None:
        self.assertFalse((SCRIPTS / "benchmark_regression_lifecycle.py").exists())
        for path in SCRIPTS.glob("*.py"):
            self.assertNotIn("GhCliIssueClient", path.read_text(encoding="utf-8"), path.name)

    def test_the_retired_helpers_are_gone_from_the_entrypoint(self) -> None:
        source = ENTRYPOINT.read_text(encoding="utf-8")
        for retired in ("_post_evidence", "def _gh", "--evidence-issue", "EVIDENCE_MARKER"):
            self.assertNotIn(retired, source)


class NoWorkflowRunsTheBenchmarkTests(unittest.TestCase):
    def test_no_workflow_invokes_the_execution_entrypoint(self) -> None:
        for workflow in sorted((REPO_ROOT / ".github" / "workflows").glob("*.y*ml")):
            text = workflow.read_text(encoding="utf-8")
            for name in ("run_benchmark_routine", "benchmark_lane_run", "run_benchmark.py"):
                self.assertNotIn(name, text, f"{workflow.name} references {name}")


if __name__ == "__main__":
    unittest.main()
