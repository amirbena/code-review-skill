#!/usr/bin/env python3
"""Semantic tests for deterministic review invocation options."""

from __future__ import annotations

import unittest

from tests.reference.review.invocation_options import normalize


LOCAL_DEFAULTS = {
    "include_fix_prompt": False,
    "include_fix_guidance": True,
    "include_finding_details": True,
    "human_review_output": False,
    # no static default: derived from human_review_output when unset
    "human_inline_findings": False,
}
GITHUB_DEFAULTS = {
    "include_fix_prompt": False,
    "include_fix_guidance": True,
    "include_finding_details": False,
    "human_review_output": False,
    "human_inline_findings": False,
}


class InvocationNormalizationTests(unittest.TestCase):
    def test_canonical_and_natural_fix_prompt_forms_are_equivalent(self) -> None:
        forms = (
            "include_fix_prompt=true",
            "include_fix_prompt",
            "include fix prompt",
            "include-fix-prompt",
            "give me a fix prompt",
        )
        self.assertTrue(all(normalize(f, defaults=LOCAL_DEFAULTS)["include_fix_prompt"] for f in forms))

    def test_fix_guidance_equivalents_are_supported(self) -> None:
        forms = (
            "include_fix_guidance=true",
            "include_fix_guidance",
            "include fix guidance",
            "give me fix guidance",
        )
        self.assertTrue(all(normalize(f, defaults={**LOCAL_DEFAULTS, "include_fix_guidance": False})["include_fix_guidance"] for f in forms))

    def test_canonical_false_beats_every_affirmative_form(self) -> None:
        result = normalize(
            "give me a fix prompt; include_fix_prompt=true; include_fix_prompt=false",
            defaults=LOCAL_DEFAULTS,
        )
        self.assertFalse(result["include_fix_prompt"])

    def test_explicit_natural_negative_is_respected(self) -> None:
        defaults = {**LOCAL_DEFAULTS, "include_fix_prompt": True}
        result = normalize("do not include a fix prompt", defaults=defaults)
        self.assertFalse(result["include_fix_prompt"])

    def test_conflicting_natural_values_fall_back_to_default(self) -> None:
        text = "include fix prompt, but do not include a fix prompt"
        self.assertFalse(normalize(text, defaults=LOCAL_DEFAULTS)["include_fix_prompt"])
        defaults_true = {**LOCAL_DEFAULTS, "include_fix_prompt": True}
        self.assertTrue(normalize(text, defaults=defaults_true)["include_fix_prompt"])

    def test_ambiguous_language_does_not_set_options(self) -> None:
        self.assertEqual(
            normalize("Be detailed and helpful.", defaults=GITHUB_DEFAULTS),
            GITHUB_DEFAULTS,
        )
        self.assertEqual(
            normalize("What does include_fix_prompt do?", defaults=LOCAL_DEFAULTS),
            LOCAL_DEFAULTS,
        )
        mixed = normalize(
            "What does include_fix_prompt do? Give me a fix prompt.",
            defaults=LOCAL_DEFAULTS,
        )
        self.assertTrue(mixed["include_fix_prompt"])

    def test_invocations_do_not_leak(self) -> None:
        first = normalize("include finding details", defaults=GITHUB_DEFAULTS)
        second = normalize("review this PR", defaults=GITHUB_DEFAULTS)
        self.assertTrue(first["include_finding_details"])
        self.assertFalse(second["include_finding_details"])

    def test_direct_and_agent_mediated_forms_have_parity(self) -> None:
        direct = normalize("give me a fix prompt", defaults=LOCAL_DEFAULTS)
        mediated = normalize("include_fix_prompt=true", defaults=LOCAL_DEFAULTS)
        self.assertEqual(direct, mediated)


