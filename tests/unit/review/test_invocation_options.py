#!/usr/bin/env python3
"""Semantic tests for deterministic review invocation options."""

from __future__ import annotations

import unittest
from typing import Any

from tests.reference.review.invocation_options import normalize


LOCAL_DEFAULTS = {
    "include_fix_prompt": False,
    "include_fix_guidance": True,
    "include_finding_details": True,
    "human_review_output": False,
    # no static default: derived from human_review_output when unset
    "human_inline_findings": False,
    # local-code-review has no severity legend; normalized for parity only
    "include_severity_description": False,
    "structured_review_result": False,
}
GITHUB_DEFAULTS = {
    "include_fix_prompt": False,
    "include_fix_guidance": True,
    "include_finding_details": False,
    "human_review_output": False,
    "human_inline_findings": False,
    "include_severity_description": False,
    "structured_review_result": False,
}


def _on(defaults: dict[str, bool], key: str) -> dict[str, bool]:
    return {**defaults, key: True}


def _off(defaults: dict[str, bool], key: str) -> dict[str, bool]:
    return {**defaults, key: False}


# Per-option contract table: axis -> case data. An axis an option omits was
# never asserted for it. `conflict` holds (text, defaults, expected) triples;
# `extra` pins other options' values alongside the target option.
CONTRACTS: dict[str, dict[str, Any]] = {
    "include_fix_prompt": {
        "enables": {
            "phrases": (
                "include_fix_prompt=true",
                "include_fix_prompt",
                "include fix prompt",
                "include-fix-prompt",
                "give me a fix prompt",
            ),
            "defaults": LOCAL_DEFAULTS,
        },
        "forces_off": {
            "phrases": ("do not include a fix prompt",),
            "defaults": _on(LOCAL_DEFAULTS, "include_fix_prompt"),
        },
        "unset": {
            "phrases": ("Be detailed and helpful.", "What does include_fix_prompt do?"),
            "defaults": (LOCAL_DEFAULTS,),
        },
        "canonical_false": {
            "text": "give me a fix prompt; include_fix_prompt=true; include_fix_prompt=false",
            "defaults": LOCAL_DEFAULTS,
        },
        "conflict": (
            (
                "include fix prompt, but do not include a fix prompt",
                LOCAL_DEFAULTS,
                False,
            ),
            (
                "include fix prompt, but do not include a fix prompt",
                _on(LOCAL_DEFAULTS, "include_fix_prompt"),
                True,
            ),
        ),
        "parity": {
            "direct": "give me a fix prompt",
            "mediated": "include_fix_prompt=true",
            "defaults": LOCAL_DEFAULTS,
        },
    },
    "include_fix_guidance": {
        "enables": {
            "phrases": (
                "include_fix_guidance=true",
                "include_fix_guidance",
                "include fix guidance",
                "give me fix guidance",
            ),
            "defaults": _off(LOCAL_DEFAULTS, "include_fix_guidance"),
        },
    },
    "include_finding_details": {
        "no_leak": {
            "first": "include finding details",
            "second": "review this PR",
            "defaults": GITHUB_DEFAULTS,
        },
    },
    "human_review_output": {
        "enables": {
            "phrases": (
                "make the review shorter and more human",
                "publish this like a senior engineer reviewing the PR",
                "review it as a senior engineer",
                "use concise review comments",
                "human review output",
                "human-review-output",
                "human_review_output=true",
            ),
            "defaults": GITHUB_DEFAULTS,
        },
        "forces_off": {
            "phrases": (
                "no, keep the full summary",
                "keep the default summary",
                "do not shorten the review",
                "don't shorten the review",
                "no human review output",
                "human_review_output=false",
            ),
            "defaults": _on(GITHUB_DEFAULTS, "human_review_output"),
        },
        "unset": {
            "phrases": (
                "make it nicer",
                "be brief",
                "tighten it up",
                "be more thorough",
                "What does human_review_output do?",
            ),
            "defaults": (
                _on(GITHUB_DEFAULTS, "human_review_output"),
                GITHUB_DEFAULTS,
            ),
        },
        "canonical_false": {
            "text": "review it like a senior engineer; human_review_output=false",
            "defaults": GITHUB_DEFAULTS,
        },
        "conflict": (
            (
                "review it like a senior engineer but keep the full summary",
                GITHUB_DEFAULTS,
                False,
            ),
            (
                "review it like a senior engineer but keep the full summary",
                _on(GITHUB_DEFAULTS, "human_review_output"),
                True,
            ),
        ),
        "parity": {
            "direct": "make the review shorter and more human",
            "mediated": "human_review_output=true",
            "defaults": GITHUB_DEFAULTS,
        },
        "no_leak": {
            "first": "review like a senior engineer",
            "second": "review this PR",
            "defaults": GITHUB_DEFAULTS,
        },
    },
    # Issue #166: the derived default is `explicit ?? human_review_output`, so
    # "explicit true/false wins" also pins what the summary option stays at.
    "human_inline_findings": {
        "enables": {
            "phrases": (
                "human_inline_findings=true",
                "review this PR and use human inline findings",
                "give me human inline comments",
            ),
            "defaults": GITHUB_DEFAULTS,
            "extra": {"human_review_output": False},
        },
        "forces_off": {
            "phrases": (
                "review it like a senior engineer; human_inline_findings=false",
                "make the review shorter and more human, but keep the structured inline comments",
                "review like a senior engineer and keep the inline comment template",
            ),
            "defaults": GITHUB_DEFAULTS,
            "extra": {"human_review_output": True},
        },
        "unset": {
            "phrases": ("make it nicer", "be brief", "tighten the comments up"),
            "defaults": (GITHUB_DEFAULTS,),
        },
        "canonical_false": {
            "text": "use human inline findings; human_inline_findings=false",
            "defaults": GITHUB_DEFAULTS,
        },
        # ambiguous -> derived default -> follows human_review_output
        "conflict": (
            (
                "use human inline findings but keep the structured inline comments",
                GITHUB_DEFAULTS,
                False,
            ),
            (
                "review like a senior engineer; "
                "use human inline findings but keep the structured inline comments",
                GITHUB_DEFAULTS,
                True,
            ),
        ),
        "parity": {
            "direct": "use human inline findings",
            "mediated": "human_inline_findings=true",
            "defaults": GITHUB_DEFAULTS,
        },
        "no_leak": {
            "first": "review like a senior engineer",
            "second": "review this PR",
            "defaults": GITHUB_DEFAULTS,
        },
    },
    # Issue #275
    "include_severity_description": {
        "enables": {
            "phrases": (
                "include severity descriptions",
                "show severity descriptions",
                "show blocking/non-blocking labels",
                "include_severity_description",
                "include severity description",
                "include-severity-description",
                "include_severity_description=true",
            ),
            "defaults": GITHUB_DEFAULTS,
        },
        "forces_off": {
            "phrases": (
                "keep severity compact",
                "do not include severity descriptions",
                "don't include severity descriptions",
                "show only p0/p1/p2",
                "include_severity_description=false",
            ),
            "defaults": _on(GITHUB_DEFAULTS, "include_severity_description"),
        },
        "unset": {
            "phrases": (
                "be more detailed",
                "what does include_severity_description do?",
                "severity matters here",
            ),
            "defaults": (
                _on(GITHUB_DEFAULTS, "include_severity_description"),
                GITHUB_DEFAULTS,
            ),
        },
        "canonical_false": {
            "text": "show severity descriptions; include_severity_description=false",
            "defaults": GITHUB_DEFAULTS,
        },
        "conflict": (
            (
                "show severity descriptions but keep severity compact",
                GITHUB_DEFAULTS,
                False,
            ),
            (
                "show severity descriptions but keep severity compact",
                _on(GITHUB_DEFAULTS, "include_severity_description"),
                True,
            ),
        ),
        "parity": {
            "direct": "show severity descriptions",
            "mediated": "include_severity_description=true",
            "defaults": GITHUB_DEFAULTS,
        },
        "no_leak": {
            "first": "show severity descriptions",
            "second": "review this PR",
            "defaults": GITHUB_DEFAULTS,
        },
    },
    "structured_review_result": {
        "enables": {
            "phrases": (
                "structured_review_result=true",
                "structured review result",
                "include a structured review result",
                "give me a machine-readable review result",
                "emit the review result as JSON",
            ),
            "defaults": LOCAL_DEFAULTS,
        },
        "forces_off": {
            "phrases": (
                "structured_review_result=false",
                "no machine-readable review result",
                "human report only",
            ),
            "defaults": LOCAL_DEFAULTS,
        },
        "unset": {
            "phrases": (
                "give me json",
                "make it parseable",
                "What does structured_review_result do?",
            ),
            "defaults": (LOCAL_DEFAULTS,),
        },
        "conflict": (
            (
                "machine-readable review result but human report only",
                LOCAL_DEFAULTS,
                False,
            ),
        ),
    },
}


