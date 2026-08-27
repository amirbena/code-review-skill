#!/usr/bin/env python3
"""Hierarchical repository-instruction resolution contract tests."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import pr_simulation as sim
from pr_checkout import prepare_repository_checkout
from repository_instructions import InstructionResolutionError, resolve_repository_instructions


class RepositoryInstructionResolutionTests(unittest.TestCase):
    def test_root_nested_order_and_sibling_isolation(self) -> None:
        with sim.simulated_pr() as pr:
            with prepare_repository_checkout(pr.normalized_source()) as handle:
                context = resolve_repository_instructions(
                    handle.path, handle.changed_files(), repository_snapshot=handle.head_sha
                )
                payment = context.chain_for("services/payments/src/handler.py")
                self.assertEqual(
                    [item.path for item in payment],
                    ["AGENTS.md", "services/AGENTS.md", "services/payments/AGENTS.md"],
                )
                self.assertNotIn("services/search/AGENTS.md", [item.path for item in payment])
                self.assertEqual([item.path for item in context.chain_for("src/lib.py")], ["AGENTS.md"])
                self.assertEqual(set(dict(context.by_changed_file)), set(handle.changed_files()))

    def test_no_agents_is_valid_and_identity_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src/a.py").write_text("pass\n", encoding="utf-8")
            first = resolve_repository_instructions(root, ["src/a.py"], repository_snapshot="abc")
            second = resolve_repository_instructions(root, ["src/a.py"], repository_snapshot="abc")
            self.assertEqual(first.chain_for("src/a.py"), ())
            self.assertEqual(first.identity, second.identity)

    def test_more_specific_instruction_is_last(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a/b").mkdir(parents=True)
            (root / "AGENTS.md").write_text("generic preference\n", encoding="utf-8")
            (root / "a/AGENTS.md").write_text("specific convention\n", encoding="utf-8")
            context = resolve_repository_instructions(root, ["a/b/x.py"], repository_snapshot="s")
            self.assertEqual([item.content.strip() for item in context.chain_for("a/b/x.py")],
                             ["generic preference", "specific convention"])

    def test_traversal_and_symlink_escape_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            with self.assertRaises(InstructionResolutionError):
                resolve_repository_instructions(root, ["../x.py"], repository_snapshot="s")
            (root / "nested").mkdir()
            (Path(outside) / "AGENTS.md").write_text("escape\n", encoding="utf-8")
            os.symlink(Path(outside) / "AGENTS.md", root / "nested/AGENTS.md")
            with self.assertRaises(InstructionResolutionError):
                resolve_repository_instructions(root, ["nested/x.py"], repository_snapshot="s")

    def test_malformed_applicable_instruction_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_bytes(b"\xff\xfe")
            with self.assertRaisesRegex(InstructionResolutionError, "cannot read applicable"):
                resolve_repository_instructions(root, ["x.py"], repository_snapshot="s")


if __name__ == "__main__":
    unittest.main()
