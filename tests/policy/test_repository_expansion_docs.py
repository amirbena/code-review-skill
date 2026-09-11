"""Contract checks for the repository-expansion policy and its wiring (Issue #87)."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

POLICY = REPO_ROOT / "shared" / "policies" / "repository-expansion.md"
REVIEW_SCOPE = REPO_ROOT / "shared" / "policies" / "review-scope.md"
EVIDENCE = REPO_ROOT / "shared" / "policies" / "evidence.md"
SHARED_README = REPO_ROOT / "shared" / "policies" / "README.md"
REVIEW_SUMMARY = REPO_ROOT / "shared" / "templates" / "review-summary.md"
MANIFEST = REPO_ROOT / "scripts" / "package-manifest.json"


def _norm(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").replace("**", "").replace("`", ""))


class RepositoryExpansionPolicyContentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = POLICY.read_text(encoding="utf-8")
        self.norm = _norm(POLICY)

    def test_enumerates_every_expansion_trigger(self) -> None:
        for trigger in (
            "Call-site trigger",
            "Interface/contract trigger",
            "Migration/schema trigger",
            "Config-consumer trigger",
        ):
            self.assertIn(trigger, self.text)

    def test_ring_based_bounded_expansion(self) -> None:
        self.assertIn("## Bounded, ring-based expansion", self.text)
        for token in (
            "ring 0",
            "ring 1",
            "ring 2",
            "ring 3",
            "Stop at the first ring",
        ):
            self.assertIn(token, self.norm)

    def test_ceiling_scales_with_change_risk_depth(self) -> None:
        self.assertIn("## Expansion bound scales with change-risk depth", self.text)
        self.assertIn("change-risk-signals.md", self.text)
        self.assertIn("a ceiling, not a target", self.norm)
        self.assertIn("never forces expansion out to ring 3", self.norm)

    def test_determinism_section(self) -> None:
        self.assertIn("## Determinism", self.text)
        self.assertIn("no run-to-run variance", self.norm)

    def test_expansion_decisions_are_reported(self) -> None:
        self.assertIn("## Expansion decisions are reported", self.text)
        self.assertIn("never in the primary human-facing body", self.norm)
        self.assertIn('still emits the classification, as "none"', self.norm)

    def test_machine_readable_model(self) -> None:
        self.assertIn("repository_expansion:", self.text)
        self.assertIn("ring_reached:", self.text)

    def test_non_goals_and_ownership_boundary(self) -> None:
        self.assertIn("## Non-goals and ownership boundary", self.text)
        self.assertIn("Not a merge gate.", self.text)
        self.assertIn("No cross-repository expansion.", self.text)
        self.assertIn("Not a repository-wide audit.", self.text)

    def test_not_a_second_scope_or_evidence_model(self) -> None:
        self.assertIn("## Not a second scope or evidence model", self.text)
        self.assertIn("never lowers the evidence bar", self.norm)

    def test_always_active_no_toggle(self) -> None:
        self.assertIn("## Activation", self.text)
        self.assertIn("always active", self.norm)
        self.assertIn("no caller option to disable it", self.norm)


class RepositoryExpansionWiringTests(unittest.TestCase):
    def test_review_scope_section_precedes_technology_neutrality(self) -> None:
        text = REVIEW_SCOPE.read_text(encoding="utf-8")
        heading = text.index("## Repository expansion")
        neutrality = text.index("## Technology neutrality")
        self.assertLess(heading, neutrality)
        self.assertIn("repository-expansion.md", text)

    def test_evidence_ties_scaling_to_the_triggers(self) -> None:
        norm = _norm(EVIDENCE)
        self.assertIn("repository-expansion.md", EVIDENCE.read_text(encoding="utf-8"))
        self.assertIn("bounded, ring-based procedure", norm)

    def test_shared_readme_has_a_policy_map_row(self) -> None:
        self.assertIn("repository-expansion.md", SHARED_README.read_text(encoding="utf-8"))

    def test_review_summary_routes_it_to_subordinate_metadata(self) -> None:
        norm = _norm(REVIEW_SUMMARY)
        self.assertIn("repository-expansion.md", REVIEW_SUMMARY.read_text(encoding="utf-8"))
        self.assertIn("one exception to consumer-gating", norm)
        self.assertIn("never as a finding and never in a way that implies a verdict", norm)

    def test_packaged_in_the_one_shared_manifest(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        destinations = [entry["destination"] for entry in manifest["shared_files"]]
        self.assertIn("shared/policies/repository-expansion.md", destinations)

    def test_both_skills_load_and_list_the_policy(self) -> None:
        for path in (
            REPO_ROOT / "skills" / "local-code-review" / "SKILL.md",
            REPO_ROOT / "skills" / "github-pr-review" / "SKILL.md",
            REPO_ROOT / "skills" / "local-code-review" / "metadata" / "skill.yaml",
            REPO_ROOT / "skills" / "github-pr-review" / "metadata" / "skill.yaml",
            REPO_ROOT / "skills" / "local-code-review" / "runbooks" / "local-review.md",
            REPO_ROOT / "skills" / "github-pr-review" / "runbooks" / "active-pr-review.md",
            REPO_ROOT / "skills" / "github-pr-review" / "runbooks" / "passive-pr-review.md",
            REPO_ROOT / "skills" / "local-code-review" / "templates" / "local-review-report.md",
            REPO_ROOT / "skills" / "github-pr-review" / "templates" / "external-review-summary.md",
        ):
            with self.subTest(path=path):
                self.assertIn("repository-expansion.md", path.read_text(encoding="utf-8"))

    def test_both_runbooks_have_a_dedicated_expansion_step(self) -> None:
        for path in (
            REPO_ROOT / "skills" / "local-code-review" / "runbooks" / "local-review.md",
            REPO_ROOT / "skills" / "github-pr-review" / "runbooks" / "active-pr-review.md",
            REPO_ROOT / "skills" / "github-pr-review" / "runbooks" / "passive-pr-review.md",
        ):
            with self.subTest(path=path):
                norm = _norm(path)
                self.assertIn("Resolve repository expansion", norm)
                self.assertIn("never becomes a finding", norm)

    def test_local_report_renders_expansion_in_review_metadata(self) -> None:
        text = (
            REPO_ROOT
            / "skills"
            / "local-code-review"
            / "templates"
            / "local-review-report.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Repository expansion:", text)

    def test_github_template_renders_expansion_in_subordinate_block(self) -> None:
        text = (
            REPO_ROOT
            / "skills"
            / "github-pr-review"
            / "templates"
            / "external-review-summary.md"
        ).read_text(encoding="utf-8")
        self.assertIn("repository_expansion_triggers:", text)


class RepositoryExpansionDocsTests(unittest.TestCase):
    def test_architecture_and_comparison_and_feature_index_mention_it(self) -> None:
        for path in (
            REPO_ROOT / "docs" / "ARCHITECTURE.md",
            REPO_ROOT / "docs" / "CODE_REVIEW_COMPARISON.md",
            REPO_ROOT / "docs" / "features" / "README.md",
        ):
            with self.subTest(path=path):
                self.assertIn("repository-expansion.md", path.read_text(encoding="utf-8"))

    def test_feature_index_lists_it_as_not_a_feature_guide(self) -> None:
        text = (REPO_ROOT / "docs" / "features" / "README.md").read_text(encoding="utf-8")
        not_a_guide = text.split("## Not a feature guide", 1)[1]
        self.assertIn("repository-expansion.md", not_a_guide)

    def test_changelog_records_the_added_shared_policy(self) -> None:
        # The entry may still be under "## Unreleased" or may have already
        # moved under a released version heading (see CHANGELOG.md's own
        # "move under a version heading at release time" convention) — this
        # only pins that the changelog records it *somewhere*, in an
        # "### Added" section, not which release it landed in.
        text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("### Added", text)
        self.assertIn("repository-expansion.md", text)
        self.assertIn("(#87)", text)


if __name__ == "__main__":
    unittest.main()
