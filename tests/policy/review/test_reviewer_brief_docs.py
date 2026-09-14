"""Contract checks for the private Reviewer Brief policy and its wiring
(Issue #304): skills/github-pr-review/policies/reviewer-brief.md,
skills/github-pr-review/templates/reviewer-brief.md, and every file that
must reference it (github-review.md index, review-output.md's boundary
section, both runbooks, SKILL.md, the publication templates, the
packaging manifest, and docs/features/)."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

SKILL_DIR = REPO_ROOT / "skills" / "github-pr-review"
POLICY = SKILL_DIR / "policies" / "reviewer-brief.md"
TEMPLATE = SKILL_DIR / "templates" / "reviewer-brief.md"
GITHUB_REVIEW_INDEX = SKILL_DIR / "policies" / "github-review.md"
REVIEW_OUTPUT = SKILL_DIR / "policies" / "review-output.md"
PASSIVE_RUNBOOK = SKILL_DIR / "runbooks" / "passive-pr-review.md"
ACTIVE_RUNBOOK = SKILL_DIR / "runbooks" / "active-pr-review.md"
SKILL_MD = SKILL_DIR / "SKILL.md"
EXTERNAL_SUMMARY = SKILL_DIR / "templates" / "external-review-summary.md"
INLINE_FINDING = SKILL_DIR / "templates" / "inline-finding.md"
MANIFEST = REPO_ROOT / "scripts" / "packaging" / "package-manifest.json"
FEATURE_GUIDE = REPO_ROOT / "docs" / "features" / "reviewer-brief.md"
FEATURES_README = REPO_ROOT / "docs" / "features" / "README.md"
LOCAL_SKILL_MD = REPO_ROOT / "skills" / "local-code-review" / "SKILL.md"


def _norm(path: Path) -> str:
    return re.sub(
        r"\s+", " ", path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    )


class PolicyFileExistsAndDeclaresBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = POLICY.read_text(encoding="utf-8")
        self.norm = _norm(POLICY)

    def test_policy_file_exists(self) -> None:
        self.assertTrue(POLICY.is_file())

    def test_declares_never_published(self) -> None:
        self.assertIn("## Never published to GitHub", self.text)
        self.assertIn(
            "never submitted as a GitHub review body, inline comment, or",
            self.norm,
        )

    def test_declares_structural_not_textual_boundary(self) -> None:
        self.assertIn("structural boundary, not a textual filter", self.norm)

    def test_names_the_exclusive_publication_inputs(self) -> None:
        self.assertIn("external-review-summary.md", self.text)
        self.assertIn("inline-finding.md", self.text)
        self.assertIn("is never one of those inputs", self.norm)

    def test_declares_presentation_over_completed_analysis(self) -> None:
        self.assertIn(
            "private presentation artifact over already-completed",
            self.norm,
        )
        self.assertIn("it never influences it", self.norm)

    def test_required_fields_present(self) -> None:
        for field in (
            "What changed",
            "User-provided focus",
            "Manual review focus",
            "Open questions / assumptions",
        ):
            self.assertIn(field, self.text)

    def test_manual_review_focus_must_not_restate_findings(self) -> None:
        self.assertIn("must not simply restate the findings list", self.norm)

    def test_user_focus_is_attention_signal_not_authority(self) -> None:
        self.assertIn(
            "attention signal, not authority over review truth", self.norm
        )
        for phrase in (
            "cannot force a finding",
            "cannot lower the evidence bar",
            "cannot change a finding's severity",
            "cannot change coverage accounting",
            "cannot change verdict derivation",
        ):
            self.assertIn(phrase, self.norm)

    def test_no_leakage_of_hidden_state(self) -> None:
        self.assertIn("## No leakage of hidden state", self.text)
        for phrase in (
            "scratchpad or chain-of-thought reasoning",
            "machine-only authorization state, secrets, or hidden runtime metadata",
        ):
            self.assertIn(phrase, self.norm)

    def test_clean_review_still_gets_a_useful_brief(self) -> None:
        self.assertIn("## Clean reviews still get a useful brief", self.text)
        self.assertIn("never implies a false positive", self.norm)


class ModeCompositionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.norm = _norm(POLICY)

    def test_passive_vs_active_same_semantics(self) -> None:
        self.assertIn(
            "the same private brief semantics apply either way", self.norm
        )

    def test_human_review_output_wording_only(self) -> None:
        self.assertIn(
            "adjust the brief's wording and compactness only", self.norm
        )
        self.assertIn("never whether the brief exists", self.norm)

    def test_delta_re_review_summarizes_delta_not_history(self) -> None:
        self.assertIn(
            "the brief summarizes the reviewed delta, not the entire review history",
            self.norm,
        )

    def test_stacked_pr_summarizes_effective_layer(self) -> None:
        self.assertIn(
            "the brief summarizes the effective reviewed layer", self.norm
        )
        self.assertIn("not the entire stack", self.norm)

    def test_partitioned_pr_synthesized_once(self) -> None:
        self.assertIn(
            "the brief is synthesized once, over the final aggregated review target",
            self.norm,
        )
        self.assertIn("never once per partition", self.norm)


class TemplateFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = TEMPLATE.read_text(encoding="utf-8")
        self.norm = _norm(TEMPLATE)

    def test_template_file_exists(self) -> None:
        self.assertTrue(TEMPLATE.is_file())

    def test_canonical_shape_has_required_heading(self) -> None:
        self.assertIn("## Reviewer Brief", self.text)

    def test_worked_examples_present(self) -> None:
        for heading in (
            "## Clean review",
            "## Review with findings",
            "## Delta re-review",
            "## Stacked PR",
            "## Large-PR partitioning",
        ):
            self.assertIn(heading, self.text)

    def test_never_part_of_github_publication_payload_stated(self) -> None:
        self.assertIn(
            "Never part of the GitHub publication payload", self.text
        )

    def test_partitioned_example_is_singular_not_per_partition(self) -> None:
        section = re.search(
            r"## Large-PR partitioning\n(.*?)(?=\n## `human_review_output`|\Z)",
            self.text,
            re.S,
        )
        self.assertIsNotNone(section)
        body = section.group(1)
        self.assertNotIn("Partition 1", body)
        self.assertNotIn("Partition 2", body)
        self.assertIn("Synthesized **once**", body)


class WiringIntoGithubReviewIndexTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = GITHUB_REVIEW_INDEX.read_text(encoding="utf-8")
        self.norm = _norm(GITHUB_REVIEW_INDEX)

    def test_reviewer_brief_in_ordered_sub_policy_list(self) -> None:
        self.assertIn("reviewer-brief.md", self.text)

    def test_runs_after_review_output_in_declared_order(self) -> None:
        review_output_idx = self.text.index("review-output.md ")
        reviewer_brief_idx = self.text.index("reviewer-brief.md ")
        self.assertLess(review_output_idx, reviewer_brief_idx)

    def test_never_influences_finalized_result_stated(self) -> None:
        self.assertIn("it reads that finalized result and never influences it", self.norm)


class WiringIntoReviewOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = REVIEW_OUTPUT.read_text(encoding="utf-8")
        self.norm = _norm(REVIEW_OUTPUT)

    def test_private_reviewer_brief_section_exists(self) -> None:
        self.assertIn("## Private Reviewer Brief (never published)", self.text)

    def test_states_exclusive_construction_inputs(self) -> None:
        self.assertIn(
            "constructed exclusively from", self.norm
        )
        self.assertIn("is never one of those inputs", self.norm)


class WiringIntoRunbooksTests(unittest.TestCase):
    def test_passive_runbook_composes_the_brief(self) -> None:
        text = PASSIVE_RUNBOOK.read_text(encoding="utf-8")
        norm = _norm(PASSIVE_RUNBOOK)
        self.assertIn("reviewer-brief.md", text)
        self.assertIn("Compose the private Reviewer Brief", norm)

    def test_active_runbook_composes_the_brief_separately_from_construction(self) -> None:
        text = ACTIVE_RUNBOOK.read_text(encoding="utf-8")
        norm = _norm(ACTIVE_RUNBOOK)
        self.assertIn("reviewer-brief.md", text)
        self.assertIn("Compose the private Reviewer Brief", norm)
        self.assertIn("is not part of the review constructed in step", norm)
        self.assertIn("never added to the review body", norm)
        self.assertIn("never added to the inline-comments array", norm)

    def test_active_runbook_brief_step_precedes_submission_steps(self) -> None:
        text = ACTIVE_RUNBOOK.read_text(encoding="utf-8")
        brief_idx = text.index("13a. **Compose the private Reviewer Brief**")
        gate_idx = text.index('14. **Apply the review-action authorization gate**')
        submit_idx = text.index("16. **Submit the one review**")
        self.assertLess(brief_idx, gate_idx)
        self.assertLess(gate_idx, submit_idx)


class WiringIntoSkillMdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = SKILL_MD.read_text(encoding="utf-8")
        self.norm = _norm(SKILL_MD)

    def test_safety_boundary_bullet_present(self) -> None:
        self.assertIn("Reviewer Brief is private and never published", self.norm)

    def test_output_contract_mentions_brief(self) -> None:
        self.assertIn("policies/reviewer-brief.md", self.text)
        self.assertIn("structurally excluded from", self.norm)


class PublicationTemplatesDisclaimBriefTests(unittest.TestCase):
    def test_external_review_summary_states_exclusivity(self) -> None:
        text = EXTERNAL_SUMMARY.read_text(encoding="utf-8")
        norm = _norm(EXTERNAL_SUMMARY)
        self.assertIn("reviewer-brief.md", text)
        self.assertIn(
            "the exclusive source of what", norm
        )

    def test_reviewer_brief_never_appears_in_rendered_examples(self) -> None:
        text = EXTERNAL_SUMMARY.read_text(encoding="utf-8")
        for block in re.findall(r"```markdown\n(.*?)\n```", text, re.S):
            self.assertNotIn("Reviewer Brief", block)

    def test_inline_finding_disclaims_brief(self) -> None:
        text = INLINE_FINDING.read_text(encoding="utf-8")
        self.assertIn("reviewer-brief.md", text)
        self.assertIn("never appears in an inline comment", text)


class PackagingManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_policy_and_template_are_packaged_for_github_skill(self) -> None:
        sources = {
            entry["source"] for entry in self.manifest["skills"]["github"]["files"]
        }
        self.assertIn("skills/github-pr-review/policies/reviewer-brief.md", sources)
        self.assertIn("skills/github-pr-review/templates/reviewer-brief.md", sources)


class NonGoalNeverAddedToLocalCodeReviewTests(unittest.TestCase):
    def test_local_skill_md_has_no_reviewer_brief_reference(self) -> None:
        text = LOCAL_SKILL_MD.read_text(encoding="utf-8")
        self.assertNotIn("Reviewer Brief", text)
        self.assertNotIn("reviewer-brief.md", text)


class DocumentationImpactTests(unittest.TestCase):
    def test_feature_guide_exists(self) -> None:
        self.assertTrue(FEATURE_GUIDE.is_file())

    def test_feature_guide_states_never_published(self) -> None:
        norm = _norm(FEATURE_GUIDE)
        self.assertIn("never published to github", norm.lower())

    def test_features_readme_lists_it(self) -> None:
        text = FEATURES_README.read_text(encoding="utf-8")
        self.assertIn("Reviewer Brief", text)
        self.assertIn("reviewer-brief.md", text)


if __name__ == "__main__":
    unittest.main()
