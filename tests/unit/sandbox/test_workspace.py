"""Unit tests for scripts/sandbox/workspace.py (Issue #302)."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.sandbox import workspace as ws


class FingerprintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "a.txt").write_text("hello")

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_unchanged_tree_has_stable_fingerprint(self) -> None:
        self.assertEqual(ws.fingerprint(self.tmp), ws.fingerprint(self.tmp))

    def test_content_change_changes_fingerprint(self) -> None:
        before = ws.fingerprint(self.tmp)
        (self.tmp / "a.txt").write_text("mutated")
        os.utime(self.tmp / "a.txt", (0, 0))  # force a differing size, not just mtime noise
        self.assertNotEqual(before, ws.fingerprint(self.tmp))

    def test_new_file_changes_fingerprint(self) -> None:
        before = ws.fingerprint(self.tmp)
        (self.tmp / "b.txt").write_text("new")
        self.assertNotEqual(before, ws.fingerprint(self.tmp))

    def test_git_directory_is_ignored(self) -> None:
        (self.tmp / ".git").mkdir()
        (self.tmp / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        before = ws.fingerprint(self.tmp)
        (self.tmp / ".git" / "HEAD").write_text("ref: refs/heads/other\n")
        self.assertEqual(before, ws.fingerprint(self.tmp))


class PrepareWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = Path(tempfile.mkdtemp())
        (self.source / "app.py").write_text("value = 1\n")
        (self.source / "sub").mkdir()
        (self.source / "sub" / "b.py").write_text("value = 2\n")

    def tearDown(self) -> None:
        shutil.rmtree(self.source, ignore_errors=True)

    def test_work_copy_mirrors_source_content(self) -> None:
        wsp = ws.prepare_workspace(self.source)
        try:
            self.assertEqual((wsp.work_copy / "app.py").read_text(), "value = 1\n")
            self.assertEqual((wsp.work_copy / "sub" / "b.py").read_text(), "value = 2\n")
        finally:
            wsp.teardown()

    def test_writes_to_work_copy_never_touch_source(self) -> None:
        wsp = ws.prepare_workspace(self.source)
        try:
            (wsp.work_copy / "app.py").write_text("mutated in copy\n")
            self.assertEqual((self.source / "app.py").read_text(), "value = 1\n")
        finally:
            wsp.teardown()

    def test_verify_source_unchanged_detects_no_drift(self) -> None:
        wsp = ws.prepare_workspace(self.source)
        try:
            self.assertTrue(ws.verify_source_unchanged(self.source, wsp.source_fingerprint))
        finally:
            wsp.teardown()

    def test_teardown_removes_the_ephemeral_root(self) -> None:
        wsp = ws.prepare_workspace(self.source)
        root = wsp.root
        wsp.teardown()
        self.assertFalse(root.exists())

    def test_escaping_symlink_is_not_followed_into_the_copy(self) -> None:
        outside = Path(tempfile.mkdtemp())
        (outside / "secret.txt").write_text("host secret")
        try:
            (self.source / "escape").symlink_to(outside / "secret.txt")
            wsp = ws.prepare_workspace(self.source)
            try:
                copied = wsp.work_copy / "escape"
                self.assertFalse(copied.is_symlink())
                self.assertNotIn("host secret", copied.read_text())
            finally:
                wsp.teardown()
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_contained_symlink_is_preserved(self) -> None:
        (self.source / "link.py").symlink_to(self.source / "app.py")
        wsp = ws.prepare_workspace(self.source)
        try:
            copied = wsp.work_copy / "link.py"
            self.assertTrue(copied.is_symlink())
            self.assertEqual(copied.read_text(), "value = 1\n")
        finally:
            wsp.teardown()
