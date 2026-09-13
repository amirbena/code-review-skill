#!/usr/bin/env python3
"""Structural contract checks for the benchmark CI integration doc (#255).

Pins docs/benchmark/ci-integration.md so the applicability path list, the
three-state non-blocking/informational contract, the independence-from-
release-worthiness rule, and the "runs the same script a developer runs
manually" invariant cannot drift silently. Mirrors the pinning style of
tests/policy/benchmark/test_benchmark_runner_docs.py.
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT

DOC = REPO_ROOT / "docs" / "benchmark" / "ci-integration.md"
README = REPO_ROOT / "docs" / "benchmark" / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "benchmark-check.yml"
CLASSIFIER = REPO_ROOT / "scripts" / "benchmark_ci_classifier.py"
CLASSIFIER_UNIT_TEST = REPO_ROOT / "tests" / "unit" / "benchmark" / "test_benchmark_ci_classifier.py"


class BenchmarkCiIntegrationDocTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = DOC.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_is_repository_development_only_not_packaged(self) -> None:
        self.assertIn("Repository-development doc: not packaged", self.text)
        self.assertIn("no packaged Skill resource depends on it", self.text)

    def test_names_issue_255_and_255(self) -> None:
        for token in ("#255", "#250"):
            self.assertIn(token, self.raw)

    def test_never_reimplements_benchmark_logic(self) -> None:
        self.assertIn(
            "It reimplements no benchmark logic: no second reviewer, no second runner, "
            "no second evaluator, and no Claude Code plugin.",
            self.text,
        )

    def test_applicability_path_list_is_exact(self) -> None:
        self.assertIn("## 2. Applicability classifier", self.raw)
        self.assertIn("no fuzzy heuristics", self.text)
        for token in (
            "`shared/**`",
            "`skills/**`",
            "`docs/benchmark/**`",
            "`tests/reference/benchmark/**`",
            "`scripts/run_benchmark.py` (exact file)",
            "`scripts/benchmark_review_adapter.py` (exact file)",
        ):
            self.assertIn(token, self.raw)

    def test_classifier_boundary_from_release_worthiness_is_explicit(self) -> None:
        self.assertIn("## 3. Independence from release-worthiness", self.raw)
        self.assertIn(
            "it does not import, call, or route through "
            "`scripts/release_lib/classification.py` or `scripts/release_worthiness.py`",
            self.text,
        )
        self.assertIn("no `needs:` on, and no job shared with", self.text)
        self.assertIn("not a required status check", self.text)

    def test_three_state_non_blocking_contract_is_named(self) -> None:
        self.assertIn("## 4. Non-blocking / informational status", self.raw)
        self.assertIn("**Not applicable**", self.raw)
        self.assertIn("**Applicable, runtime unavailable**", self.raw)
        self.assertIn("**Applicable, runtime available**", self.raw)
        self.assertIn("benchmark not run: runtime unavailable", self.text)
        self.assertIn("never conflated with", self.text)

    def test_not_a_required_gate_is_stated(self) -> None:
        self.assertIn("the job is never made a required merge gate", self.text)
        self.assertIn("default read-only `GITHUB_TOKEN` permissions", self.text)

    def test_runs_the_same_script_a_developer_runs_manually(self) -> None:
        self.assertIn("## 5. Runs the same script a developer runs manually", self.raw)
        self.assertIn("python3 scripts/run_benchmark.py", self.raw)
        self.assertIn("BENCHMARK_REVIEW_CLI", self.raw)
        self.assertIn("BENCHMARK_REVIEW_CLI_ARGS", self.raw)

    def test_files_named_in_the_doc_exist(self) -> None:
        self.assertTrue(WORKFLOW.is_file())
        self.assertTrue(CLASSIFIER.is_file())
        self.assertTrue(CLASSIFIER_UNIT_TEST.is_file())


class BenchmarkReadmeAndArchitectureLinkTests(unittest.TestCase):
    def test_readme_document_map_links_ci_integration(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("ci-integration.md", text)
        self.assertIn("255", text)

    def test_architecture_benchmark_section_links_ci_integration(self) -> None:
        text = ARCHITECTURE.read_text(encoding="utf-8")
        self.assertIn("benchmark/ci-integration.md", text)
        self.assertIn("255", text)


if __name__ == "__main__":
    unittest.main()
