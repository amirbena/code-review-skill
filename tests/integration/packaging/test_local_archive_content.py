"""Packaging-boundary guard: end-to-end contents of the built local-code-review archive."""

from __future__ import annotations

import shutil
import subprocess
import unittest
import zipfile

from tests.support.paths import REPO_ROOT
from tests.integration.packaging._shared import (
    DIST_DIR,
    PACKAGE_SCRIPT,
    REFERENCE_TEST_MODULES,
)


@unittest.skipUnless(
    shutil.which("zip") and shutil.which("unzip"),
    "zip/unzip not available on PATH — cannot build/inspect the archive",
)

class BuiltArchiveContentTests(unittest.TestCase):
    """End-to-end confirmation: build the real local-code-review archive
    and inspect its actual contents, not just the declared file list."""

    @classmethod
    def setUpClass(cls) -> None:
        result = subprocess.run(
            [str(PACKAGE_SCRIPT), "local"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"package-skills.sh local failed:\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        archive_path = DIST_DIR / "local-code-review-skill.zip"
        if not archive_path.is_file():
            raise AssertionError(f"expected archive not found: {archive_path}")
        with zipfile.ZipFile(archive_path) as zf:
            cls.archive_names = set(zf.namelist())
            cls.review_scope_text = zf.read(
                "shared/policies/review-scope.md"
            ).decode("utf-8")
            cls.remediation_text = zf.read(
                "shared/policies/remediation-guidance.md"
            ).decode("utf-8")

    def test_archive_contains_no_python_files(self) -> None:
        python_files = {n for n in self.archive_names if n.endswith(".py")}
        self.assertEqual(
            python_files,
            set(),
            f"packaged local-code-review archive must contain no .py files, found: {python_files}",
        )

    def test_archive_contains_the_review_context_policy(self) -> None:
        self.assertIn("policies/review-context.md", self.archive_names)

    def test_archive_contains_license(self) -> None:
        self.assertIn("LICENSE", self.archive_names)
        with zipfile.ZipFile(DIST_DIR / "local-code-review-skill.zip") as zf:
            self.assertEqual(
                (REPO_ROOT / "LICENSE").read_bytes(), zf.read("LICENSE")
            )

    def test_archive_contains_every_context_related_runtime_file(self) -> None:
        # The complete, minimal set of context-related files this Skill
        # actually depends on at runtime — policy + template + runbook +
        # entry point, all Markdown, all consumed by the LLM reading them.
        required = {
            "SKILL.md",
            "policies/review-context.md",
            "policies/pr-context.md",
            "runbooks/local-review.md",
            "templates/local-review-report.md",
            "shared/policies/severity.md",
            "shared/policies/review-scope.md",
            "shared/policies/review-context.md",
            "shared/policies/review-evidence.md",
        }
        missing = required - self.archive_names
        self.assertEqual(missing, set(), f"archive missing required runtime file(s): {missing}")

    def test_archive_contains_root_cause_model_completeness_policy(self) -> None:
        self.assertIn(
            "## Root-cause and model-completeness pass", self.review_scope_text
        )

    def test_archive_contains_architectural_placement_policy(self) -> None:
        self.assertIn(
            "## Architectural placement and execution-lifecycle fidelity",
            self.review_scope_text,
        )

    def test_archive_contains_affected_test_impact_policy(self) -> None:
        self.assertIn(
            "## Affected-test / test-impact analysis", self.review_scope_text
        )

    def test_archive_contains_shared_remediation_policy(self) -> None:
        self.assertIn("## Evidence-grounded direction", self.remediation_text)
        self.assertIn("include_fix_prompt", self.remediation_text)

    def test_archive_does_not_contain_reference_test_modules(self) -> None:
        for module in REFERENCE_TEST_MODULES:
            with self.subTest(module=module):
                matches = {n for n in self.archive_names if n.endswith(module)}
                self.assertEqual(matches, set())


if __name__ == "__main__":
    unittest.main()