class HumanReviewOutputOptionTests(unittest.TestCase):
    """Issue #140: the opt-in concise senior-engineer summary mode, requested
    in natural language (no CLI-style flag required)."""

    def test_natural_affirmative_phrasings_enable_it(self) -> None:
        for text in (
            "make the review shorter and more human",
            "publish this like a senior engineer reviewing the PR",
            "review it as a senior engineer",
            "use concise review comments",
            "human review output",
            "human-review-output",
            "human_review_output=true",
        ):
            with self.subTest(text=text):
                self.assertTrue(
                    normalize(text, defaults=GITHUB_DEFAULTS)["human_review_output"]
                )

    def test_explicit_negatives_force_it_off(self) -> None:
        on = {**GITHUB_DEFAULTS, "human_review_output": True}
        for text in (
            "no, keep the full summary",
            "keep the default summary",
            "do not shorten the review",
            "don't shorten the review",
            "no human review output",
            "human_review_output=false",
        ):
            with self.subTest(text=text):
                self.assertFalse(normalize(text, defaults=on)["human_review_output"])

    def test_ambiguous_or_vague_language_does_not_set_it(self) -> None:
        on = {**GITHUB_DEFAULTS, "human_review_output": True}
        off = dict(GITHUB_DEFAULTS)
        for text in (
            "make it nicer",
            "be brief",
            "tighten it up",
            "be more thorough",
            "What does human_review_output do?",
        ):
            with self.subTest(text=text):
                # Neither default is flipped: the option is simply not set.
                self.assertTrue(normalize(text, defaults=on)["human_review_output"])
                self.assertFalse(normalize(text, defaults=off)["human_review_output"])

    def test_canonical_false_beats_a_natural_affirmative_phrasing(self) -> None:
        result = normalize(
            "review it like a senior engineer; human_review_output=false",
            defaults=GITHUB_DEFAULTS,
        )
        self.assertFalse(result["human_review_output"])

    def test_conflicting_natural_values_fall_back_to_default(self) -> None:
        text = "review it like a senior engineer but keep the full summary"
        self.assertFalse(normalize(text, defaults=GITHUB_DEFAULTS)["human_review_output"])
        on = {**GITHUB_DEFAULTS, "human_review_output": True}
        self.assertTrue(normalize(text, defaults=on)["human_review_output"])

    def test_direct_and_mediated_forms_have_parity(self) -> None:
        direct = normalize("make the review shorter and more human", defaults=GITHUB_DEFAULTS)
        mediated = normalize("human_review_output=true", defaults=GITHUB_DEFAULTS)
        self.assertEqual(direct, mediated)

    def test_the_option_does_not_leak_between_invocations(self) -> None:
        first = normalize("review like a senior engineer", defaults=GITHUB_DEFAULTS)
        second = normalize("review this PR", defaults=GITHUB_DEFAULTS)
        self.assertTrue(first["human_review_output"])
        self.assertFalse(second["human_review_output"])

    def test_both_skills_share_one_default_off(self) -> None:
        # The option is defined once in shared policy with the same default for
        # both Skills — mode-off is the compatible default everywhere.
        for defaults in (LOCAL_DEFAULTS, GITHUB_DEFAULTS):
            self.assertFalse(defaults["human_review_output"])
            self.assertFalse(
                normalize("review this", defaults=defaults)["human_review_output"]
            )

    def test_selecting_human_output_changes_no_unrelated_option(self) -> None:
        # Semantic-equivalence guard: turning the summary voice on/off leaves
        # every option other than the human-rendering pair exactly as it was.
        # `human_inline_findings` co-varies *by design* (derived default).
        off = normalize("review this PR", defaults=GITHUB_DEFAULTS)
        on = normalize(
            "review this PR, and make the review shorter and more human",
            defaults=GITHUB_DEFAULTS,
        )
        self.assertTrue(on.pop("human_review_output"))
        self.assertTrue(on.pop("human_inline_findings"))
        off.pop("human_review_output", None)
        off.pop("human_inline_findings", None)
        self.assertEqual(on, off)


class SeniorPhraseExpansionTests(unittest.TestCase):
    """Issue #227: the expanded senior-intent phrase vocabulary for
    `human_review_output` — common wording that previously did not resolve
    senior mode at all."""

    def test_new_affirmative_phrasings_enable_it(self) -> None:
        for text in (
            "senior review",
            "do a senior code review",
            "senior PR review",
            "review this as a senior",
        ):
            with self.subTest(text=text):
                self.assertTrue(
                    normalize(text, defaults=GITHUB_DEFAULTS)["human_review_output"]
                )

    def test_new_negative_phrasings_force_it_off(self) -> None:
        on = {**GITHUB_DEFAULTS, "human_review_output": True}
        for text in ("structured format", "structured review"):
            with self.subTest(text=text):
                self.assertFalse(normalize(text, defaults=on)["human_review_output"])

    def test_bare_as_a_senior_is_not_a_trigger(self) -> None:
        # Deliberately excluded per Issue #227: avoid an overly broad bare
        # "as a senior" false-positive trigger outside the closed phrase set.
        for text in ("as a senior", "I want this as a senior would see it"):
            with self.subTest(text=text):
                self.assertFalse(
                    normalize(text, defaults=GITHUB_DEFAULTS)["human_review_output"]
                )

    def test_one_shot_publish_request_with_stated_senior_intent(self) -> None:
        result = normalize(
            "senior review this PR and publish it", defaults=GITHUB_DEFAULTS
        )
        self.assertTrue(result["human_review_output"])
        self.assertTrue(result["human_inline_findings"])

    def test_one_shot_publish_request_with_stated_structured_format(self) -> None:
        result = normalize(
            "review #123 and post it in structured format", defaults=GITHUB_DEFAULTS
        )
        self.assertFalse(result["human_review_output"])

    def test_plain_publish_request_resolves_nothing(self) -> None:
        # "publish it" alone carries no presentation wording; the option
        # falls through to the Skill default, exactly like any other
        # invocation with no recognized phrase.
        result = normalize("publish it", defaults=GITHUB_DEFAULTS)
        self.assertFalse(result["human_review_output"])


