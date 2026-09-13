#!/usr/bin/env python3
"""Coverage for the benchmark CI applicability classifier (Issue #255).

Pure-function tests for `scripts/benchmark/benchmark_ci_classifier.py`: applicable
paths (each of the minimum path categories in
docs/benchmark/ci-integration.md), not-applicable paths, mixed changesets,
and the empty changeset. Plus a thin CLI check for `--changed-files-from`
and `--github-output` wiring.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts" / "benchmark"))

import benchmark_ci_classifier as bcc  # noqa: E402

SCRIPT = REPO_ROOT / "scripts" / "benchmark" / "benchmark_ci_classifier.py"


class IsApplicablePathTests(unittest.TestCase):
    def test_shared_tree_is_applicable(self) -> None:
        self.assertTrue(bcc.is_applicable_path("shared/policies/severity.md"))

    def test_skills_tree_is_applicable(self) -> None:
        self.assertTrue(bcc.is_applicable_path("skills/local-code-review/SKILL.md"))

    def test_docs_benchmark_tree_is_applicable(self) -> None:
        self.assertTrue(bcc.is_applicable_path("docs/benchmark/corpus/correctness.yaml"))

    def test_reference_benchmark_tests_are_applicable(self) -> None:
        self.assertTrue(bcc.is_applicable_path("tests/reference/benchmark/benchmark_runner.py"))

    def test_run_benchmark_script_is_applicable(self) -> None:
        self.assertTrue(bcc.is_applicable_path("scripts/benchmark/run_benchmark.py"))

    def test_benchmark_review_adapter_script_is_applicable(self) -> None:
        self.assertTrue(bcc.is_applicable_path("scripts/benchmark/benchmark_review_adapter.py"))

    def test_unrelated_docs_are_not_applicable(self) -> None:
        self.assertFalse(bcc.is_applicable_path("docs/RELEASE.md"))

    def test_unrelated_scripts_are_not_applicable(self) -> None:
        self.assertFalse(bcc.is_applicable_path("scripts/release/release_worthiness.py"))

    def test_ci_workflow_files_are_not_applicable(self) -> None:
        self.assertFalse(bcc.is_applicable_path(".github/workflows/release-worthiness.yml"))

    def test_this_workflow_and_classifier_are_not_applicable(self) -> None:
        self.assertFalse(bcc.is_applicable_path(".github/workflows/benchmark-check.yml"))
        self.assertFalse(bcc.is_applicable_path("scripts/benchmark/benchmark_ci_classifier.py"))

    def test_empty_path_is_not_applicable(self) -> None:
        self.assertFalse(bcc.is_applicable_path(""))
        self.assertFalse(bcc.is_applicable_path("   "))

    def test_leading_dot_slash_and_backslashes_are_normalized(self) -> None:
        self.assertTrue(bcc.is_applicable_path("./shared/policies/severity.md"))
        self.assertTrue(bcc.is_applicable_path("shared\\policies\\severity.md"))


class ClassifyChangedPathsTests(unittest.TestCase):
    def test_empty_changeset_is_not_applicable(self) -> None:
        result = bcc.classify_changed_paths([])
        self.assertFalse(result.applicable)
        self.assertEqual(result.applicable_paths, ())
        self.assertIn("no review-behavior-affecting paths changed", result.reason)

    def test_all_not_applicable_changeset(self) -> None:
        result = bcc.classify_changed_paths(["README.md", "docs/RELEASE.md", "CHANGELOG.md"])
        self.assertFalse(result.applicable)
        self.assertEqual(result.other_paths, ("README.md", "docs/RELEASE.md", "CHANGELOG.md"))

    def test_mixed_changeset_is_applicable(self) -> None:
        result = bcc.classify_changed_paths(
            [
                "README.md",
                "shared/policies/severity.md",
                "docs/RELEASE.md",
            ]
        )
        self.assertTrue(result.applicable)
        self.assertEqual(result.applicable_paths, ("shared/policies/severity.md",))
        self.assertEqual(result.other_paths, ("README.md", "docs/RELEASE.md"))
        self.assertIn("shared/policies/severity.md", result.reason)

    def test_blank_lines_are_ignored(self) -> None:
        result = bcc.classify_changed_paths(["", "   ", "shared/x.md"])
        self.assertEqual(result.applicable_paths, ("shared/x.md",))

    def test_reason_truncates_a_long_sample(self) -> None:
        paths = [f"shared/{i}.md" for i in range(5)]
        result = bcc.classify_changed_paths(paths)
        self.assertIn("+2 more", result.reason)


class CliChangedFilesFromTests(unittest.TestCase):
    def _run(self, *extra_args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *extra_args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )

    def test_applicable_changeset_emits_true(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp) / "changed.txt"
            changed.write_text("shared/policies/severity.md\ndocs/RELEASE.md\n", encoding="utf-8")
            out = Path(tmp) / "gh-out.txt"

            proc = self._run("--changed-files-from", str(changed), "--github-output", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr)
            pairs = dict(line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines() if "=" in line)
            self.assertEqual(pairs["applicable"], "true")

    def test_not_applicable_changeset_emits_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            changed = Path(tmp) / "changed.txt"
            changed.write_text("README.md\ndocs/RELEASE.md\n", encoding="utf-8")
            out = Path(tmp) / "gh-out.txt"

            proc = self._run("--changed-files-from", str(changed), "--github-output", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr)
            pairs = dict(line.split("=", 1) for line in out.read_text(encoding="utf-8").splitlines() if "=" in line)
            self.assertEqual(pairs["applicable"], "false")

    def test_missing_base_ref_and_changed_files_from_errors(self) -> None:
        proc = self._run()
        self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
