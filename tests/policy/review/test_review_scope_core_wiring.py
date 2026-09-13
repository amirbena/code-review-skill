#!/usr/bin/env python3
"""Core review-scope.md wiring and cross-Skill invariants.

Contract: shared/policies/review-scope.md as the canonical scope/routing
contract, reachable through both Skills' normal review step without being
duplicated or forked by either Skill. This module owns the file-wide
guards (no second source of truth, no per-Skill fork of shared prose) and
the routing checks that apply across every extracted behavioral pass,
rather than any single pass's own semantics — see
test_root_cause_and_model_completeness.py,
test_existing_behavior_and_failure_retry_ownership.py,
test_observability_and_metrics.py,
test_semantic_implication_and_null_absence.py,
test_architectural_placement_and_affected_test.py,
test_api_contract_compatibility.py, and
test_dependency_supply_chain_deepening.py for those.
Prose checks only — there is deliberately no second implementation of the
rules (see policies/skill-development-policy.md, "Runbook Design").
"""

from __future__ import annotations

import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import (
    EVIDENCE,
    GITHUB_REASONING,
    GITHUB_SKILL_DIR,
    GITHUB_SKILL_MD,
    LOCAL_RUNBOOK,
    LOCAL_SKILL_DIR,
    LOCAL_SKILL_MD,
    REVIEW_SCOPE,
    GITHUB_ACTIVE_RUNBOOK,
    GITHUB_PASSIVE_RUNBOOK,
)
from tests.support.policy_docs import load_normalized_text as _text

# The failure-retry-recovery pass was extracted from review-scope.md into
# its own canonical shared policy (Issue #264); this module only asserts
# that the runbook does not fork its prose, not the pass's own semantics.
FAILURE_RETRY_RECOVERY = REPO_ROOT / "shared/policies/failure-retry-recovery.md"


class RunbookReferencesCanonicalPoliciesTests(unittest.TestCase):
    """(1) local-review.md still references all canonical policies required
    for normal execution."""

    def setUp(self) -> None:
        self.text = _text(LOCAL_RUNBOOK)

    def test_always_applicable_shared_policies_are_referenced(self) -> None:
        for policy in (
            "review-scope.md",
            "severity.md",
            "evidence.md",
            "repository-instructions.md",
            "file-reviewability.md",
            "git-safety.md",
            "review-summary.md",
        ):
            self.assertIn(policy, self.text)

    def test_skill_owned_policies_are_referenced(self) -> None:
        for policy in ("invocation-approval.md", "repository-state.md"):
            self.assertIn(policy, self.text)

    def test_conditional_policies_are_referenced(self) -> None:
        for policy in ("review-context.md", "pr-context.md"):
            self.assertIn(policy, self.text)


class BehavioralHeuristicsReachableThroughReviewStepTests(unittest.TestCase):
    """(2) The new behavioral heuristics are reachable through the normal
    review phase, not disconnected prose."""

    def test_review_scope_defines_all_behavioral_heuristics(self) -> None:
        text = _text(REVIEW_SCOPE)
        self.assertIn("## Existing behavior ownership", text)
        self.assertIn("## Root-cause and model-completeness pass", text)
        self.assertIn("## Failure state, retry safety, and recovery", text)
        self.assertIn("## Related changes as one unit", text)
        self.assertIn(
            "## Architectural placement and execution-lifecycle fidelity", text
        )
        self.assertIn("## Affected-test / test-impact analysis", text)
        self.assertIn("## Semantic change-implication reasoning", text)
        self.assertIn("## Null-like absence-risk review", text)
        self.assertIn("## API / contract compatibility review", text)
        self.assertIn("## Dependency / supply-chain deepening review", text)

    def test_local_skill_always_loads_review_scope_and_evidence(self) -> None:
        text = _text(LOCAL_SKILL_MD)
        self.assertIn("review-scope.md", text)
        self.assertIn("evidence.md", text)

    def test_local_runbook_review_step_names_both_new_sections(self) -> None:
        review_step = self.text = _text(LOCAL_RUNBOOK)
        step9 = self.text.find("9. Review the complete delta against")
        step10 = self.text.find("10. Classify findings per")
        self.assertGreater(step9, -1)
        self.assertGreater(step10, step9)
        step9_body = self.text[step9:step10]
        self.assertIn("Semantic change-implication reasoning", step9_body)
        self.assertIn("Null-like absence-risk review", step9_body)
        self.assertIn("Existing behavior ownership", step9_body)
        self.assertIn("Root-cause and model-completeness pass", step9_body)
        self.assertIn("Failure state, retry safety, and recovery", step9_body)
        self.assertIn("Related changes as one unit", step9_body)
        self.assertIn(
            "Architectural placement and execution-lifecycle fidelity", step9_body
        )
        self.assertIn("Affected-test / test-impact analysis", step9_body)
        self.assertIn("API / contract compatibility review", step9_body)
        self.assertIn("Dependency / supply-chain deepening review", step9_body)


