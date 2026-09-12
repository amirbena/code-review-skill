"""Packaging-boundary guard: the declarative package manifest itself — schema, source/destination path safety, and Windows-path-escape rejection."""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from tests.support.paths import REPO_ROOT
from tests.integration.packaging._shared import (
    PACKAGE_MANIFEST,
    PACKAGE_MANIFEST_HELPER,
    REFERENCE_TEST_MODULES,
    _package_manifest,
    _skill_destinations,
)


class DeclaredPackageFileListTests(unittest.TestCase):
    """Structural checks on the declarative package manifest."""

    def setUp(self) -> None:
        self.manifest = _package_manifest()
        self.local_files = _skill_destinations("local")

    def test_manifest_schema_and_targets_are_stable(self) -> None:
        self.assertEqual(self.manifest["schema_version"], 1)
        self.assertEqual(set(self.manifest["skills"]), {"local", "github"})

    def test_every_mapping_has_a_unique_existing_source_and_safe_destination(self) -> None:
        for target, skill in self.manifest["skills"].items():
            entries = self.manifest["shared_files"] + skill["files"]
            destinations = [entry["destination"] for entry in entries]
            self.assertEqual(len(destinations), len(set(destinations)), target)
            for entry in entries:
                source = Path(entry["source"])
                destination = Path(entry["destination"])
                self.assertFalse(source.is_absolute())
                self.assertFalse(destination.is_absolute())
                self.assertNotIn("..", source.parts)
                self.assertNotIn("..", destination.parts)
                self.assertTrue((REPO_ROOT / source).is_file(), entry["source"])
            self.assertLessEqual(set(skill["required_entries"]), set(destinations))

    def _validate_mutated_manifest(self, mutate) -> subprocess.CompletedProcess[str]:
        manifest = _package_manifest()
        mutate(manifest)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(PACKAGE_MANIFEST_HELPER), str(path), "local", "validate"],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_manifest_rejects_repository_development_shared_source(self) -> None:
        result = self._validate_mutated_manifest(
            lambda manifest: manifest["shared_files"].append(
                {"source": "AGENTS.md", "destination": "AGENTS.md"}
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shared package source escapes approved roots", result.stderr)

    def test_manifest_rejects_cross_skill_source(self) -> None:
        result = self._validate_mutated_manifest(
            lambda manifest: manifest["skills"]["local"]["files"].append(
                {
                    "source": "skills/github-pr-review/policies/github-review.md",
                    "destination": "policies/github-review.md",
                }
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Skill package source escapes skills/local-code-review/", result.stderr)

    def test_manifest_rejects_windows_style_path_escapes(self) -> None:
        mutations = (
            lambda manifest: manifest["skills"]["local"].update(
                archive="..\\outside.zip"
            ),
            lambda manifest: manifest["skills"]["local"].update(
                name="..\\github-pr-review"
            ),
            lambda manifest: manifest["skills"]["local"]["files"].append(
                {
                    "source": "skills/local-code-review\\..\\github-pr-review/SKILL.md",
                    "destination": "copied-skill.md",
                }
            ),
            lambda manifest: manifest["skills"]["local"]["files"].append(
                {
                    "source": "skills/local-code-review/SKILL.md",
                    "destination": "..\\outside.md",
                }
            ),
            lambda manifest: manifest["skills"]["local"]["required_entries"].append(
                "..\\outside.md"
            ),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                result = self._validate_mutated_manifest(mutate)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("safe POSIX-style relative path", result.stderr)

    def test_manifest_rejects_windows_drives_roots_and_wildcards(self) -> None:
        mutations = (
            lambda manifest: manifest["skills"]["local"].update(
                archive="C:outside.zip"
            ),
            lambda manifest: manifest["skills"]["local"]["files"].append(
                {
                    "source": "skills/local-code-review/SKILL.md",
                    "destination": "C:/outside",
                }
            ),
            lambda manifest: manifest["skills"]["local"]["files"].append(
                {
                    "source": "skills/local-code-review/SKILL.md",
                    "destination": "//server/share/outside.md",
                }
            ),
            lambda manifest: manifest["skills"]["local"]["files"].append(
                {
                    "source": "skills/local-code-review/foo/*.md",
                    "destination": "wildcard-star.md",
                }
            ),
            lambda manifest: manifest["skills"]["local"]["files"].append(
                {
                    "source": "skills/local-code-review/foo/?ar.txt",
                    "destination": "wildcard-question.md",
                }
            ),
            lambda manifest: manifest["skills"]["local"]["files"].append(
                {
                    "source": "skills/local-code-review/foo/[ab].txt",
                    "destination": "wildcard-brackets.md",
                }
            ),
            lambda manifest: manifest["skills"]["local"].update(
                archive="local-*-review.zip"
            ),
            lambda manifest: manifest["skills"]["local"]["files"].append(
                {
                    "source": "skills/local-code-review/SKILL.md",
                    "destination": "templates/[draft].md",
                }
            ),
        )
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                result = self._validate_mutated_manifest(mutate)
                self.assertNotEqual(result.returncode, 0)

    def test_manifest_accepts_ordinary_posix_relative_paths(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(PACKAGE_MANIFEST_HELPER),
                str(PACKAGE_MANIFEST),
                "local",
                "validate",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_local_file_list_is_non_empty_and_sane(self) -> None:
        self.assertIn("SKILL.md", self.local_files)
        self.assertIn("policies/review-context.md", self.local_files)
        self.assertIn("policies/pr-context.md", self.local_files)

    def test_declared_file_list_contains_no_python_files(self) -> None:
        python_entries = [f for f in self.local_files if f.endswith(".py")]
        self.assertEqual(
            python_entries,
            [],
            "package-manifest.json declares a .py file for local-code-review — "
            "this is a Markdown/YAML-only Skill package; a .py entry here "
            "means a reference/test module was mistakenly wired into "
            "packaging without becoming a genuine, reviewed runtime "
            f"dependency: {python_entries}",
        )

    def test_none_of_the_reference_test_modules_are_declared(self) -> None:
        for module in REFERENCE_TEST_MODULES:
            with self.subTest(module=module):
                self.assertNotIn(
                    module,
                    self.local_files,
                    f"{module} must not be declared in package-manifest.json's "
                    "local-code-review file list unless it has genuinely "
                    "become a runtime dependency (Contract B) — see "
                    "tests/integration/test_packaging_runtime_boundary.py module "
                    "docstring",
                )


if __name__ == "__main__":
    unittest.main()
