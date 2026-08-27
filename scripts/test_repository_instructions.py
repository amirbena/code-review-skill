#!/usr/bin/env python3
"""Repository-instruction discovery/resolution contract tests.

Covers hierarchical AGENTS.md + CLAUDE.md discovery, repository-declared
AGENTS/CLAUDE precedence, conservative ambiguity handling, and the
present-but-unreadable vs. genuinely-missing distinction. Behavioral, not
exact-paragraph string matching.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import pr_simulation as sim
from pr_checkout import prepare_repository_checkout
from repository_instructions import (
    ConflictOutcome,
    InstructionKind,
    InstructionPrecedence,
    InstructionResolutionError,
    UnresolvedReason,
    context_is_graded_ready,
    declared_precedence,
    resolve_conflict,
    resolve_repository_instructions,
)


def _write(root: Path, rel: str, text: str) -> Path:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


class HierarchicalAgentsChainTests(unittest.TestCase):
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
                self.assertTrue(context.is_complete)

    def test_more_specific_instruction_is_last(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "AGENTS.md", "generic preference\n")
            _write(root, "a/AGENTS.md", "specific convention\n")
            (root / "a/b").mkdir(parents=True)
            context = resolve_repository_instructions(root, ["a/b/x.py"], repository_snapshot="s")
            self.assertEqual(
                [item.content.strip() for item in context.chain_for("a/b/x.py")],
                ["generic preference", "specific convention"],
            )


class ClaudeMdDiscoveryTests(unittest.TestCase):
    def test_claude_md_discovered_on_applicable_ancestry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "CLAUDE.md", "root claude guidance\n")
            _write(root, "src/x.py", "pass\n")
            context = resolve_repository_instructions(root, ["src/x.py"], repository_snapshot="s")
            chain = context.chain_for("src/x.py")
            self.assertEqual([item.kind for item in chain], [InstructionKind.CLAUDE])
            self.assertEqual([item.path for item in chain], ["CLAUDE.md"])

    def test_nested_claude_md_is_in_chain_root_to_specific(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "AGENTS.md", "root agents\n")
            _write(root, "services/CLAUDE.md", "services claude\n")
            _write(root, "services/payments/AGENTS.md", "payments agents\n")
            _write(root, "services/payments/CLAUDE.md", "payments claude\n")
            _write(root, "services/search/AGENTS.md", "search agents\n")
            _write(root, "services/search/CLAUDE.md", "search claude\n")
            context = resolve_repository_instructions(
                root, ["services/payments/h.py"], repository_snapshot="s"
            )
            self.assertEqual(
                [item.path for item in context.chain_for("services/payments/h.py")],
                [
                    "AGENTS.md",
                    "services/CLAUDE.md",
                    "services/payments/AGENTS.md",
                    "services/payments/CLAUDE.md",
                ],
            )

    def test_sibling_agents_and_claude_files_do_not_leak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "AGENTS.md", "root\n")
            _write(root, "services/payments/AGENTS.md", "payments agents\n")
            _write(root, "services/payments/CLAUDE.md", "payments claude\n")
            _write(root, "services/search/AGENTS.md", "search agents\n")
            _write(root, "services/search/CLAUDE.md", "search claude\n")
            context = resolve_repository_instructions(
                root, ["services/payments/h.py"], repository_snapshot="s"
            )
            paths = {item.path for item in context.chain_for("services/payments/h.py")}
            self.assertNotIn("services/search/AGENTS.md", paths)
            self.assertNotIn("services/search/CLAUDE.md", paths)

    def test_agents_and_claude_coexist_in_deterministic_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "AGENTS.md", "root agents\n")
            _write(root, "CLAUDE.md", "root claude\n")
            first = resolve_repository_instructions(root, ["x.py"], repository_snapshot="s")
            second = resolve_repository_instructions(root, ["x.py"], repository_snapshot="s")
            self.assertEqual(
                [item.kind for item in first.chain_for("x.py")],
                [InstructionKind.AGENTS, InstructionKind.CLAUDE],
            )
            self.assertEqual(first.identity, second.identity)


class AgentsClaudePrecedenceTests(unittest.TestCase):
    """The policy allows AGENTS.md to win over CLAUDE.md ONLY when the target
    repository itself declares that relationship — never as a universal rule."""

    def _chain(self, agents_text: str, claude_text: str):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "AGENTS.md", agents_text)
            _write(root, "CLAUDE.md", claude_text)
            context = resolve_repository_instructions(root, ["x.py"], repository_snapshot="s")
            return context.chain_for("x.py")

    def test_repository_declared_precedence_is_respected(self) -> None:
        chain = self._chain(
            "Use tab indentation.\n",
            "This file defers to AGENTS.md, which is the canonical instruction source.\n",
        )
        self.assertIs(declared_precedence(chain), InstructionPrecedence.CLAUDE_DEFERS_TO_AGENTS)
        self.assertIs(
            resolve_conflict(chain, materially_conflicts=True),
            ConflictOutcome.RESOLVED_BY_DECLARED_PRECEDENCE,
        )

    def test_material_conflict_without_declared_precedence_is_surfaced_as_ambiguous(self) -> None:
        chain = self._chain("Use tab indentation.\n", "Use two-space indentation.\n")
        self.assertIs(declared_precedence(chain), InstructionPrecedence.NONE_DECLARED)
        self.assertIs(
            resolve_conflict(chain, materially_conflicts=True),
            ConflictOutcome.AMBIGUOUS_SURFACED,
        )

    def test_no_conflict_when_the_two_do_not_materially_disagree(self) -> None:
        chain = self._chain("Use tab indentation.\n", "Prefer descriptive test names.\n")
        self.assertIs(
            resolve_conflict(chain, materially_conflicts=False),
            ConflictOutcome.NO_CONFLICT,
        )

    def test_agents_md_alone_never_triggers_a_precedence_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "AGENTS.md", "Use tab indentation.\n")
            context = resolve_repository_instructions(root, ["x.py"], repository_snapshot="s")
            chain = context.chain_for("x.py")
            self.assertIs(declared_precedence(chain), InstructionPrecedence.NONE_DECLARED)
            self.assertIs(
                resolve_conflict(chain, materially_conflicts=True), ConflictOutcome.NO_CONFLICT
            )


class UnresolvableApplicableInstructionTests(unittest.TestCase):
    def test_genuinely_missing_instruction_is_valid_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/a.py", "pass\n")
            first = resolve_repository_instructions(root, ["src/a.py"], repository_snapshot="abc")
            second = resolve_repository_instructions(root, ["src/a.py"], repository_snapshot="abc")
            self.assertEqual(first.chain_for("src/a.py"), ())
            self.assertTrue(first.is_complete)
            self.assertTrue(context_is_graded_ready(first))
            self.assertEqual(first.identity, second.identity)

    def test_dangling_applicable_symlink_is_surfaced_not_silently_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "nested").mkdir()
            os.symlink(root / "nested/missing-target", root / "nested/AGENTS.md")
            context = resolve_repository_instructions(
                root, ["nested/x.py"], repository_snapshot="s"
            )
            self.assertEqual(context.chain_for("nested/x.py"), ())
            self.assertFalse(context.is_complete)
            self.assertFalse(context_is_graded_ready(context))
            self.assertEqual(
                [(u.path, u.reason) for u in context.unresolved],
                [("nested/AGENTS.md", UnresolvedReason.DANGLING_SYMLINK)],
            )

    def test_symlink_escaping_repository_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as outside:
            root = Path(tmp)
            (root / "nested").mkdir()
            _write(Path(outside), "AGENTS.md", "escape\n")
            os.symlink(Path(outside) / "AGENTS.md", root / "nested/AGENTS.md")
            with self.assertRaises(InstructionResolutionError):
                resolve_repository_instructions(root, ["nested/x.py"], repository_snapshot="s")

    def test_traversal_changed_file_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(InstructionResolutionError):
                resolve_repository_instructions(Path(tmp), ["../x.py"], repository_snapshot="s")

    def test_malformed_encoding_applicable_instruction_is_surfaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_bytes(b"\xff\xfe")
            context = resolve_repository_instructions(root, ["x.py"], repository_snapshot="s")
            self.assertEqual(context.chain_for("x.py"), ())
            self.assertFalse(context.is_complete)
            self.assertEqual(
                [(u.path, u.reason) for u in context.unresolved],
                [("AGENTS.md", UnresolvedReason.MALFORMED_ENCODING)],
            )

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root bypasses file mode bits")
    def test_unreadable_applicable_instruction_is_surfaced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            unreadable = _write(root, "AGENTS.md", "secret conventions\n")
            os.chmod(unreadable, 0o000)
            try:
                context = resolve_repository_instructions(root, ["x.py"], repository_snapshot="s")
            finally:
                os.chmod(unreadable, 0o644)
            self.assertFalse(context.is_complete)
            self.assertEqual(
                [(u.path, u.reason) for u in context.unresolved],
                [("AGENTS.md", UnresolvedReason.UNREADABLE)],
            )

    def test_unresolved_entry_changes_the_context_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "src/a.py", "pass\n")
            clean = resolve_repository_instructions(root, ["src/a.py"], repository_snapshot="s")
            (root / "AGENTS.md").write_bytes(b"\xff\xfe")
            incomplete = resolve_repository_instructions(root, ["src/a.py"], repository_snapshot="s")
            self.assertNotEqual(clean.identity, incomplete.identity)


class PassiveRunbookHierarchyWordingTests(unittest.TestCase):
    """The passive runbook must describe the same hierarchical repository-
    instruction model as the active runbook and the shared policy."""

    @classmethod
    def setUpClass(cls) -> None:
        runbooks = Path(__file__).resolve().parent.parent / "skills" / "github-pr-review" / "runbooks"
        cls.passive = " ".join(
            (runbooks / "passive-pr-review.md").read_text(encoding="utf-8").split()
        )
        cls.active = " ".join(
            (runbooks / "active-pr-review.md").read_text(encoding="utf-8").split()
        )

    def test_passive_runbook_describes_normalized_per_file_hierarchy(self) -> None:
        for token in (
            "root-to-specific",
            "hierarchical `AGENTS.md`",
            "`CLAUDE.md`",
            "normalized per-file Repository Instruction Context",
        ):
            self.assertIn(token, self.passive, f"passive runbook missing {token!r}")

    def test_passive_runbook_distinguishes_api_only_and_repository_backed_sources(self) -> None:
        self.assertIn("API-visible repository paths in API-only mode", self.passive)
        self.assertIn("verified temporary snapshot in repository-backed mode", self.passive)

    def test_passive_runbook_drops_the_imprecise_working_tree_phrasing(self) -> None:
        self.assertNotIn("from the working tree or verified temporary", self.passive)

    def test_active_and_passive_share_the_same_hierarchy_vocabulary(self) -> None:
        for token in ("root-to-specific", "API-visible"):
            self.assertIn(token, self.active)
            self.assertIn(token, self.passive)


if __name__ == "__main__":
    unittest.main()