class RunbookDoesNotDuplicateBehavioralPolicyTextTests(unittest.TestCase):
    """(3) The runbook does not need to duplicate full behavioral policy
    text — it names the governing sections and lets them govern."""

    def setUp(self) -> None:
        self.runbook_text = _text(LOCAL_RUNBOOK)
        self.policy_text = _text(REVIEW_SCOPE)

    def test_ownership_search_gating_language_lives_only_in_the_policy(self) -> None:
        gating_phrase = (
            "perform a targeted search, scoped to the current delta's "
            "realistic blast radius, for an existing canonical owner"
        )
        self.assertIn(gating_phrase, self.policy_text)
        self.assertNotIn(gating_phrase, self.runbook_text)

    def test_failure_retry_trigger_conditions_live_only_in_the_policy(self) -> None:
        trigger_phrase = (
            "It triggers on a concrete signal in the diff: more than one "
            "side-effecting step"
        )
        self.assertIn(trigger_phrase, _text(FAILURE_RETRY_RECOVERY))
        self.assertNotIn(trigger_phrase, self.runbook_text)

    def test_observability_hierarchy_prose_lives_only_in_the_policy(self) -> None:
        hierarchy_phrase = "never a generic \"add more logs\" recommendation"
        self.assertIn(hierarchy_phrase, _text(FAILURE_RETRY_RECOVERY))
        self.assertNotIn(hierarchy_phrase, self.runbook_text)


class EvidenceScalingCrossReferenceTests(unittest.TestCase):
    """The new sections reuse existing blast-radius scaling rather than
    inventing a new evidentiary standard."""

    def test_evidence_md_cross_references_both_new_sections(self) -> None:
        text = _text(EVIDENCE)
        self.assertIn("Existing behavior ownership", text)
        self.assertIn("Failure state, retry safety, and recovery", text)
        self.assertIn(
            "Architectural placement and execution-lifecycle fidelity", text
        )
        self.assertIn("Affected-test / test-impact analysis", text)
        self.assertIn("Semantic change-implication reasoning", text)
        self.assertIn("Null-like absence-risk review", text)
        self.assertIn("API / contract compatibility review", text)
        self.assertIn("repository-wide audit", text)


