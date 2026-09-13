#!/usr/bin/env python3
"""Architectural-boundary guard: the benchmark CI classifier and the
release-worthiness classifier must never couple to each other (Issue #255).

Structural (AST-based) rather than behavioral: it fails on the coupling
itself — an import, not merely a shared outcome — even if someone adds an
import that happens to go unused. Mirrors the intent of
tests/integration/release/test_release_worthiness_pr_boundary.py, but for
this new cross-classifier independence requirement rather than the
existing PR-diff-base boundary.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

BENCHMARK_CLASSIFIER = REPO_ROOT / "scripts" / "benchmark_ci_classifier.py"
RELEASE_WORTHINESS = REPO_ROOT / "scripts" / "release_worthiness.py"
RELEASE_LIB_DIR = REPO_ROOT / "scripts" / "release_lib"
BENCHMARK_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "benchmark-check.yml"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release-worthiness.yml"


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


class ClassifierImportBoundaryTests(unittest.TestCase):
    def test_benchmark_classifier_does_not_import_release_lib_or_release_worthiness(self) -> None:
        imported = _imported_module_names(BENCHMARK_CLASSIFIER)
        self.assertNotIn("release_lib", imported)
        self.assertNotIn("release_worthiness", imported)

    def test_release_worthiness_does_not_import_benchmark_ci_classifier(self) -> None:
        imported = _imported_module_names(RELEASE_WORTHINESS)
        self.assertNotIn("benchmark_ci_classifier", imported)

    def test_release_lib_modules_do_not_import_benchmark_ci_classifier(self) -> None:
        for py_file in RELEASE_LIB_DIR.rglob("*.py"):
            imported = _imported_module_names(py_file)
            self.assertNotIn(
                "benchmark_ci_classifier",
                imported,
                msg=f"{py_file} must not import benchmark_ci_classifier",
            )


class WorkflowIndependenceTests(unittest.TestCase):
    def test_benchmark_workflow_does_not_reference_release_worthiness_jobs(self) -> None:
        text = BENCHMARK_WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("release-gate", text)
        self.assertNotIn("release_worthiness.py", text)
        self.assertNotIn("release_lib", text)

    def test_release_worthiness_workflow_does_not_reference_benchmark_check(self) -> None:
        text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("benchmark-check", text)
        self.assertNotIn("benchmark_ci_classifier.py", text)
        self.assertNotIn("run_benchmark.py", text)

    def test_workflows_have_independent_concurrency_groups(self) -> None:
        benchmark_text = BENCHMARK_WORKFLOW.read_text(encoding="utf-8")
        release_text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: benchmark-check-", benchmark_text)
        self.assertIn("group: release-worthiness-", release_text)

    def test_benchmark_workflow_is_never_added_as_required_via_needs(self) -> None:
        # Only the YAML `needs:` key matters here (a job dependency); the
        # workflow's own explanatory comments mention "needs:" in prose.
        lines = BENCHMARK_WORKFLOW.read_text(encoding="utf-8").splitlines()
        needs_keys = [line for line in lines if line.strip().startswith("needs:")]
        self.assertEqual(needs_keys, [])


if __name__ == "__main__":
    unittest.main()
