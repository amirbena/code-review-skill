#!/usr/bin/env python3
"""Documentation-contract coverage for Issue #34: the optional exact-HEAD
machine-readable review status for `github-pr-review`.

Pins the canonical policy (`review-status-enforcement.md`) and its
wire-in points (the policy index, `review-output.md`, both runbooks,
`parallel-review.md`, `SKILL.md`, package metadata, the packaging /
validation scripts, and the architecture docs) so a later edit cannot
quietly drop the SHA-binding invariant, the self-review success
prohibition, or the "no false green" rule.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

GITHUB = REPO_ROOT / "skills" / "github-pr-review"
POLICY = GITHUB / "policies" / "review-status-enforcement.md"
INDEX = GITHUB / "policies" / "github-review.md"
OUTPUT = GITHUB / "policies" / "review-output.md"
PARALLEL = GITHUB / "policies" / "parallel-review.md"
SKILL = GITHUB / "SKILL.md"
ACTIVE_RUNBOOK = GITHUB / "runbooks" / "active-pr-review.md"
PASSIVE_RUNBOOK = GITHUB / "runbooks" / "passive-pr-review.md"
METADATA = GITHUB / "metadata" / "skill.yaml"
PKG_SH = REPO_ROOT / "scripts" / "package-skills.sh"
PKG_PS1 = REPO_ROOT / "scripts" / "package-skills.ps1"
VALIDATOR = REPO_ROOT / "scripts" / "validate-skill-metadata.py"
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
COMPARISON = REPO_ROOT / "docs" / "CODE_REVIEW_COMPARISON.md"


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class CanonicalPolicyExists(unittest.TestCase):
    def test_file_exists_and_is_the_canonical_owner(self) -> None:
        self.assertTrue(POLICY.is_file())
        t = _norm(POLICY)
        self.assertIn("Canonical index", t)
        self.assertIn("exact-HEAD, machine-readable", t)
        self.assertIn("adds nothing to the verdict or to native-event authority", t)


class CoreInvariantsStated(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(POLICY)

    def test_separate_from_native_events(self) -> None:
        self.assertIn("Separate from native review events", self.t)
        self.assertIn("additional, optional", self.t)
        self.assertIn("never substitutes for the native authorization gate", self.t)

    def test_exact_head_binding_and_no_inherited_green(self) -> None:
        self.assertIn("Exact reviewed-HEAD binding", self.t)
        self.assertIn("status belongs only to SHA A", self.t)
        self.assertIn("inherits no status and no green from A", self.t)
        self.assertIn("until B is itself reviewed clean", self.t)
        self.assertIn("STATUS WITHHELD (HEAD advanced)", self.t)
        self.assertIn("never retarget the reviewed result onto the new SHA", self.t)

    def test_verdict_mapping_reuses_the_canonical_verdict(self) -> None:
        self.assertIn("no second engine", self.t.lower())
        self.assertIn("canonical verdict already", self.t)
        self.assertIn("introduces no second severity or verdict path", self.t)
        self.assertIn("No false green.", self.t)

    def test_blocking_vs_positive_authority_split(self) -> None:
        self.assertIn("blocking authority vs. positive authority", self.t)
        self.assertIn("blocking-only enforcement", self.t)
        self.assertIn("including a self-review", self.t)
        self.assertIn("can only make the merge gate stricter", self.t)
        self.assertIn("what a native APPROVE requires", self.t)
        self.assertIn("A self-review must never publish a success status.", self.t)
        self.assertIn("Ambiguity fails closed.", self.t)

    def test_enforcement_detection_reads_both_sources(self) -> None:
        self.assertIn("Enforcement-state detection", self.t)
        for state in ("ENFORCED", "NOT ENFORCED", "UNKNOWN"):
            self.assertIn(state, self.t)
        self.assertIn(
            "repository rulesets and classic branch protection", self.t
        )
        self.assertIn("never infers enforcement from the mere existence", self.t)

    def test_setup_is_explicit_minimal_preserving_idempotent(self) -> None:
        self.assertIn("Explicit opt-in required-check setup", self.t)
        self.assertIn("never happens during an ordinary review", self.t)
        for preserved in (
            "every existing required check",
            "every bypass actor",
            "dismiss_stale_reviews_on_push",
            "require_last_push_approval",
        ):
            self.assertIn(preserved, self.t)
        self.assertIn("Already required → no-op.", self.t)

    def test_no_merge(self) -> None:
        self.assertIn("No merge", self.t)
        self.assertIn("never enables auto-merge", self.t)


class WiredIntoPolicyFamily(unittest.TestCase):
    def test_index_lists_it_last_and_in_order(self) -> None:
        raw = INDEX.read_text(encoding="utf-8")
        self.assertIn("review-status-enforcement.md", raw)
        self.assertLess(
            raw.index("review-output.md"), raw.index("review-status-enforcement.md")
        )
        t = _norm(INDEX)
        self.assertIn("runs last", t)
        self.assertIn("adds nothing to the verdict or to native-event authority", t)

    def test_review_output_points_to_it_without_restating(self) -> None:
        t = _norm(OUTPUT)
        self.assertIn("Optional machine-readable review status", t)
        self.assertIn("review-status-enforcement.md", t)
        self.assertIn("does not restate that behavior", t)

    def test_parallel_review_reserves_publication_to_the_aggregator(self) -> None:
        t = _norm(PARALLEL)
        self.assertIn("review-status-enforcement.md", t)
        self.assertIn("only\nthe aggregating reviewer may publish".replace("\n", " "), t)


class WiredIntoEntrypointAndRunbooks(unittest.TestCase):
    def test_skill_names_the_boundary_and_links_the_policy(self) -> None:
        t = _norm(SKILL)
        self.assertIn("Optional machine-readable status.", t)
        self.assertIn("never\npublished by a self-review".replace("\n", " "), t)
        self.assertIn("A new HEAD inherits no green.", t)
        self.assertIn("policies/review-status-enforcement.md", t)

    def test_active_runbook_publishes_after_the_gate_and_binds_head(self) -> None:
        raw = ACTIVE_RUNBOOK.read_text(encoding="utf-8")
        t = _norm(ACTIVE_RUNBOOK)
        self.assertIn("Optional machine-readable status.", t)
        self.assertIn("review-status-enforcement.md", t)
        self.assertIn("STATUS WITHHELD (HEAD advanced)", t)
        self.assertLess(
            raw.index("submit permitted Approve/Request Changes"),
            raw.index("Optional machine-readable status"),
        )
        self.assertLess(
            raw.index("Optional machine-readable status"),
            raw.index("Guaranteed cleanup"),
        )

    def test_passive_runbook_publishes_no_status(self) -> None:
        t = _norm(PASSIVE_RUNBOOK)
        self.assertIn("No machine-readable status/check is published either.", t)
        self.assertIn("review-status-enforcement.md", t)


class WiredIntoMetadataAndScripts(unittest.TestCase):
    def test_metadata_declares_the_capability_and_keeps_can_merge_false(self) -> None:
        raw = METADATA.read_text(encoding="utf-8")
        self.assertIn("machine_readable_review_status: optional", raw)
        self.assertIn("required_check_setup: explicit-opt-in-only", raw)
        self.assertIn("publishes_machine_readable_status: conditional", raw)
        self.assertIn("can_merge: false", raw)

    def test_both_package_scripts_ship_the_policy(self) -> None:
        for script in (PKG_SH, PKG_PS1):
            self.assertIn(
                "policies/review-status-enforcement.md",
                script.read_text(encoding="utf-8"),
                script.name,
            )

    def test_validator_orders_and_marks_the_policy(self) -> None:
        raw = VALIDATOR.read_text(encoding="utf-8")
        self.assertIn('"review-status-enforcement.md"', raw)
        order_block = raw.split("GITHUB_POLICY_ORDER", 1)[1].split(")", 1)[0]
        self.assertIn("review-status-enforcement.md", order_block)
        self.assertLess(
            order_block.index("review-output.md"),
            order_block.index("review-status-enforcement.md"),
        )
        marker_block = raw.split("GITHUB_POLICY_MARKERS", 1)[1]
        self.assertIn('"review-status-enforcement.md": (', marker_block)


class WiredIntoArchitectureDocs(unittest.TestCase):
    def test_architecture_lists_it_as_implemented(self) -> None:
        t = _norm(ARCHITECTURE)
        self.assertIn("machine-readable review status", t)
        self.assertIn("review-status-enforcement.md", t)
        future = t.split("Future work (not implemented)", 1)[1]
        self.assertNotIn("merge-blocking / required status checks", future)

    def test_comparison_lists_it_as_implemented(self) -> None:
        t = _norm(COMPARISON)
        self.assertIn("Machine-readable review status", t)
        self.assertIn("review-status-enforcement.md", t)


if __name__ == "__main__":
    unittest.main()