class _ContractAxes:
    """Axis assertions shared by every option; `OPTION`/`CASES` come from the
    generated subclass, so a failure names the option (class) and axis (method)."""

    OPTION: str
    CASES: dict[str, Any]

    def _case(self, axis: str) -> dict[str, Any]:
        return self.CASES[axis]

    def _check_phrases(self, axis: str, expected: bool) -> None:
        case = self._case(axis)
        for text in case["phrases"]:
            with self.subTest(text=text):
                result = normalize(text, defaults=case["defaults"])
                self.assertEqual(result[self.OPTION], expected)
                for key, value in case.get("extra", {}).items():
                    self.assertEqual(result[key], value)

    def test_natural_affirmative_phrasings_enable_it(self) -> None:
        self._check_phrases("enables", True)

    def test_explicit_negatives_force_it_off(self) -> None:
        self._check_phrases("forces_off", False)

    def test_ambiguous_or_vague_language_does_not_set_it(self) -> None:
        # Neither default is flipped: the option is simply not set.
        case = self._case("unset")
        for text in case["phrases"]:
            for defaults in case["defaults"]:
                with self.subTest(text=text, default=defaults[self.OPTION]):
                    self.assertEqual(
                        normalize(text, defaults=defaults)[self.OPTION],
                        defaults[self.OPTION],
                    )

    def test_canonical_false_beats_a_natural_affirmative_phrasing(self) -> None:
        case = self._case("canonical_false")
        result = normalize(case["text"], defaults=case["defaults"])
        self.assertFalse(result[self.OPTION])

    def test_conflicting_natural_values_fall_back_to_default(self) -> None:
        for text, defaults, expected in self._case("conflict"):
            with self.subTest(text=text, expected=expected):
                self.assertEqual(
                    normalize(text, defaults=defaults)[self.OPTION], expected
                )

    def test_direct_and_mediated_forms_have_parity(self) -> None:
        case = self._case("parity")
        direct = normalize(case["direct"], defaults=case["defaults"])
        mediated = normalize(case["mediated"], defaults=case["defaults"])
        self.assertEqual(direct, mediated)

    def test_the_option_does_not_leak_between_invocations(self) -> None:
        case = self._case("no_leak")
        first = normalize(case["first"], defaults=case["defaults"])
        second = normalize(case["second"], defaults=case["defaults"])
        self.assertTrue(first[self.OPTION])
        self.assertFalse(second[self.OPTION])


