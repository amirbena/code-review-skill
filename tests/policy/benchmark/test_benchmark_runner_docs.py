#!/usr/bin/env python3
"""Structural contract checks for the benchmark runner contract (#52).

Pins runtime_platform/benchmark/runner-contract.md so the canonical invariant, the
per-case isolation model, the repository-safety invariants (no mutation,
exact dirty-state preservation, integrity verification, cleanup on both
paths), the machine-readable per-case result shape, run modes, the
exit-status rule, and the deferred-scope boundaries cannot drift silently.
Prose assertions are whitespace-normalized; structural ones target
headings and literal terms.
"""

import unittest

from tests.support.benchmark_doc_contract import (
    BenchmarkDocContractMixin,
    BenchmarkDocNavigationMixin,
    BenchmarkDocSpec,
    Section,
)
from tests.support.paths import REPO_ROOT

BENCH = REPO_ROOT / "runtime_platform" / "benchmark"
DOC = BENCH / "runner-contract.md"

SPEC = BenchmarkDocSpec(
    doc=DOC,
    issue_tokens=("#52", "#50", "#51", "#53", "#41", "#40"),
    invariant=(
        "A benchmark run executes each case's reviewer against an isolated, "
        "disposable copy of that case's input, records what the reviewer "
        "produced, and leaves every protected source checkout byte-for-byte "
        "unchanged — whether the case succeeds or fails."
    ),
    sections=(
        Section(
            "## 8. Explicitly out of scope",
            body=(
                "match relation",
                "issues/41",
                "issues/53",
                "Container / sandbox orchestration",
                "future* isolation mechanism, not required by this contract",
            ),
        ),
    ),
    status_body=("becomes the design record", "MUST NOT keep evolving the runner behavior independently"),
    status_raw=(
        "](reference/benchmark_runner.py)",
        "](../../tests/unit/benchmark/test_benchmark_runner.py)",
    ),
    readme_link="](runner-contract.md)",
    readme_issue="#52",
    architecture_name="runner-contract.md",
    reference=BENCH / "reference" / "benchmark_runner.py",
    reference_head_chars=600,
    unit_test=REPO_ROOT / "tests" / "unit" / "benchmark" / "test_benchmark_runner.py",
    unit_import="from runtime_platform.benchmark.reference import benchmark_runner as br",
    unit_phrase="never defines a second one",
)


class RunnerContractTests(BenchmarkDocContractMixin, unittest.TestCase):
    spec = SPEC

    def test_runner_is_external_infra_never_launched_by_a_skill(self) -> None:
        self.assertIn("It is **not** a Skill and is never packaged", self.text)
        self.assertIn("Neither `local-code-review` nor `github-pr-review` launches a benchmark", self.text)
        self.assertIn("only ever *invoked by* the runner against a prepared target", self.text)

    def test_reviewer_adapter_boundary_is_defined(self) -> None:
        self.assertIn("## 9. On the reviewer adapter", self.raw)
        self.assertIn("what performs the review is pluggable", self.text)
        self.assertIn("never itself reads Skill instructions and never runs target-repository code", self.text)

    def test_run_modes_cover_single_case_and_whole_corpus(self) -> None:
        self.assertIn("## 2. Run modes", self.raw)
        self.assertIn("either the whole corpus or one selected case", self.text)
        self.assertIn("An unknown `id` is an execution failure", self.text)
        self.assertIn("malformed corpus is not silently partially run", self.text)

    def test_per_case_isolation_materializes_into_the_workspace_only(self) -> None:
        self.assertIn("## 3. Per-case isolation", self.raw)
        self.assertIn("into that workspace only", self.text)
        self.assertIn("only the workspace path", self.text)
        self.assertIn("single-use", self.text)
        for token in ("`patch` input", "`repo_ref` input"):
            self.assertIn(token, self.raw)

    def test_repository_safety_invariants_are_explicit(self) -> None:
        self.assertIn("## 4. Repository-safety invariants", self.raw)
        self.assertIn("No mutation.", self.raw)
        self.assertIn("Dirty state is preserved exactly.", self.raw)
        self.assertIn("does not require it to be clean", self.text)
        self.assertIn("byte for byte", self.text)
        self.assertIn("Integrity is verified around execution.", self.raw)
        self.assertIn("`git status --porcelain`", self.raw)
        self.assertIn("A detected mutation is an execution failure.", self.raw)

    def test_cleanup_runs_on_both_paths_and_failure_is_an_execution_failure(self) -> None:
        self.assertIn("## 5. Cleanup", self.raw)
        self.assertIn("on both the success and the failure path", self.text)
        self.assertIn("A failed cleanup is an execution failure", self.text)
        self.assertIn("no benchmark-created residue remains", self.text)

    def test_case_result_shape_is_machine_readable_and_not_scored(self) -> None:
        self.assertIn("## 6. Case result shape", self.raw)
        for field in ("`id`", "`input_kind`", "`status`", "`produced_findings`", "`error`"):
            self.assertIn(field, self.raw)
        self.assertIn("recorded verbatim", self.text)
        self.assertIn("does **not** compare them to the fixture's `expected` block", self.text)

    def test_exit_code_reflects_execution_health_not_review_quality(self) -> None:
        self.assertIn("## 7. Execution status and exit code", self.raw)
        self.assertIn("Exit code reflects execution health, not review quality", self.text)
        self.assertIn("Finding defects is never a runner failure", self.text)


class DirectoryNavigationTests(BenchmarkDocNavigationMixin, unittest.TestCase):
    spec = SPEC


if __name__ == "__main__":
    unittest.main()
