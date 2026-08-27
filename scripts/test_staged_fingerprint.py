#!/usr/bin/env python3
"""Coverage for staged_fingerprint against a real Git repository:
derivation from `git diff --cached --raw -M -z`, `-M` rename detection,
stability, and that staged equality never implies unstaged/untracked.

Contract: skills/local-code-review/policies/repository-state.md.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from staged_fingerprint import (
    STAGED_FINGERPRINT_COMMAND,
    compute_staged_fingerprint,
    run_staged_fingerprint,
)


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, check=True
    )


def _init_repo() -> Path:
    repo = Path(tempfile.mkdtemp(prefix="staged-fingerprint-test-"))
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "base.txt").write_text("base content\n")
    _git(repo, "add", "base.txt")
    _git(repo, "commit", "-q", "-m", "initial commit")
    return repo


def _staged_raw_bytes(repo: Path) -> bytes:
    return _git(repo, "diff", "--cached", "--raw", "-M", "-z").stdout


class StagedFingerprintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = _init_repo()

    def tearDown(self) -> None:
        shutil.rmtree(self.repo, ignore_errors=True)

    def test_documented_command_is_exact(self) -> None:
        self.assertEqual(
            tuple(STAGED_FINGERPRINT_COMMAND),
            ("git", "diff", "--cached", "--raw", "-M", "-z"),
        )

    def test_empty_staged_index_has_stable_well_known_fingerprint(self) -> None:
        fingerprint = run_staged_fingerprint(cwd=str(self.repo))
        self.assertEqual(fingerprint, hashlib.sha256(b"").hexdigest())

    def test_identical_staged_state_produces_the_same_fingerprint(self) -> None:
        (self.repo / "new.txt").write_text("new content\n")
        _git(self.repo, "add", "new.txt")

        first = run_staged_fingerprint(cwd=str(self.repo))
        second = run_staged_fingerprint(cwd=str(self.repo))
        self.assertEqual(first, second)

    def test_staging_a_change_alters_the_fingerprint(self) -> None:
        baseline = run_staged_fingerprint(cwd=str(self.repo))

        (self.repo / "new.txt").write_text("new content\n")
        _git(self.repo, "add", "new.txt")
        after_staging = run_staged_fingerprint(cwd=str(self.repo))

        self.assertNotEqual(baseline, after_staging)

    def test_staged_rename_is_detected_and_alters_the_fingerprint(self) -> None:
        baseline = run_staged_fingerprint(cwd=str(self.repo))

        _git(self.repo, "mv", "base.txt", "renamed.txt")
        raw = _staged_raw_bytes(self.repo)
        after_rename = compute_staged_fingerprint(raw)

        # -M rename detection must actually engage: the raw record status
        # field starts with 'R' (e.g. "R100"), not a plain delete+add.
        self.assertIn(b"R1", raw)
        self.assertNotEqual(baseline, after_rename)

    def test_staged_fingerprint_is_unaffected_by_further_unstaged_edits(self) -> None:
        (self.repo / "new.txt").write_text("new content\n")
        _git(self.repo, "add", "new.txt")
        staged_before = run_staged_fingerprint(cwd=str(self.repo))

        # Edit the already-staged file further, WITHOUT staging the edit —
        # this creates unstaged delta on top of the existing staged state.
        (self.repo / "new.txt").write_text("new content, further edited\n")
        unstaged_diff = _git(self.repo, "diff", "--name-only").stdout
        self.assertIn(b"new.txt", unstaged_diff)

        staged_after = run_staged_fingerprint(cwd=str(self.repo))
        self.assertEqual(
            staged_before,
            staged_after,
            "staged fingerprint must reflect only index state, never "
            "working-tree-only (unstaged) edits",
        )

    def test_staged_fingerprint_is_unaffected_by_untracked_files(self) -> None:
        baseline = run_staged_fingerprint(cwd=str(self.repo))

        (self.repo / "untracked.txt").write_text("not added to git\n")
        untracked = _git(
            self.repo, "ls-files", "--others", "--exclude-standard"
        ).stdout
        self.assertIn(b"untracked.txt", untracked)

        after_untracked_file_created = run_staged_fingerprint(cwd=str(self.repo))
        self.assertEqual(baseline, after_untracked_file_created)

    def test_staged_equality_does_not_mask_unstaged_or_untracked_changes(self) -> None:
        (self.repo / "new.txt").write_text("new content\n")
        _git(self.repo, "add", "new.txt")
        staged_first = run_staged_fingerprint(cwd=str(self.repo))

        # Change both unstaged and untracked state without touching the index.
        (self.repo / "base.txt").write_text("base content, edited\n")
        (self.repo / "untracked.txt").write_text("brand new\n")

        staged_second = run_staged_fingerprint(cwd=str(self.repo))
        unstaged_names = _git(self.repo, "diff", "--name-only").stdout
        untracked_names = _git(
            self.repo, "ls-files", "--others", "--exclude-standard"
        ).stdout

        # The staged fingerprint alone says "unchanged" ...
        self.assertEqual(staged_first, staged_second)
        # ... but unstaged and untracked state plainly did change, and must
        # be detected through their own dedicated commands, never inferred
        # from staged-fingerprint equality.
        self.assertIn(b"base.txt", unstaged_names)
        self.assertIn(b"untracked.txt", untracked_names)

    def test_raw_bytes_type_is_enforced(self) -> None:
        with self.assertRaises(TypeError):
            compute_staged_fingerprint("not-bytes")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
