#!/usr/bin/env python3
"""Documentation-contract coverage for Issue #140.

Two contracts, pinned so a later edit cannot quietly drop them:

1. `human_review_output` — an opt-in, natural-language-only presentation
   option (no CLI-style flag) that renders only the final human-facing
   review summary in a concise senior-engineer voice, changing nothing
   about findings, severity, deduplication, the verdict, the GitHub
   review state, inline comments, or any machine-readable status.
2. Publication ordering — `final review comment == last publication
   event`: for `github-pr-review` the one batched review carries the
   final summary, any machine-readable status is published before that
   submission, and nothing review-owned is published or edited after it,
   whether or not human-style mode is on.

Also guards against cross-Skill drift: the option is defined once in
shared policy with one default, and both Skills wire it in consistently.
"""

from __future__ import annotations

import re
import unittest

from tests.support.paths import REPO_ROOT

INVOCATION = REPO_ROOT / "shared/policies/invocation-options.md"
SHARED_SUMMARY = REPO_ROOT / "shared/templates/review-summary.md"
GH_SKILL = REPO_ROOT / "skills/github-pr-review/SKILL.md"
GH_OUTPUT = REPO_ROOT / "skills/github-pr-review/policies/review-output.md"
GH_STATUS = REPO_ROOT / "skills/github-pr-review/policies/review-status-enforcement.md"
GH_INDEX = REPO_ROOT / "skills/github-pr-review/policies/github-review.md"
GH_SUMMARY = REPO_ROOT / "skills/github-pr-review/templates/external-review-summary.md"
GH_ACTIVE = REPO_ROOT / "skills/github-pr-review/runbooks/active-pr-review.md"
GH_PASSIVE = REPO_ROOT / "skills/github-pr-review/runbooks/passive-pr-review.md"
GH_METADATA = REPO_ROOT / "skills/github-pr-review/metadata/skill.yaml"
LOCAL_SKILL = REPO_ROOT / "skills/local-code-review/SKILL.md"
LOCAL_REPORT = REPO_ROOT / "skills/local-code-review/templates/local-review-report.md"
LOCAL_RUNBOOK = REPO_ROOT / "skills/local-code-review/runbooks/local-review.md"
LOCAL_METADATA = REPO_ROOT / "skills/local-code-review/metadata/skill.yaml"
COMPARISON = REPO_ROOT / "docs/CODE_REVIEW_COMPARISON.md"
ARCHITECTURE = REPO_ROOT / "docs/ARCHITECTURE.md"

INVARIANT = "final review comment == last publication event"