_AXIS_TESTS = {
    "enables": "test_natural_affirmative_phrasings_enable_it",
    "forces_off": "test_explicit_negatives_force_it_off",
    "unset": "test_ambiguous_or_vague_language_does_not_set_it",
    "canonical_false": "test_canonical_false_beats_a_natural_affirmative_phrasing",
    "conflict": "test_conflicting_natural_values_fall_back_to_default",
    "parity": "test_direct_and_mediated_forms_have_parity",
    "no_leak": "test_the_option_does_not_leak_between_invocations",
}


def _build_contract_class(option: str, cases: dict[str, Any]) -> type:
    """One TestCase per option holding only the axes that option declares."""

    namespace: dict[str, Any] = {"OPTION": option, "CASES": cases}
    # Axes the option does not declare are masked so they are never collected.
    for axis, test_name in _AXIS_TESTS.items():
        if axis not in cases:
            namespace[test_name] = None
    name = "InvocationOptionContract_" + option
    return type(name, (_ContractAxes, unittest.TestCase), namespace)


for _option, _cases in CONTRACTS.items():
    _cls = _build_contract_class(_option, _cases)
    globals()[_cls.__name__] = _cls
del _option, _cases, _cls


class OptionSpecificTests(unittest.TestCase):
    """Behavior that is not part of the shared per-option contract."""

    def test_ambiguous_language_leaves_every_option_untouched(self) -> None:
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

    def test_derived_inline_default_follows_human_review_output(self) -> None:
        # unset: inherits whatever human_review_output resolved to
        self.assertFalse(
            normalize("review this PR", defaults=GITHUB_DEFAULTS)["human_inline_findings"]
        )
        on = normalize("review it like a senior engineer", defaults=GITHUB_DEFAULTS)
        self.assertTrue(on["human_review_output"])
        self.assertTrue(on["human_inline_findings"])
        canonical = normalize("human_review_output=true", defaults=GITHUB_DEFAULTS)
        self.assertTrue(canonical["human_inline_findings"])

    def test_local_defaults_also_carry_the_derived_inline_value(self) -> None:
        # normalized for parity; the Skill simply has no inline surface to act on
        self.assertFalse(
            normalize("review this", defaults=LOCAL_DEFAULTS)["human_inline_findings"]
        )
        self.assertTrue(
            normalize("review like a senior engineer", defaults=LOCAL_DEFAULTS)[
                "human_inline_findings"
            ]
        )

    def test_severity_description_default_is_compact_for_both_skills(self) -> None:
        for defaults in (LOCAL_DEFAULTS, GITHUB_DEFAULTS):
            self.assertFalse(defaults["include_severity_description"])
            self.assertFalse(
                normalize("review this PR", defaults=defaults)[
                    "include_severity_description"
                ]
            )

    def test_severity_description_does_not_change_any_other_option(self) -> None:
        off = normalize("review this PR", defaults=GITHUB_DEFAULTS)
        on = normalize(
            "review this PR and show severity descriptions",
            defaults=GITHUB_DEFAULTS,
        )
        self.assertTrue(on.pop("include_severity_description"))
        off.pop("include_severity_description", None)
        self.assertEqual(on, off)

    def test_severity_description_local_defaults_normalize_for_parity_only(self) -> None:
        # local-code-review has no severity legend at all; the option
        # still normalizes deterministically for cross-Skill parity even
        # though the Skill has nothing to act on.
        self.assertTrue(
            normalize("show severity descriptions", defaults=LOCAL_DEFAULTS)[
                "include_severity_description"
            ]
        )
        self.assertFalse(
            normalize("review this", defaults=LOCAL_DEFAULTS)[
                "include_severity_description"
            ]
        )

    def test_structured_result_defaults_false(self) -> None:
        self.assertFalse(
            normalize("review this", defaults=LOCAL_DEFAULTS)["structured_review_result"]
        )

    def test_structured_result_name_is_not_read_as_human_output_negative_phrase(
        self,
    ) -> None:
        result = normalize(
            "review like a senior engineer and include a structured review result",
            defaults=LOCAL_DEFAULTS,
        )
        self.assertTrue(result["human_review_output"])
        self.assertTrue(result["structured_review_result"])
        self.assertFalse(
            normalize("structured review", defaults={**LOCAL_DEFAULTS, "human_review_output": True})[
                "human_review_output"
            ]
        )

    def test_structured_result_does_not_change_any_other_option(self) -> None:
        off = normalize("review this", defaults=LOCAL_DEFAULTS)
        on = normalize("review this, structured_review_result=true", defaults=LOCAL_DEFAULTS)
        self.assertTrue(on.pop("structured_review_result"))
        off.pop("structured_review_result")
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


if __name__ == "__main__":
    unittest.main()
