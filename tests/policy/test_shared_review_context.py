#!/usr/bin/env python3
"""Regression coverage for the shared review-context / review-evidence model
and its wiring into both Skills, the architecture docs, and the comparison
doc. Structural prose checks, in the same style as test_pr_context_docs.py.

Run with:
    python3 -m unittest tests.policy.test_shared_review_context
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

SHARED = REPO_ROOT / "shared" / "policies"
LOCAL = REPO_ROOT / "skills" / "local-code-review"
GITHUB = REPO_ROOT / "skills" / "github-pr-review"

SHARED_CONTEXT = SHARED / "review-context.md"
SHARED_EVIDENCE = SHARED / "review-evidence.md"


def _text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class SharedPolicyFilesTests(unittest.TestCase):
    def test_shared_files_exist(self) -> None:
        self.assertTrue(SHARED_CONTEXT.is_file())
        self.assertTrue(SHARED_EVIDENCE.is_file())

    def test_context_names_the_four_concepts(self) -> None:
        t = _text(SHARED_CONTEXT)
        for concept in (
            "Review target",
            "Review context",
            "Repository context",
            "Existing review evidence",
        ):
            self.assertIn(concept, t)

    def test_context_lists_the_supported_input_forms(self) -> None:
        t = _text(SHARED_CONTEXT)
        for form in (
            "explicit user instructions",
            "Jira",
            "acceptance criteria",
            "GitHub Issue",
            "HLD",
            "ADR",
            "implementation plan",
            "PR/task description",
        ):
            self.assertIn(form, t)

    def test_context_is_optional_and_never_widens_target(self) -> None:
        t = _text(SHARED_CONTEXT)
        self.assertIn("Context never expands it", t)
        self.assertIn(
            "never a reason to fail, block, or degrade the review", t
        )
        self.assertIn("The review target stays the local delta / the PR", t)

    def test_context_keeps_the_code_first_evidence_hierarchy(self) -> None:
        t = _text(SHARED_CONTEXT)
        self.assertIn("actual code / diff / tests / configuration", t)
        self.assertIn("reviewer inference", t)

    def test_context_has_scope_boundary_reasoning_without_rigid_order(self) -> None:
        t = _text(SHARED_CONTEXT)
        self.assertIn("Scope-boundary reasoning", t)
        self.assertIn("There is no rigid global priority order", t)
        for case in (
            "Required behavior missing",
            "Implementation contradicts acceptance criteria",
            "Unrelated scope expansion",
            "Repository-policy violation",
        ):
            self.assertIn(case, t)
        self.assertIn(
            "Repository policy and invariants can constrain the implementation "
            "even when a ticket says otherwise",
            t,
        )
        self.assertIn(
            "An accepted ADR/HLD decision generally outweighs speculative "
            "ticket discussion",
            t,
        )
        self.assertIn(
            "Newer explicit maintainer clarification supersedes stale earlier "
            "discussion",
            t,
        )

    def test_context_explicit_non_goal_rule_is_present(self) -> None:
        # _text() strips ** and ` but keeps single-* emphasis, so match
        # around the emphasised words.
        t = _text(SHARED_CONTEXT).replace("*", "")
        self.assertIn(
            "A stated non-goal narrows what's expected to be built; it never "
            "narrows what's expected to be safe",
            t,
        )

    def test_context_grants_no_mutation_and_no_new_decision_path(self) -> None:
        t = _text(SHARED_CONTEXT)
        self.assertIn("it never grants either Skill a state-changing capability", t)
        self.assertIn("or any Jira mutation", t)
        self.assertIn("Jira access is context retrieval only", t)
        self.assertIn("It never adds a separate decision path", t)
        self.assertIn("never bypasses", t)

    def test_evidence_classifies_prior_findings(self) -> None:
        t = _text(SHARED_EVIDENCE)
        for status in (
            "still-relevant finding",
            "resolved finding",
            "stale finding",
            "duplicate",
            "settled decision",
            "speculative discussion",
        ):
            self.assertIn(status, t)

    def test_evidence_is_not_authority_and_not_the_target(self) -> None:
        t = _text(SHARED_EVIDENCE)
        self.assertIn("evidence and context, not authority", t)
        self.assertIn("Do not blindly inherit", t)
        self.assertIn(
            "It is Existing Review Evidence, not the review target", t
        )
        self.assertIn(
            "Prior review evidence never becomes an additional review target", t
        )

    def test_evidence_settled_decision_bar_and_challenge_rule(self) -> None:
        t = _text(SHARED_EVIDENCE)
        self.assertIn(
            "A decision is settled only when the prior evidence provides "
            "sufficient proof it was actually agreed upon",
            t,
        )
        self.assertIn(
            "Do not contradict a settled decision without such new evidence", t
        )
        self.assertIn(
            "Do not miss a still-unresolved previously identified issue", t
        )

    def test_evidence_absence_never_blocks(self) -> None:
        self.assertIn(
            "Missing or incomplete prior evidence is never a reason to fail, "
            "block, or degrade the review",
            _text(SHARED_EVIDENCE),
        )

    def test_evidence_interpreted_against_the_current_target(self) -> None:
        t = _text(SHARED_EVIDENCE)
        self.assertIn("## Interpret prior evidence against the current target", t)
        self.assertIn("not a correctness oracle", t)
        self.assertIn(
            "Regression after a resolved finding is a finding of this review", t
        )
        self.assertIn("An old approval never authorizes a new HEAD", t)
        self.assertIn("re-classify prior human findings against it", t)

    def test_evidence_has_authorship_authority_rule(self) -> None:
        t = _text(SHARED_EVIDENCE)
        self.assertIn(
            "## Comment authorship: human review vs. automation output", t
        )
        self.assertIn("Automation output alone never establishes a settled", t)
        for noise in ("deployment previews", "coverage bots", "CI status", "please rebase"):
            self.assertIn(noise, t)
        # Explicitly bounded — no trust-scoring machinery.
        self.assertIn(
            "no reviewer-reputation weighting, no bot allowlists", t
        )

    def test_behavioral_reference_model_exists_for_github_evidence(self) -> None:
        # The contract must be proven behaviorally, not only in prose.
        mod = REPO_ROOT / "tests" / "reference" / "pr_review_evidence.py"
        test = REPO_ROOT / "tests" / "unit" / "test_pr_review_evidence.py"
        self.assertTrue(mod.is_file())
        self.assertTrue(test.is_file())
        head = mod.read_text(encoding="utf-8")[:600]
        self.assertIn("Test-only", head)
        self.assertIn("not runtime logic, not packaged", head.lower())


class BothSkillsReferenceTheSharedModelTests(unittest.TestCase):
    def test_local_skill_md_loads_both_shared_policies(self) -> None:
        t = _text(LOCAL / "SKILL.md")
        self.assertIn("shared/policies/review-context.md", t)
        self.assertIn("shared/policies/review-evidence.md", t)

    def test_github_skill_md_loads_both_shared_policies(self) -> None:
        t = _text(GITHUB / "SKILL.md")
        self.assertIn("shared/policies/review-context.md", t)
        self.assertIn("shared/policies/review-evidence.md", t)

    def test_local_runbook_references_shared_model(self) -> None:
        t = _text(LOCAL / "runbooks" / "local-review.md")
        self.assertIn("shared/policies/review-context.md", t)
        self.assertIn("shared/policies/review-evidence.md", t)

    def test_github_runbooks_reference_shared_model(self) -> None:
        for runbook in ("active-pr-review.md", "passive-pr-review.md"):
            t = _text(GITHUB / "runbooks" / runbook)
            self.assertIn("shared/policies/review-context.md", t)
            self.assertIn("shared/policies/review-evidence.md", t)

    def test_local_thin_policies_defer_to_shared(self) -> None:
        ctx = _text(LOCAL / "policies" / "review-context.md")
        self.assertIn("local application", ctx)
        self.assertIn("shared/policies/review-context.md", ctx)
        pr = _text(LOCAL / "policies" / "pr-context.md")
        self.assertIn("local application", pr)
        self.assertIn("shared/policies/review-evidence.md", pr)

    def test_github_thin_policies_exist_and_defer_to_shared(self) -> None:
        ctx = GITHUB / "policies" / "review-context.md"
        ev = GITHUB / "policies" / "review-evidence.md"
        self.assertTrue(ctx.is_file())
        self.assertTrue(ev.is_file())
        ctx_t = _text(ctx)
        self.assertIn("thin application", ctx_t)
        self.assertIn("shared/policies/review-context.md", ctx_t)
        self.assertIn("The PR remains the review target", ctx_t)
        ev_t = _text(ev)
        self.assertIn("thin application", ev_t)
        self.assertIn("shared/policies/review-evidence.md", ev_t)

    def test_github_policy_index_lists_the_two_new_subpolicies_in_order(self) -> None:
        t = (GITHUB / "policies" / "github-review.md").read_text(encoding="utf-8")
        order = [
            "pr-scope.md",
            "review-context.md",
            "review-evidence.md",
            "review-reasoning.md",
        ]
        positions = [t.find(name) for name in order]
        self.assertTrue(all(p >= 0 for p in positions))
        self.assertEqual(positions, sorted(positions))


class GitHubIssueIsOptionalContextNotATargetTests(unittest.TestCase):
    def test_issue_is_explicit_only_no_auto_discovery(self) -> None:
        for path in (
            SHARED_CONTEXT,
            LOCAL / "SKILL.md",
            GITHUB / "SKILL.md",
            GITHUB / "policies" / "review-context.md",
            LOCAL / "policies" / "review-context.md",
        ):
            hay = _text(path).lower().replace("↔", "").replace("*", "")
            self.assertIn("no automatic pr", hay, f"{path} missing explicit-only note")

    def test_issue_never_becomes_a_review_target(self) -> None:
        self.assertIn(
            "never converts a Jira ticket, an Issue, an ADR, or a PR "
            "description into an additional review target",
            _text(SHARED_CONTEXT),
        )
        self.assertIn(
            "never converts a Jira ticket, a GitHub Issue, an ADR, or the PR "
            "description into an additional review target",
            _text(GITHUB / "policies" / "review-context.md"),
        )


class NoNewMutationOrDecisionChangeTests(unittest.TestCase):
    def test_local_metadata_still_declares_no_github_mutation(self) -> None:
        self.assertIn(
            "mutates_github: false",
            (LOCAL / "metadata" / "skill.yaml").read_text(encoding="utf-8"),
        )

    def test_github_metadata_mutation_still_conditional_only(self) -> None:
        t = (GITHUB / "metadata" / "skill.yaml").read_text(encoding="utf-8")
        self.assertIn("mutates_github: conditional", t)
        self.assertIn("mutates_repository: false", t)
        self.assertIn("can_merge: false", t)

    def test_github_review_context_policy_forbids_new_mutation(self) -> None:
        t = _text(GITHUB / "policies" / "review-context.md")
        self.assertIn("No new mutation", t)
        self.assertIn("maximum positive action (Approve) are unchanged", t)

    def test_decision_derivation_unchanged_language_present(self) -> None:
        self.assertIn(
            "It never adds a separate decision path", _text(SHARED_CONTEXT)
        )
        self.assertIn(
            "Decision derivation (mechanical)",
            _text(GITHUB / "policies" / "review-context.md"),
        )


class DocsReflectCurrentCapabilitiesTests(unittest.TestCase):
    def test_comparison_has_a_two_skill_section(self) -> None:
        t = _text(REPO_ROOT / "docs" / "CODE_REVIEW_COMPARISON.md")
        self.assertIn("local-code-review vs. github-pr-review", t)
        for row in (
            "Review target",
            "GitHub Issue context",
            "Existing Review Evidence",
            "Scope-boundary reasoning",
            "Final decision semantics",
            "Mutation / read-only boundaries",
            "Re-review behavior",
        ):
            self.assertIn(row, t)

    def test_comparison_keeps_only_merge_enforcement_and_pr_code_as_future(self) -> None:
        t = _text(REPO_ROOT / "docs" / "CODE_REVIEW_COMPARISON.md")
        self.assertIn("Planned / not yet implemented", t)
        self.assertIn("GitHub blocking status checks / merge enforcement", t)
        self.assertIn("Automatic execution of PR code", t)
        # Phase 2 shipped these — they must no longer be listed as future.
        future_block = t.split("Planned / not yet implemented", 1)[1].split("See also", 1)[0]
        self.assertNotIn("Temporary GitHub PR repository checkout", future_block)
        self.assertNotIn("Parallel / spawned execution", future_block)

    def test_comparison_shows_repository_backed_and_parallel_as_implemented(self) -> None:
        t = _text(REPO_ROOT / "docs" / "CODE_REVIEW_COMPARISON.md")
        for row in (
            "Repository-backed inspection",
            "temporary checkout",
            "base/head fidelity",
            "Parallel review capability",
            "sequential fallback",
            "centralized aggregation",
            "runtime portability",
            "simulated PR testing",
        ):
            self.assertIn(row, t)

    def test_architecture_shows_repository_backed_and_parallel_stages(self) -> None:
        t = _text(REPO_ROOT / "docs" / "ARCHITECTURE.md")
        self.assertIn("Normalize Inputs", t)
        self.assertIn("Existing Review Evidence", t)
        self.assertIn("Prepare Repository Context", t)
        self.assertIn("Temporary repository-backed mode", t)
        self.assertIn("Plan Review Execution", t)
        self.assertIn("Reconcile findings", t)
        self.assertIn("Future work (not implemented)", t)

    def test_architecture_keeps_merge_and_pr_code_execution_as_future(self) -> None:
        t = _text(REPO_ROOT / "docs" / "ARCHITECTURE.md")
        future_block = t.split("Future work (not implemented)", 1)[1].split("## 3.", 1)[0]
        self.assertIn("merge-blocking / required status checks", future_block)
        self.assertIn("Automatic execution of PR code", future_block)
        self.assertNotIn("repository-backed GitHub PR review", future_block)


PY_POLICY = REPO_ROOT / "policies" / "python_scripts_coding_policy.md"


class PythonScriptsCodingPolicyWiringTests(unittest.TestCase):
    def test_policy_file_exists_and_is_scoped(self) -> None:
        self.assertTrue(PY_POLICY.is_file())
        raw = PY_POLICY.read_text(encoding="utf-8")
        self.assertIn("scripts/**/*.py", raw)
        self.assertIn("tests/**/*.py", raw)
        t = _text(PY_POLICY)
        self.assertIn("not a universal Python style guide", t)
        self.assertIn("not packaged into either Skill archive", t)

    def test_agents_md_points_to_the_new_policy_without_inlining_it(self) -> None:
        t = _text(REPO_ROOT / "AGENTS.md")
        self.assertIn("Python Authoring", t)
        self.assertIn("policies/python_scripts_coding_policy.md", t)
        self.assertNotIn("PYTHON_AUTHORING", t)
        # only a short invariant, not the rule list
        self.assertNotIn("Remove or shorten a comment that mainly explains", t)

    def test_stale_python_authoring_filename_is_gone_everywhere(self) -> None:
        # This test file holds the old name only as fixture strings (below).
        offenders = []
        for path in REPO_ROOT.rglob("*"):
            if not path.is_file() or ".git" in path.parts or "dist" in path.parts:
                continue
            if path.suffix not in (".md", ".py", ".sh", ".ps1", ".yaml", ".yml"):
                continue
            if path.name == "test_shared_review_context.py":
                continue
            if "PYTHON_AUTHORING" in path.read_text(encoding="utf-8"):
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [], f"stale PYTHON_AUTHORING references: {offenders}")


class PackagedArchivesCarryTheSharedModelTests(unittest.TestCase):
    def test_package_scripts_list_the_new_shared_policies(self) -> None:
        for script in ("package-skills.sh", "package-skills.ps1"):
            t = (REPO_ROOT / "scripts" / script).read_text(encoding="utf-8")
            self.assertIn("review-context.md", t)
            self.assertIn("review-evidence.md", t)

    def test_github_package_lists_the_two_new_policies(self) -> None:
        t = (REPO_ROOT / "scripts" / "package-skills.sh").read_text(encoding="utf-8")
        self.assertIn('"policies/review-context.md"', t)
        self.assertIn('"policies/review-evidence.md"', t)


class DocPathMigrationTests(unittest.TestCase):
    """The repo-level docs and the Python authoring policy moved out of the
    repository root."""

    def test_new_locations_exist(self) -> None:
        for p in (
            REPO_ROOT / "docs" / "ARCHITECTURE.md",
            REPO_ROOT / "docs" / "CODE_REVIEW_COMPARISON.md",
            REPO_ROOT / "policies" / "python_scripts_coding_policy.md",
        ):
            self.assertTrue(p.is_file(), f"missing: {p}")

    def test_old_locations_are_gone(self) -> None:
        for p in (
            REPO_ROOT / "ARCHITECTURE.md",
            REPO_ROOT / "CODE_REVIEW_COMPARISON.md",
            REPO_ROOT / "PYTHON_AUTHORING.md",
            REPO_ROOT / "policies" / "PYTHON_AUTHORING.md",
        ):
            self.assertFalse(p.exists(), f"stale file still present: {p}")

    def test_no_markdown_link_targets_a_stale_doc_path(self) -> None:
        # A stale link resolves to an old location. Sibling links inside docs/
        # (ARCHITECTURE.md <-> CODE_REVIEW_COMPARISON.md) resolve within docs/.
        link_re = re.compile(r"\]\(([^)]+)\)")
        stale_targets = {
            REPO_ROOT / "ARCHITECTURE.md",
            REPO_ROOT / "CODE_REVIEW_COMPARISON.md",
            REPO_ROOT / "PYTHON_AUTHORING.md",
            REPO_ROOT / "policies" / "PYTHON_AUTHORING.md",
        }
        stale = []
        for md in REPO_ROOT.rglob("*.md"):
            if ".git" in md.parts or "dist" in md.parts:
                continue
            for target in link_re.findall(md.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                rel = target.split("#", 1)[0].strip()
                if not rel:
                    continue
                resolved = (md.parent / rel).resolve()
                if resolved in stale_targets:
                    stale.append(f"{md.relative_to(REPO_ROOT)} -> {target}")
        self.assertEqual(stale, [], f"stale doc links: {stale}")

    def test_every_relative_markdown_link_resolves(self) -> None:
        link_re = re.compile(r"\]\(([^)]+)\)")
        broken = []
        for md in REPO_ROOT.rglob("*.md"):
            if ".git" in md.parts or "dist" in md.parts:
                continue
            for target in link_re.findall(md.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                rel = target.split("#", 1)[0].strip()
                if not rel:
                    continue
                if not (md.parent / rel).exists():
                    broken.append(f"{md.relative_to(REPO_ROOT)} -> {target}")
        self.assertEqual(broken, [], f"broken relative links: {broken}")

    def test_agents_and_readme_reference_new_doc_paths(self) -> None:
        agents = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/ARCHITECTURE.md", agents)
        self.assertIn("policies/python_scripts_coding_policy.md", agents)
        self.assertIn("docs/ARCHITECTURE.md", readme)
        self.assertIn("docs/CODE_REVIEW_COMPARISON.md", readme)


if __name__ == "__main__":
    unittest.main()
