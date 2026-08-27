#!/usr/bin/env python3
"""Repository-instruction discovery/resolution contract tests.

Covers: instructions are resolved from the repository under review (never the
Skill repo or the reviewer's cwd); hierarchical AGENTS.md + CLAUDE.md
discovery; deterministic AGENTS/CLAUDE precedence from an explicit
target-repository determination; the present-but-unreadable vs.
genuinely-missing distinction. Behavioral, not exact-paragraph string
matching.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import pr_simulation as sim
from parallel_review import ReviewDimension, build_worker_inputs
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


class TargetRepositoryBoundaryTests(unittest.TestCase):
    """Instructions come from the repository under review — never the Skill's
    own repository, an unrelated checkout, or the reviewer's cwd."""

    def _reviewer_and_target(self, stack: tempfile.TemporaryDirectory):
        """Build a Skill-repo dir and a separate target-repo dir under one
        parent, mirroring the task's /tmp/code-review-skill + /tmp/target-repo
        fixture."""
        base = Path(stack)
        reviewer = base / "code-review-skill"
        target = base / "target-repo"
        _write(reviewer, "AGENTS.md", "REVIEWER REPO INSTRUCTION — MUST NOT LEAK\n")
        _write(target, "AGENTS.md", "target root convention\n")
        _write(target, "services/AGENTS.md", "target services convention\n")
        _write(target, "services/pay/handler.py", "pass\n")
        _write(target, "top.py", "pass\n")
        return reviewer, target

    def test_resolver_uses_the_explicitly_supplied_target_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, target = self._reviewer_and_target(tmp)
            context = resolve_repository_instructions(
                target, ["services/pay/handler.py", "top.py"], repository_snapshot="s"
            )
            self.assertEqual(
                [i.path for i in context.chain_for("services/pay/handler.py")],
                ["AGENTS.md", "services/AGENTS.md"],
            )
            self.assertEqual([i.path for i in context.chain_for("top.py")], ["AGENTS.md"])

    def test_reviewer_repo_agents_md_does_not_leak_into_the_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reviewer, target = self._reviewer_and_target(tmp)
            context = resolve_repository_instructions(
                target, ["services/pay/handler.py"], repository_snapshot="s"
            )
            all_content = "\n".join(
                i.content for _, chain in context.by_changed_file for i in chain
            )
            self.assertNotIn("MUST NOT LEAK", all_content)
            self.assertTrue((reviewer / "AGENTS.md").is_file())  # it exists, but is unreachable

    def test_an_agents_md_outside_the_target_root_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _write(base, "AGENTS.md", "OUTSIDE THE TARGET — MUST NOT APPLY\n")
            target = base / "target-repo"
            _write(target, "AGENTS.md", "target convention\n")
            _write(target, "src/x.py", "pass\n")
            context = resolve_repository_instructions(target, ["src/x.py"], repository_snapshot="s")
            self.assertEqual([i.content.strip() for i in context.chain_for("src/x.py")],
                             ["target convention"])

    def test_current_working_directory_does_not_affect_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reviewer, target = self._reviewer_and_target(tmp)
            expected = resolve_repository_instructions(
                target, ["services/pay/handler.py"], repository_snapshot="s"
            )
            original_cwd = os.getcwd()
            try:
                os.chdir(reviewer)  # cwd is the Skill repo — must not matter
                from_reviewer_cwd = resolve_repository_instructions(
                    target, ["services/pay/handler.py"], repository_snapshot="s"
                )
            finally:
                os.chdir(original_cwd)
            self.assertEqual(expected.identity, from_reviewer_cwd.identity)
            self.assertEqual(
                [i.path for i in from_reviewer_cwd.chain_for("services/pay/handler.py")],
                ["AGENTS.md", "services/AGENTS.md"],
            )

    def test_two_target_repos_with_different_instructions_have_different_identities(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_a, tempfile.TemporaryDirectory() as tmp_b:
            for root, text in ((Path(tmp_a), "repo A convention\n"), (Path(tmp_b), "repo B convention\n")):
                _write(root, "AGENTS.md", text)
                _write(root, "x.py", "pass\n")
            id_a = resolve_repository_instructions(Path(tmp_a), ["x.py"], repository_snapshot="snap").identity
            id_b = resolve_repository_instructions(Path(tmp_b), ["x.py"], repository_snapshot="snap").identity
            self.assertNotEqual(id_a, id_b)

    def test_parallel_worker_inputs_carry_the_target_repo_instruction_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, target = self._reviewer_and_target(tmp)
            context = resolve_repository_instructions(
                target, ["services/pay/handler.py", "top.py"], repository_snapshot="head-sha"
            )
            workers = build_worker_inputs(
                review_target="PR#1 delta",
                review_context="",
                repository_context_location=str(target),
                repository_snapshot_identity="head-sha",
                repository_instruction_context_identity=context.identity,
                existing_review_evidence="",
                dimensions=[
                    ReviewDimension.ARCHITECTURE_INVARIANTS,
                    ReviewDimension.CORRECTNESS_REGRESSION,
                ],
                policies_by_dimension={},
            )
            self.assertEqual(
                {w.repository_instruction_context_identity for w in workers}, {context.identity}
            )
            self.assertEqual(len({w.shared_key() for w in workers}), 1)


class AgentsClaudePrecedenceTests(unittest.TestCase):
    """AGENTS.md wins over CLAUDE.md ONLY when the target repository itself
    establishes it — supplied to the deterministic model as an explicit
    boolean, never inferred from prose, never a universal rule."""

    def _chain(self, agents_text: str, claude_text: str):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "AGENTS.md", agents_text)
            _write(root, "CLAUDE.md", claude_text)
            return resolve_repository_instructions(
                root, ["x.py"], repository_snapshot="s"
            ).chain_for("x.py")

    def test_declared_precedence_maps_the_explicit_determination(self) -> None:
        self.assertIs(
            declared_precedence(repository_declares_claude_defers_to_agents=True),
            InstructionPrecedence.CLAUDE_DEFERS_TO_AGENTS,
        )
        self.assertIs(
            declared_precedence(repository_declares_claude_defers_to_agents=False),
            InstructionPrecedence.NONE_DECLARED,
        )

    def test_explicit_target_repo_deferral_resolves_the_conflict(self) -> None:
        chain = self._chain("Use tabs.\n", "See AGENTS.md for the canonical rules.\n")
        self.assertIs(
            resolve_conflict(
                chain, materially_conflicts=True, repository_declares_claude_defers_to_agents=True
            ),
            ConflictOutcome.RESOLVED_BY_DECLARED_PRECEDENCE,
        )

    def test_no_supplied_deferral_leaves_a_material_conflict_ambiguous(self) -> None:
        chain = self._chain("Use tabs.\n", "Use two-space indentation.\n")
        self.assertIs(
            resolve_conflict(chain, materially_conflicts=True),
            ConflictOutcome.AMBIGUOUS_SURFACED,
        )

    def test_non_material_coexistence_is_no_conflict(self) -> None:
        chain = self._chain("Use tabs.\n", "Prefer descriptive test names.\n")
        self.assertIs(
            resolve_conflict(chain, materially_conflicts=False), ConflictOutcome.NO_CONFLICT
        )

    def test_claude_prose_cannot_establish_precedence(self) -> None:
        # Prose alone never sets precedence now — the first three tripped the
        # removed keyword heuristic; the last two show even a bare mention or a
        # genuine-sounding deferral is inert without the explicit boolean.
        prose = (
            "This CLAUDE.md is the canonical source of truth. AGENTS.md is generated from it.",
            "Our style guide is authoritative. See AGENTS.md for build commands.",
            "Read and follow the linter configuration. AGENTS.md documents the rationale.",
            "AGENTS.md exists in this repository.",
            "AGENTS.md is the authoritative instruction source; follow it.",
        )
        for claude_text in prose:
            with self.subTest(claude_text=claude_text):
                chain = self._chain("Use tabs.\n", claude_text + "\n")
                self.assertIs(
                    resolve_conflict(chain, materially_conflicts=True),
                    ConflictOutcome.AMBIGUOUS_SURFACED,
                )

    def test_unrelated_document_wording_cannot_change_the_deterministic_output(self) -> None:
        for claude_text in ("plain guidance\n", "AGENTS.md canonical authoritative source of truth\n"):
            chain = self._chain("Use tabs.\n", claude_text)
            self.assertIs(
                resolve_conflict(
                    chain, materially_conflicts=True, repository_declares_claude_defers_to_agents=False
                ),
                ConflictOutcome.AMBIGUOUS_SURFACED,
            )

    def test_no_universal_agents_over_claude_rule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root, "AGENTS.md", "Use tabs.\n")  # AGENTS.md only, no CLAUDE.md
            chain = resolve_repository_instructions(
                root, ["x.py"], repository_snapshot="s"
            ).chain_for("x.py")
            self.assertIs(
                resolve_conflict(
                    chain, materially_conflicts=True, repository_declares_claude_defers_to_agents=True
                ),
                ConflictOutcome.NO_CONFLICT,
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
    """The passive runbook must describe the same target-repository-anchored
    hierarchical model as the active runbook and the shared policy."""

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

    def test_passive_runbook_anchors_discovery_to_the_target_repository(self) -> None:
        self.assertIn(
            "verified temporary target-repository snapshot in repository-backed mode", self.passive
        )
        self.assertIn("target repository's API-visible paths in API-only mode", self.passive)
        self.assertIn("never from the Skill's own source checkout", self.passive)

    def test_passive_runbook_drops_the_imprecise_working_tree_phrasing(self) -> None:
        self.assertNotIn("from the working tree or verified temporary", self.passive)

    def test_active_and_passive_share_the_target_repo_hierarchy_vocabulary(self) -> None:
        for token in ("root-to-specific", "API-visible", "target-repository"):
            self.assertIn(token, self.active)
            self.assertIn(token, self.passive)


if __name__ == "__main__":
    unittest.main()