class HumanInlineFindingsOptionTests(unittest.TestCase):
    """Issue #166: the companion inline-rendering option whose default is
    derived — `human_inline_findings = explicit_value ?? human_review_output`
    — and which acts only on `github-pr-review`'s inline-comment surface."""

    def test_derived_default_follows_human_review_output(self) -> None:
        # unset: inherits whatever human_review_output resolved to
        self.assertFalse(
            normalize("review this PR", defaults=GITHUB_DEFAULTS)["human_inline_findings"]
        )
        on = normalize("review it like a senior engineer", defaults=GITHUB_DEFAULTS)
        self.assertTrue(on["human_review_output"])
        self.assertTrue(on["human_inline_findings"])
        canonical = normalize("human_review_output=true", defaults=GITHUB_DEFAULTS)
        self.assertTrue(canonical["human_inline_findings"])

    def test_explicit_false_wins_while_summary_stays_human(self) -> None:
        for text in (
            "review it like a senior engineer; human_inline_findings=false",
            "make the review shorter and more human, but keep the structured inline comments",
            "review like a senior engineer and keep the inline comment template",
        ):
            with self.subTest(text=text):
                result = normalize(text, defaults=GITHUB_DEFAULTS)
                self.assertTrue(result["human_review_output"])
                self.assertFalse(result["human_inline_findings"])

    def test_explicit_true_wins_while_summary_stays_structured(self) -> None:
        for text in (
            "human_inline_findings=true",
            "review this PR and use human inline findings",
            "give me human inline comments",
        ):
            with self.subTest(text=text):
                result = normalize(text, defaults=GITHUB_DEFAULTS)
                self.assertFalse(result["human_review_output"])
                self.assertTrue(result["human_inline_findings"])

    def test_canonical_false_beats_a_natural_affirmative(self) -> None:
        result = normalize(
            "use human inline findings; human_inline_findings=false",
            defaults=GITHUB_DEFAULTS,
        )
        self.assertFalse(result["human_inline_findings"])

    def test_conflicting_natural_values_fall_back_to_the_derived_default(self) -> None:
        text = "use human inline findings but keep the structured inline comments"
        # ambiguous -> derived default -> follows human_review_output (off here)
        self.assertFalse(normalize(text, defaults=GITHUB_DEFAULTS)["human_inline_findings"])
        on = "review like a senior engineer; " + text
        self.assertTrue(normalize(on, defaults=GITHUB_DEFAULTS)["human_inline_findings"])

    def test_vague_language_does_not_set_it(self) -> None:
        for text in ("make it nicer", "be brief", "tighten the comments up"):
            with self.subTest(text=text):
                self.assertFalse(
                    normalize(text, defaults=GITHUB_DEFAULTS)["human_inline_findings"]
                )

    def test_direct_and_mediated_forms_have_parity(self) -> None:
        direct = normalize("use human inline findings", defaults=GITHUB_DEFAULTS)
        mediated = normalize("human_inline_findings=true", defaults=GITHUB_DEFAULTS)
        self.assertEqual(direct, mediated)

    def test_it_does_not_leak_between_invocations(self) -> None:
        first = normalize("review like a senior engineer", defaults=GITHUB_DEFAULTS)
        second = normalize("review this PR", defaults=GITHUB_DEFAULTS)
        self.assertTrue(first["human_inline_findings"])
        self.assertFalse(second["human_inline_findings"])

    def test_local_defaults_also_carry_the_derived_value(self) -> None:
        # normalized for parity; the Skill simply has no inline surface to act on
        self.assertFalse(
            normalize("review this", defaults=LOCAL_DEFAULTS)["human_inline_findings"]
        )
        self.assertTrue(
            normalize("review like a senior engineer", defaults=LOCAL_DEFAULTS)[
                "human_inline_findings"
            ]
        )


if __name__ == "__main__":
    unittest.main()