def _norm(path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class OptionDefinedOnceInSharedPolicy(unittest.TestCase):
    def setUp(self) -> None:
        self.t = _norm(INVOCATION)

    def test_canonical_option_and_shared_default(self) -> None:
        self.assertIn("human_review_output — default false for both Skills", self.t)
        self.assertIn("final human-facing review summary", self.t)
        self.assertIn("senior-engineer-voice rendering", self.t)

    def test_natural_language_contract_no_cli_flag(self) -> None:
        self.assertIn("The user-facing contract is natural language", self.t)
        self.assertIn("no\nrequired CLI-style flag such as --human-review-output".replace("\n", " "), self.t)
        self.assertIn("assignment is still\nhonored for\nmediation parity".replace("\n", " "), self.t)

    def test_finite_phrase_vocabulary_is_documented_and_exhaustive(self) -> None:
        self.assertIn("human_review_output phrasings", self.t)
        for phrase in (
            "shorter and more human",
            "like a senior engineer",
            "concise review comments",
            "keep the full summary",
            "do not shorten the review",
        ):
            self.assertIn(phrase, self.t)
        self.assertIn("This phrase set is exhaustive", self.t)
        self.assertIn("make it nicer", self.t)  # named as an explicit non-trigger

    def test_option_is_presentation_only_including_ordering(self) -> None:
        self.assertIn("changes only the wording of the final summary", self.t)
        self.assertIn("the order in which a review's artifacts are published", self.t)
        self.assertIn("keeps the final human-facing summary as the last review-owned publication", self.t)
        self.assertIn("HEAD/SHA validation, or publication ordering", self.t)

    def test_the_four_concepts_are_named(self) -> None:
        self.assertIn(
            "four canonical option concepts: fix prompt, fix guidance, "
            "finding details, and human review output",
            self.t,
        )


class SharedSummaryTemplateCarriesTheConciseShape(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = SHARED_SUMMARY.read_text(encoding="utf-8")
        self.t = _norm(SHARED_SUMMARY)

    def test_section_exists_and_is_opt_in(self) -> None:
        self.assertIn("## Concise human-style summary (opt-in)", self.raw)
        self.assertIn("When the invocation selects human_review_output", self.t)
        self.assertIn("instead of the structured canonical shape above", self.t)

    def test_concise_shape_content_rules(self) -> None:
        for token in (
            "safe to merge / proceed",
            "what's good",
            "what's concerning",
            "what to change",
            "P0 / P1 / P2 label when it is referenced",
            "raised as a question",
        ):
            self.assertIn(token, self.t)

    def test_excludes_process_and_machine_language(self) -> None:
        self.assertIn("excludes internal review-process language", self.t)
        for token in ("review mode", "base/head SHAs", "file or finding counts", "action mode"):
            self.assertIn(token, self.t)

    def test_states_semantic_equivalence_with_mode_off(self) -> None:
        self.assertIn(
            "Mode on and mode off produce identical findings and severities",
            self.t,
        )
        # GitHub-only guarantees are named as GitHub-only, not imposed on local.
        self.assertIn(
            "for github-pr-review, identical GitHub review state and "
            "machine-readable status",
            self.t,
        )
        self.assertIn(
            "never changes finding detection, severity classification, "
            "finding identity or deduplication, re-review semantics",
            self.t,
        )
        self.assertIn("where a Skill has them", self.t)
        self.assertIn(
            "When the option is off (the default), the structured canonical "
            "shape above is used unchanged",
            self.t,
        )


class GithubPublicationOrderingInvariant(unittest.TestCase):
    def test_review_output_states_the_invariant(self) -> None:
        t = _norm(GH_OUTPUT)
        self.assertIn(INVARIANT, t)
        self.assertIn(
            "the optional machine-readable status/check is published before that "
            "submission, never after it",
            t,
        )
        self.assertIn(
            "This ordering is identical whether or not human_review_output is enabled",
            t,
        )
        raw = GH_OUTPUT.read_text(encoding="utf-8")
        block = re.search(r"## Submission ordering\n\n```text\n(.*?)\n```", raw, re.S).group(1)
        self.assertLess(
            block.index("publish any optional machine-readable status"),
            block.index("submit that one review submission"),
        )

    def test_status_policy_publishes_before_the_final_summary(self) -> None:
        t = _norm(GH_STATUS)
        self.assertIn("before the final human-facing summary comment", t)
        self.assertIn(INVARIANT, t)
        self.assertIn("same whether or not human_review_output is enabled", t)

    def test_policy_index_notes_status_precedes_the_final_summary(self) -> None:
        t = _norm(GH_INDEX)
        self.assertIn(
            "its publication is placed before the final human-facing summary comment",
            t,
        )

    def test_active_runbook_orders_status_between_the_gate_and_the_final_submission(self) -> None:
        raw = GH_ACTIVE.read_text(encoding="utf-8")
        gate = raw.index("**Apply the review-action authorization gate**")
        status = raw.index("**Publish any optional machine-readable status**")
        submit = raw.index("**Submit the one review**")
        cleanup = raw.index("Guaranteed cleanup")
        self.assertLess(gate, status)
        self.assertLess(status, submit)
        self.assertLess(submit, cleanup)
        t = _norm(GH_ACTIVE)
        self.assertIn("is the last review-owned\npublication of the run".replace("\n", " "), t)
        self.assertIn(INVARIANT, t)
        self.assertIn("STATUS WITHHELD (HEAD advanced)", t)


class GithubSummaryTemplateConciseOptIn(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = GH_SUMMARY.read_text(encoding="utf-8")
        self.t = _norm(GH_SUMMARY)

    def test_opt_in_section_exists(self) -> None:
        self.assertIn("## Concise human-style body (opt-in)", self.raw)
        self.assertIn("natural language only", self.t)

    def test_findings_still_appear_once_with_severity_labels(self) -> None:
        self.assertIn(
            "Every blocking finding still appears — once — as a summary-pointer "
            "line keeping its P0 / P1 / P2 label",
            self.t,
        )

    def test_byte_identical_to_mode_off_except_wording(self) -> None:
        self.assertIn("byte-identical to the mode-off review", self.t)
        self.assertIn("only this body's wording changes", self.t)

    def test_still_one_batched_submission_and_last_event(self) -> None:
        self.assertIn(
            "still submitted as part of the one batched review submission, which "
            "stays the final publication event for the run",
            self.t,
        )

    def test_self_review_uses_the_same_concise_comment(self) -> None:
        self.assertIn(
            "A self-review uses this same concise body as its informational COMMENT",
            self.t,
        )


class LocalSkillConciseOptIn(unittest.TestCase):
    def test_local_report_template_documents_it(self) -> None:
        t = _norm(LOCAL_REPORT)
        self.assertIn("Concise human-style output (opt-in)", t)
        self.assertIn("natural language only", t)
        self.assertIn(
            "still follow it, subordinate and unchanged, and nothing else is "
            "appended after the summary",
            t,
        )
        self.assertIn(
            "findings, severities, evidence, reconciliation, source attribution, "
            "and the mechanical Decision are identical on and off",
            t,
        )

    def test_local_runbook_wires_it_into_the_compose_step(self) -> None:
        t = _norm(LOCAL_RUNBOOK)
        self.assertIn("human_review_output", t)
        self.assertIn("concise senior-engineer voice", t)
        self.assertIn(
            "findings, severities, evidence, and mechanical Decision are identical "
            "to the mode-off report",
            t,
        )


class WiredConsistentlyIntoBothSkills(unittest.TestCase):
    def test_both_skill_entrypoints_list_the_option_default_off(self) -> None:
        for path in (GH_SKILL, LOCAL_SKILL):
            t = _norm(path)
            self.assertIn("human_review_output", t)
            self.assertIn("default false", t)
            self.assertTrue(("no CLI flag" in t) or ("no flag" in t), path.name)

    def test_both_skill_entrypoints_call_it_a_natural_language_opt_in(self) -> None:
        for path in (GH_SKILL, LOCAL_SKILL):
            t = _norm(path).lower()
            self.assertIn("natural language", t)
            self.assertIn("senior-engineer voice", t)

    def test_both_metadata_declare_the_presentation_option(self) -> None:
        for path in (GH_METADATA, LOCAL_METADATA):
            raw = path.read_text(encoding="utf-8")
            self.assertIn("human_review_output: optional", raw)
            self.assertIn("presentation-only", raw)
            self.assertIn("no CLI flag", raw)

    def test_github_metadata_declares_the_ordering_invariant(self) -> None:
        raw = GH_METADATA.read_text(encoding="utf-8")
        self.assertIn("final_summary_is_last_publication: true", raw)
        self.assertIn(INVARIANT, raw)

    def test_passive_runbook_also_supports_the_concise_summary(self) -> None:
        t = _norm(GH_PASSIVE)
        self.assertIn("human_review_output", t)
        self.assertIn("concise senior-engineer voice", t)
        self.assertIn("Passive review publishes nothing", t)

    def test_default_off_is_the_compatible_shape_everywhere(self) -> None:
        # Every concise section is explicitly opt-in / default-off, never a
        # replacement of the default structured summary.
        self.assertIn("(opt-in)", SHARED_SUMMARY.read_text(encoding="utf-8"))
        self.assertIn("(opt-in)", GH_SUMMARY.read_text(encoding="utf-8"))
        self.assertIn("(opt-in)", LOCAL_REPORT.read_text(encoding="utf-8"))


class DocsRecordBothContracts(unittest.TestCase):
    def test_comparison_lists_the_option_and_the_ordering_invariant(self) -> None:
        t = _norm(COMPARISON)
        self.assertIn("Human-style summary output", t)
        self.assertIn("human_review_output", t)
        self.assertIn("Publication ordering", t)
        self.assertIn(INVARIANT, t)

    def test_architecture_lists_the_option_and_the_ordering_invariant(self) -> None:
        t = _norm(ARCHITECTURE)
        self.assertIn("human_review_output", t)
        self.assertIn("natural-language-only", t)
        self.assertIn(INVARIANT, t)
        self.assertIn("The final-summary voice is presentation-only.", t)


if __name__ == "__main__":
    unittest.main()
