#!/usr/bin/env python3
"""Tests for repository Markdown and Skill metadata references."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT


SCRIPT = REPO_ROOT / "scripts" / "validate-references.py"


class ReferenceValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def _write(self, relative_path: str, content: str = "") -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", relative_path], check=True)

    def _run(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.root)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_clean_relative_markdown_link_passes(self) -> None:
        self._write("docs/index.md", "See [the guide](guide.md#usage).\n")
        self._write("docs/guide.md", "# Usage\n")

        result = self._run()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "All repository references resolve.\n")

    def test_clean_directory_markdown_link_passes(self) -> None:
        self._write("docs/index.md", "See [the policies](../policies/).\n")
        self._write("policies/README.md", "# Policies\n")

        result = self._run()

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_broken_relative_markdown_link_fails_with_location(self) -> None:
        self._write("docs/index.md", "Intro\n\nSee [missing](missing.md#usage).\n")

        result = self._run()

        self.assertEqual(result.returncode, 1)
        self.assertIn("docs/index.md:3: missing.md#usage", result.stderr)

    def test_broken_shared_metadata_entry_fails_with_location(self) -> None:
        self._write(
            "skills/example/metadata/skill.yaml",
            "shared:\n  policies:\n    - ../../../shared/policies/missing.md\n",
        )

        result = self._run()

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "skills/example/metadata/skill.yaml:3: ../../../shared/policies/missing.md",
            result.stderr,
        )

    def test_clean_shared_metadata_entries_pass(self) -> None:
        self._write(
            "skills/example/metadata/skill.yaml",
            "shared:\n  policies:\n    - ../../../shared/policies/policy.md\n",
        )
        self._write("shared/policies/policy.md", "# Policy\n")

        result = self._run()

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_external_urls_and_inline_code_paths_are_ignored(self) -> None:
        self._write(
            "README.md",
            "[web](https://example.com/missing) [mail](mailto:test@example.com) "
            "[cdn](//example.com/file) `policies/missing.md`\n",
        )

        result = self._run()

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_every_unresolved_reference_is_reported(self) -> None:
        self._write("README.md", "[one](missing-one.md)\n[two](missing-two.md)\n")
        self._write(
            "skills/example/metadata/skill.yaml",
            "shared:\n  templates:\n    - ../../../shared/templates/missing.md\n",
        )

        result = self._run()

        self.assertEqual(result.returncode, 1)
        self.assertIn("README.md:1: missing-one.md", result.stderr)
        self.assertIn("README.md:2: missing-two.md", result.stderr)
        self.assertIn(
            "skills/example/metadata/skill.yaml:3: ../../../shared/templates/missing.md",
            result.stderr,
        )


class RepositoryIntegrationTests(unittest.TestCase):
    def test_standard_validation_runs_reference_check(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
        self.assertIn("python scripts/validate-references.py", workflow)

    def test_readme_documents_local_reference_check(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("python3 scripts/validate-references.py", readme)


if __name__ == "__main__":
    unittest.main()
