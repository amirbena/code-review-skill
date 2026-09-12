"""Packaging-boundary guard: end-to-end contents of the built github-pr-review archive."""

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

class GitHubArchiveContentTests(unittest.TestCase):
    """The packaged github-pr-review archive carries every policy needed to
    instruct repository-backed review and portable concurrency, and no
    Python."""

    @classmethod
    def setUpClass(cls) -> None:
        result = subprocess.run(
            [str(PACKAGE_SCRIPT), "github"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"package-skills.sh github failed:\n{result.stdout}\n{result.stderr}"
            )
        with zipfile.ZipFile(DIST_DIR / "github-pr-review-skill.zip") as zf:
            cls.names = set(zf.namelist())
            cls.review_scope_text = zf.read(
                "shared/policies/review-scope.md"
            ).decode("utf-8")
            cls.remediation_text = zf.read(
                "shared/policies/remediation-guidance.md"
            ).decode("utf-8")

    def test_no_python_and_no_reference_modules(self) -> None:
        self.assertEqual({n for n in self.names if n.endswith(".py")}, set())
        for module in REFERENCE_TEST_MODULES:
            self.assertEqual({n for n in self.names if n.endswith(module)}, set())

    def test_repository_backed_and_parallel_policies_are_packaged(self) -> None:
        required = {
            "SKILL.md",
            "policies/github-review.md",
            "policies/repository-checkout.md",
            "policies/parallel-review.md",
            "runbooks/active-pr-review.md",
            "runbooks/passive-pr-review.md",
            "shared/policies/parallel-review.md",
            "shared/policies/review-scope.md",
        }
        self.assertEqual(required - self.names, set())

    def test_archive_contains_license(self) -> None:
        self.assertIn("LICENSE", self.names)

    def test_root_cause_model_completeness_policy_is_packaged(self) -> None:
        self.assertIn(
            "## Root-cause and model-completeness pass", self.review_scope_text
        )

    def test_architectural_placement_policy_is_packaged(self) -> None:
        self.assertIn(
            "## Architectural placement and execution-lifecycle fidelity",
            self.review_scope_text,
        )

    def test_affected_test_impact_policy_is_packaged(self) -> None:
        self.assertIn(
            "## Affected-test / test-impact analysis", self.review_scope_text
        )

    def test_shared_remediation_policy_is_packaged(self) -> None:
        self.assertIn("## Skill-specific detail", self.remediation_text)
        self.assertIn("github-pr-review", self.remediation_text)

    def test_repo_dev_docs_are_not_packaged(self) -> None:
        for n in self.names:
            self.assertNotIn("runtime-parallelism.md", n)
            self.assertNotIn("ARCHITECTURE.md", n)


if __name__ == "__main__":
    unittest.main()
