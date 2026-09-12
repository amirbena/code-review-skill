"""Packaging-boundary guard: both platform scripts consume the same declarative package manifest, with no restated file lists."""

from __future__ import annotations

import unittest

from tests.integration.packaging._shared import (
    PS1,
    SH,
    _shared_destinations,
    _skill_destinations,
)


class PackagingScriptParityTests(unittest.TestCase):
    """Both platform scripts consume the one package manifest."""

    def setUp(self) -> None:
        self.sh = SH.read_text(encoding="utf-8")
        self.ps1 = PS1.read_text(encoding="utf-8")

    def test_both_scripts_read_the_manifest(self) -> None:
        for script in (self.sh, self.ps1):
            self.assertIn("package-manifest.json", script)

    def test_scripts_do_not_restate_manifest_resources(self) -> None:
        for obsolete_name in (
            "shared_policies",
            "shared_templates",
            "github_required_runtime_templates",
            "sharedPolicies",
            "sharedTemplates",
            "githubRequiredRuntimeTemplates",
            "SkillFiles",
        ):
            self.assertNotIn(obsolete_name, self.sh)
            self.assertNotIn(obsolete_name, self.ps1)

    def test_new_shared_policies_are_in_both(self) -> None:
        for name in (
            "review-context.md",
            "review-evidence.md",
            "parallel-review.md",
            "runtime-validation.md",
            "change-risk-signals.md",
            "repository-expansion.md",
            "large-pr-partitioning.md",
            "review-stopping-criteria.md",
        ):
            self.assertIn(f"shared/policies/{name}", _shared_destinations())

    def test_new_github_policies_are_in_both(self) -> None:
        for name in (
            "policies/review-context.md",
            "policies/review-evidence.md",
            "policies/repository-checkout.md",
            "policies/parallel-review.md",
        ):
            self.assertIn(name, _skill_destinations("github"))

    def test_powershell_resolves_a_windows_compatible_python_launcher(self) -> None:
        self.assertIn('Get-Command "python"', self.ps1)
        self.assertIn('Get-Command "python3"', self.ps1)
        self.assertNotIn("& python3 $metadataValidator", self.ps1)

    def test_powershell_treats_manifest_sources_as_literal_paths(self) -> None:
        self.assertIn("Test-Path -LiteralPath $sourcePath -PathType Leaf", self.ps1)
        self.assertIn("Copy-Item -LiteralPath $sourcePath -Destination $destPath", self.ps1)
        self.assertNotIn("Test-Path $sourcePath", self.ps1)
        self.assertNotIn("Copy-Item -Path $sourcePath", self.ps1)


if __name__ == "__main__":
    unittest.main()
