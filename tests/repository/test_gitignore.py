#!/usr/bin/env python3
"""`.gitignore` ignores macOS metadata files at any depth."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT


def _ignored(rel_path: str) -> bool:
    return subprocess.run(
        ["git", "check-ignore", "-q", rel_path], cwd=str(REPO_ROOT), check=False
    ).returncode == 0


class GitignoreTests(unittest.TestCase):
    def test_ds_store_pattern_present(self) -> None:
        lines = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".DS_Store", [ln.strip() for ln in lines])

    def test_ds_store_ignored_at_root_and_nested(self) -> None:
        for rel in (".DS_Store", "docs/.DS_Store", "skills/github-pr-review/.DS_Store"):
            with self.subTest(path=rel):
                self.assertTrue(_ignored(rel), f"{rel} should be git-ignored")

    def test_no_ds_store_is_tracked(self) -> None:
        tracked = subprocess.run(
            ["git", "ls-files"], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True
        ).stdout.splitlines()
        offenders = [p for p in tracked if Path(p).name == ".DS_Store"]
        self.assertEqual(offenders, [])

    def test_documented_local_build_outputs_are_ignored(self) -> None:
        for rel in (".venv/pyvenv.cfg", "dist/local-code-review-skill.zip"):
            with self.subTest(path=rel):
                self.assertTrue(_ignored(rel), f"{rel} should be git-ignored")


if __name__ == "__main__":
    unittest.main()
