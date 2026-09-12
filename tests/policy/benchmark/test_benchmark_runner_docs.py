#!/usr/bin/env python3
"""Structural contract checks for the benchmark runner contract (#52).

Pins docs/benchmark/runner-contract.md so the canonical invariant, the
per-case isolation model, the repository-safety invariants (no mutation,
exact dirty-state preservation, integrity verification, cleanup on both
paths), the machine-readable per-case result shape, run modes, the
exit-status rule, and the deferred-scope boundaries cannot drift silently.
Prose assertions are whitespace-normalized; structural ones target
headings and literal terms.
"""

import unittest

from tests.support.paths import REPO_ROOT

DOC = REPO_ROOT / "docs" / "benchmark" / "runner-contract.md"
README = REPO_ROOT / "docs" / "benchmark" / "README.md"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
REFERENCE = REPO_ROOT / "tests" / "reference" / "benchmark" / "benchmark_runner.py"
UNIT_TEST = REPO_ROOT / "tests" / "unit" / "benchmark" / "test_benchmark_runner.py"


class RunnerContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw = DOC.read_text(encoding="utf-8")
        cls.text = " ".join(cls.raw.split())

    def test_is_repository_development_only_not_packaged(self) -> None:
        self.assertIn("repository-development doc: not packaged", self.text)
        self.assertIn("no packaged Skill resource depends on it", self.text)

    def test_names_issue_52_and_its_neighbours(self) -> None:
        for token in ("#52", "#50", "#51", "#53", "#41", "#40"):
            self.assertIn(token, self.raw)

    def test_canonical_invariant_is_stated_verbatim(self) -> None:
        self.assertIn(
            "A benchmark run executes each case's reviewer against an isolated, "
            "disposable copy of that case's input, records what the reviewer "
            "produced, and leaves every protected source checkout byte-for-byte "
            "unchanged — whether the case succeeds or fails.",
            self.text,
        )

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

    def test_scope_boundaries_defer_matching_metrics_and_reporting(self) -> None:
        self.assertIn("## 8. Explicitly out of scope", self.raw)
        boundary = " ".join(self.raw.split("## 8. Explicitly out of scope", 1)[1].split())
        self.assertIn("match relation", boundary)
        self.assertIn("issues/41", boundary)
        self.assertIn("issues/53", boundary)
        self.assertIn("Container / sandbox orchestration", boundary)
        self.assertIn("future* isolation mechanism, not required by this contract", boundary)

    def test_status_defers_to_an_eventual_canonical_home(self) -> None:
        tail = " ".join(self.raw.split("## Status and canonical home", 1)[1].split())
        self.assertIn("becomes the design record", tail)
        self.assertIn("MUST NOT keep evolving the runner behavior independently", tail)
        self.assertIn("](../../tests/reference/benchmark/benchmark_runner.py)", self.raw)
        self.assertIn("](../../tests/unit/benchmark/test_benchmark_runner.py)", self.raw)


class DirectoryNavigationTests(unittest.TestCase):
    def test_readme_maps_the_runner_contract(self) -> None:
        raw = README.read_text(encoding="utf-8")
        self.assertIn("](runner-contract.md)", raw)
        self.assertIn("#52", raw)

    def test_architecture_mentions_the_runner_is_built(self) -> None:
        text = " ".join(ARCHITECTURE.read_text(encoding="utf-8").split())
        self.assertIn("runner-contract.md", text)
        self.assertIn("nothing benchmark", text)

    def test_reference_module_is_declared_test_only(self) -> None:
        head = REFERENCE.read_text(encoding="utf-8")[:600]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())

    def test_unit_test_consumes_the_single_reference_runner(self) -> None:
        raw = UNIT_TEST.read_text(encoding="utf-8")
        self.assertIn("from tests.reference.benchmark import benchmark_runner as br", raw)
        self.assertIn("never defines a second one", raw)


if __name__ == "__main__":
    unittest.main()
