#!/usr/bin/env python3
"""Import and credential boundary of the publication CLI (Issue #471).

Contract: runtime_platform/benchmark/scheduled-operations/publication-architecture.md §5.
"""

from __future__ import annotations

import ast
import unittest

from tests.support.paths import REPO_ROOT

PUBLISHER = REPO_ROOT / "runtime_platform" / "benchmark" / "publisher"
FORBIDDEN_IMPORTS = (
    "subprocess",
    "runtime_platform.benchmark.scripts.run_benchmark",
    "runtime_platform.benchmark.scripts.run_benchmark_routine",
    "runtime_platform.benchmark.scripts.benchmark_review_adapter",
    "runtime_platform.benchmark.scripts.benchmark_drift",
    "runtime_platform.benchmark.scripts.benchmark_history",
    "runtime_platform.benchmark.scripts.benchmark_routine_verify",
    "runtime_platform.benchmark.reference",
)
FORBIDDEN_CREDENTIAL_NAMES = ("GH_TOKEN", "GITHUB_TOKEN", "gh auth")


def _imports(path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


class PublisherBoundaryTests(unittest.TestCase):
    def sources(self):
        files = sorted(PUBLISHER.glob("*.py")) + [REPO_ROOT / "runtime_platform" / "benchmark" / "scripts" / "publish_benchmark.py"]
        self.assertGreater(len(files), 5)
        return files

    def test_publisher_imports_no_execution_path_and_no_subprocess(self) -> None:
        for path in self.sources():
            for imported in _imports(path):
                for forbidden in FORBIDDEN_IMPORTS:
                    self.assertFalse(imported == forbidden or imported.startswith(forbidden + "."), f"{path.name} imports {imported}")

    def test_no_ambient_or_personal_credential_is_ever_read(self) -> None:
        for path in self.sources():
            text = path.read_text(encoding="utf-8")
            for name in FORBIDDEN_CREDENTIAL_NAMES:
                self.assertNotIn(name, text.replace("BENCHMARK_", ""), f"{path.name} mentions {name}")

    def test_the_retired_in_routine_gh_client_is_gone(self) -> None:
        drift = (REPO_ROOT / "runtime_platform" / "benchmark" / "scripts" / "benchmark_drift.py").read_text(encoding="utf-8")
        for retired in ("GhCliIssueClient", "subprocess", "sync_regressions"):
            self.assertFalse(retired in drift, f"benchmark_drift.py still mentions {retired}")


if __name__ == "__main__":
    unittest.main()
