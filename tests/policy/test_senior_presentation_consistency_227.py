#!/usr/bin/env python3
"""Documentation-contract coverage for Issue #227.

Widens `human_review_output` (senior/human presentation) so it is
consistent across every human-facing `github-pr-review` surface, in both
passive and active publication, without touching the underlying finding
model:

1. Senior intent (an expanded, still-closed phrase vocabulary) resolves
   `human_review_output=true`, which by derived default also resolves
   `human_inline_findings=true`.
2. `human_review_output` governs a new **human full rendering** for any
   finding rendered in full in the review body (passive findings, and an
   active fallback finding with no valid inline anchor) — not
   `human_inline_findings`, which stays scoped to the GitHub inline
   surface only.
3. Publishing a previously produced passive review asks once for a
   presentation when the current publish request doesn't state one, and
   withholds publication rather than silently defaulting to structured.
4. `local-code-review` is untouched by all of the above.
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT

FINDING_RENDERING = REPO_ROOT / "shared/templates/finding-rendering.md"
FINDING = REPO_ROOT / "shared/templates/finding.md"
REVIEW_SUMMARY = REPO_ROOT / "shared/templates/review-summary.md"
INVOCATION = REPO_ROOT / "shared/policies/invocation-options.md"
GH_OUTPUT = REPO_ROOT / "skills/github-pr-review/policies/review-output.md"
GH_PLACEMENT = REPO_ROOT / "skills/github-pr-review/policies/finding-placement.md"
GH_SUMMARY = REPO_ROOT / "skills/github-pr-review/templates/external-review-summary.md"
GH_ACTIVE = REPO_ROOT / "skills/github-pr-review/runbooks/active-pr-review.md"
GH_PASSIVE = REPO_ROOT / "skills/github-pr-review/runbooks/passive-pr-review.md"
GH_SKILL = REPO_ROOT / "skills/github-pr-review/SKILL.md"
GH_METADATA = REPO_ROOT / "skills/github-pr-review/metadata/skill.yaml"
LOCAL_REPORT = REPO_ROOT / "skills/local-code-review/templates/local-review-report.md"
LOCAL_RUNBOOK = REPO_ROOT / "skills/local-code-review/runbooks/local-review.md"
LOCAL_METADATA = REPO_ROOT / "skills/local-code-review/metadata/skill.yaml"


def _norm(path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class SeniorPhraseVocabulary(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(INVOCATION)

    def test_new_senior_phrasings_are_documented(self) -> None:
        for phrase in (
            "senior review",
            "senior code review",
            "senior pr review",
            "review this as a senior",
        ):
            self.assertIn(phrase, self.t)

    def test_new_structured_negative_phrasings_are_documented(self) -> None:
        for phrase in ("structured format", "structured review"):
            self.assertIn(phrase, self.t)

    def test_still_a_closed_vocabulary_guarding_bare_as_a_senior(self) -> None:
        self.assertIn("This phrase set is exhaustive", self.t)
        self.assertIn("a bare as a senior with no review this", self.t)

    def test_offering_a_prior_value_is_distinguished_from_reusing_it(self) -> None:
        self.assertIn("Offering, never applying, a prior value", self.t)
        self.assertIn("recommended choice", self.t)
        self.assertIn(
            "Silently applying the prior value without asking remains forbidden",
            self.t,
        )


class HumanFullRenderingContract(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = FINDING_RENDERING.read_text(encoding="utf-8")
        self.t = _norm(FINDING_RENDERING)

    def test_section_exists(self) -> None:
        self.assertIn("## Canonical human full rendering", self.raw)

    def test_selected_by_human_review_output_not_inline_findings(self) -> None:
        self.assertIn(
            "Selected directly by human_review_output", self.t
        )
        self.assertIn("not by human_inline_findings", self.t)

    def test_keeps_id_and_location_unlike_inline(self) -> None:
        self.assertIn("id and canonical Location are kept as their own line", self.t)

    def test_local_code_review_is_unaffected(self) -> None:
        self.assertIn(
            "local-code-review has no inline/body split", self.t
        )

    def test_is_a_projection_not_a_weaker_finding(self) -> None:
        self.assertIn(
            "structured and human full are two renderings of one semantic "
            "finding",
            self.t,
        )
        self.assertIn(
            "rendering voice never moves it between the body and an inline "
            "comment",
            self.t,
        )

    def test_full_and_summary_pointer_renderings_are_no_longer_claimed_unaffected(
        self,
    ) -> None:
        # Issue #227 supersedes the old "full / summary-pointer renderings
        # above are never affected" claim for the full rendering: the full
        # rendering now has its own opt-in human projection.
        self.assertNotIn("the full / summary-pointer renderings above are never affected", self.t)
        self.assertIn("summary-pointer rendering is never affected by either presentation", self.t)

    def test_rules_section_lists_the_new_projection(self) -> None:
        self.assertIn("the opt-in human full rendering", self.t)
        self.assertIn("github-pr-review body/fallback surface only", self.t)


class FindingTemplatePointsAtBothProjections(unittest.TestCase):
    def test_finding_md_names_the_human_full_rendering(self) -> None:
        t = _norm(FINDING)
        self.assertIn("Canonical human full rendering", t)
        self.assertIn("review-body/fallback surface only", t)


class ReviewSummarySharedExtension(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = REVIEW_SUMMARY.read_text(encoding="utf-8")
        self.t = _norm(REVIEW_SUMMARY)

    def test_section_exists_and_is_github_only(self) -> None:
        self.assertIn(
            "### Human full rendering for body/fallback findings "
            "(`github-pr-review` only)",
            self.raw,
        )
        self.assertIn(
            "This subsection is an explicit, opt-in extension that only "
            "github-pr-review applies",
            self.t,
        )

    def test_local_code_review_stays_inert(self) -> None:
        self.assertIn(
            "local-code-review does not reference this subsection", self.t
        )

    def test_human_inline_findings_not_redefined(self) -> None:
        self.assertIn(
            "not by human_inline_findings — that companion option stays "
            "scoped to the GitHub inline surface",
            self.t,
        )


class GithubReviewOutputPublishQuestion(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = GH_OUTPUT.read_text(encoding="utf-8")
        self.t = _norm(GH_OUTPUT)

    def test_section_exists(self) -> None:
        self.assertIn(
            "### Publishing a previously produced passive review", self.raw
        )

    def test_asks_once_with_two_choices(self) -> None:
        self.assertIn("asks the user once", self.t)
        self.assertIn("Senior/human", self.t)
        self.assertIn("Structured", self.t)

    def test_recommends_but_never_silently_applies(self) -> None:
        self.assertIn("recommended choice", self.t)
        self.assertIn("never silently applied without an answer", self.t)

    def test_withholds_when_unresolvable_rather_than_defaulting_structured(
        self,
    ) -> None:
        self.assertIn(
            "withhold publication", self.t
        )
        self.assertIn(
            "Mutation: WITHHELD (publication format unresolved)", self.t
        )
        self.assertIn("rather than defaulting to structured", self.t)

    def test_skipped_for_one_shot_invocations(self) -> None:
        self.assertIn("asked only for that specific case", self.t)
        self.assertIn("senior review this PR and publish it", self.t)
        self.assertIn("post it in structured format", self.t)

    def test_body_finding_full_rendering_is_wired_here(self) -> None:
        self.assertIn("Canonical human full rendering", self.t)
        self.assertIn(
            "passive review's findings, or an active-review finding with no "
            "valid inline anchor",
            self.t,
        )
        self.assertIn(
            "human_inline_findings is never what governs a body finding's "
            "voice",
            self.t,
        )


class FindingPlacementRenderingVoiceExtended(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(GH_PLACEMENT)

    def test_human_review_output_governs_body_rendering_orthogonally(self) -> None:
        self.assertIn(
            "human_review_output similarly re-voices a finding rendered in "
            "full in the body",
            self.t,
        )
        self.assertIn("never changes inline-comment eligibility", self.t)
        self.assertIn(
            "Rendering voice never moves a finding between the body and an "
            "inline comment",
            self.t,
        )


class ExternalReviewSummaryFallbackVoicing(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(GH_SUMMARY)
        self.raw = GH_SUMMARY.read_text(encoding="utf-8")

    def test_fallback_section_documents_the_human_rendering(self) -> None:
        self.assertIn(
            "each of these body findings uses the human full rendering "
            "instead",
            self.t,
        )

    def test_human_inline_findings_does_not_govern_body_findings(self) -> None:
        self.assertIn(
            "human_inline_findings is scoped to this inline surface only",
            self.t,
        )
        self.assertIn(
            "It has no effect on a finding rendered in full in the body",
            self.t,
        )


class RunbooksWireTheContract(unittest.TestCase):
    def test_passive_runbook_uses_human_full_rendering_for_every_finding(
        self,
    ) -> None:
        t = _norm(GH_PASSIVE)
        self.assertIn(
            "Passive review has no inline surface, so every finding is a "
            "body finding",
            t,
        )
        self.assertIn("Canonical human full rendering", t)

    def test_active_runbook_has_the_publish_question_step(self) -> None:
        raw = GH_ACTIVE.read_text(encoding="utf-8")
        self.assertIn("3a. **If this invocation asks to publish/post a review", raw)
        t = _norm(GH_ACTIVE)
        self.assertIn("Senior/human", t)
        self.assertIn("Structured", t)
        self.assertIn(
            "Mutation: WITHHELD (publication format unresolved)", t
        )

    def test_active_runbook_fallback_findings_use_human_full_rendering(self) -> None:
        t = _norm(GH_ACTIVE)
        self.assertIn(
            "it still renders in full in the body", t
        )
        self.assertIn("Canonical human full rendering", t)

    def test_publish_question_precedes_review_mode_resolution(self) -> None:
        raw = GH_ACTIVE.read_text(encoding="utf-8")
        publish_step = raw.index("3a. **If this invocation asks to publish/post")
        mode_step = raw.index("4. **Resolve review mode**")
        self.assertLess(publish_step, mode_step)


class SkillEntrypointsUpdated(unittest.TestCase):
    def test_github_skill_names_new_phrases_and_body_scope(self) -> None:
        t = _norm(GH_SKILL)
        self.assertIn("senior review", t)
        self.assertIn("body/fallback finding", t)
        self.assertIn("Publishing a previously produced passive review", t)

    def test_github_metadata_documents_the_widened_option(self) -> None:
        raw = GH_METADATA.read_text(encoding="utf-8")
        self.assertIn("human_review_output: optional", raw)
        self.assertIn("senior code review", raw)
        self.assertIn("Canonical human full rendering", raw)
        self.assertIn(
            "body/fallback finding's wording is governed by "
            "`human_review_output` directly, not this option",
            raw,
        )


class LocalCodeReviewUnaffected(unittest.TestCase):
    def test_local_report_template_has_no_body_rendering_reference(self) -> None:
        t = _norm(LOCAL_REPORT)
        self.assertNotIn("Canonical human full rendering", t)

    def test_local_runbook_unchanged_by_this_issue(self) -> None:
        t = _norm(LOCAL_RUNBOOK)
        self.assertNotIn("Canonical human full rendering", t)

    def test_local_metadata_unaffected(self) -> None:
        raw = LOCAL_METADATA.read_text(encoding="utf-8")
        self.assertNotIn("Canonical human full rendering", raw)


if __name__ == "__main__":
    unittest.main()