class CrossSkillConsistencyTests(unittest.TestCase):
    """(cross-Skill) both Skills consume the intended shared behavioral
    policies; neither Skill contains an unnecessary fork/copy."""

    def test_both_skills_always_load_review_scope_and_evidence(self) -> None:
        local_text = _text(LOCAL_SKILL_MD)
        github_text = _text(GITHUB_SKILL_MD)
        self.assertIn("review-scope.md", local_text)
        self.assertIn("evidence.md", local_text)
        self.assertIn("review-scope.md", github_text)
        self.assertIn("evidence.md", github_text)

    def test_github_review_reasoning_forwards_generically_without_restating(
        self,
    ) -> None:
        text = _text(GITHUB_REASONING)
        self.assertIn("review-scope.md", text)
        self.assertIn("## Semantic Implication Review", text)
        self.assertIn("Semantic change-implication reasoning", text)
        self.assertIn("## Null-Like Absence-Risk Review", text)
        self.assertIn("Null-like absence-risk review", text)
        self.assertIn("Root-Cause and Model-Completeness Review", text)
        self.assertIn("Root-cause and model-completeness pass", text)
        self.assertIn("this file does not restate their full text", text)
        # The PR-specific forwarding subsection names the shared section but
        # does not fork its body.
        self.assertIn("## Architectural Placement Review", text)
        self.assertIn(
            "Architectural placement and execution-lifecycle fidelity", text
        )
        self.assertIn("not a second scope model", text)
        # The affected-test forwarding subsection names the shared section
        # without forking its heading or body.
        self.assertIn("## Affected-Test Impact Review", text)
        self.assertIn("Affected-test / test-impact analysis", text)
        # The API/contract compatibility forwarding subsection names the
        # shared section but does not fork its body.
        self.assertIn("## API / Contract Compatibility Review", text)
        self.assertIn("API / contract compatibility review", text)
        # The dependency/supply-chain forwarding subsection names the shared
        # section but does not fork its body.
        self.assertIn("## Dependency / Supply-Chain Deepening Review", text)
        self.assertIn("Dependency / supply-chain deepening review", text)
        # It must not have grown a private copy of the new section names —
        # it consumes them through the shared file, not by forking them.
        self.assertNotIn("## Existing behavior ownership", text)
        self.assertNotIn("## Failure state, retry safety, and recovery", text)
        self.assertNotIn(
            "## Architectural placement and execution-lifecycle fidelity", text
        )
        self.assertNotIn(
            "## Affected-test / test-impact analysis", text
        )
        self.assertNotIn(
            "## Semantic change-implication reasoning", text
        )
        self.assertNotIn("## Null-like absence-risk review", text)
        self.assertNotIn("## API / contract compatibility review", text)
        self.assertNotIn("## Dependency / supply-chain deepening review", text)
        self.assertNotIn("### When to expand context", text)
        self.assertNotIn("### Stop conditions", text)

    def test_github_runbooks_apply_review_scope_in_full(self) -> None:
        for runbook in (GITHUB_ACTIVE_RUNBOOK, GITHUB_PASSIVE_RUNBOOK):
            text = _text(runbook)
            self.assertIn("review-scope.md", text)

    def test_no_skill_specific_policy_forks_the_shared_section_text(self) -> None:
        # Every Skill-specific policy file, in either Skill, must not
        # contain a private copy of any shared heading — each lives in
        # review-scope.md (as a routing stub, checked positively above) and
        # its canonical owner file, never in a Skill-specific policy, and is,
        # incidentally, cross-linked by name (never restated) from
        # local-review.md/README docs.
        forbidden_headings = (
            "## Existing behavior ownership",
            "## Root-cause and model-completeness pass",
            "## Failure state, retry safety, and recovery",
            "## Architectural placement and execution-lifecycle fidelity",
            "## Affected-test / test-impact analysis",
            "## Semantic change-implication reasoning",
            "## Null-like absence-risk review",
            "## API / contract compatibility review",
            "## Dependency / supply-chain deepening review",
        )
        skill_policy_dirs = [
            LOCAL_SKILL_DIR / "policies",
            GITHUB_SKILL_DIR / "policies",
        ]
        for policy_dir in skill_policy_dirs:
            for policy_file in sorted(policy_dir.glob("*.md")):
                text = policy_file.read_text(encoding="utf-8")
                for heading in forbidden_headings:
                    self.assertNotIn(
                        heading,
                        text,
                        f"{policy_file} must not fork {heading!r} from "
                        "shared/policies/review-scope.md",
                    )


class NoSecondSourceOfTruthTests(unittest.TestCase):
    """(ownership of policy logic) this suite does not require, and this
    repository does not contain, a second hand-maintained implementation
    of the behavioral heuristics."""

    def test_behavioral_review_signals_module_was_removed(self) -> None:
        for candidate in (
            REPO_ROOT / "tests" / "reference" / "behavioral_review_signals.py",
            REPO_ROOT / "tests" / "support" / "behavioral_review_signals.py",
        ):
            self.assertFalse(candidate.exists())

    def test_no_python_module_imports_a_behavioral_signals_mirror(self) -> None:
        this_file = Path(__file__).resolve()
        for base in (REPO_ROOT / "tests" / "reference", REPO_ROOT / "tests" / "support"):
            for py_file in sorted(base.rglob("*.py")):
                if py_file.resolve() == this_file:
                    continue  # never scanned here, but keep the guard explicit
                text = py_file.read_text(encoding="utf-8")
                self.assertNotIn("behavioral_review_signals", text)


if __name__ == "__main__":
    unittest.main()
