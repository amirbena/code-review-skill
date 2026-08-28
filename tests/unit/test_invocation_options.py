#!/usr/bin/env python3
"""Semantic tests for deterministic review invocation options."""

from __future__ import annotations

import unittest

from tests.reference.invocation_options import normalize


LOCAL_DEFAULTS = {
    "include_fix_prompt": False,
    "include_fix_guidance": True,
    "include_finding_details": True,
}
GITHUB_DEFAULTS = {
    "include_fix_prompt": False,
    "include_fix_guidance": True,
    "include_finding_details": False,
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


if __name__ == "__main__":
    unittest.main()
