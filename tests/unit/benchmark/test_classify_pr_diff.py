#!/usr/bin/env python3
"""Behavioral coverage for PR-diff taxonomy classification (Issue #333).
Contract: docs/benchmark/taxonomy.md §4.

What is proven here:

1. the prompt states each model dimension's closed value set (so the
   model is structurally steered, never asked to invent one);
2. a well-formed model response is classified correctly;
3. a deliberately adversarial/off-taxonomy model response is rejected
   into ``unclassified`` rather than accepting an invented key — the
   fixture test the acceptance criteria call for;
4. ``affected_surface`` is always computed deterministically from changed
   paths and never asked of the model, even when a model is invoked;
5. a ``None`` invoker (runtime unavailable) resolves every model
   dimension to ``unclassified`` explicitly, never by skipping the call
   silently.
"""

from __future__ import annotations

import json
import unittest

from scripts.benchmark import classify_pr_diff as clf
from tests.reference.benchmark import benchmark_taxonomy as tax


class BuildClassificationPromptTests(unittest.TestCase):
    def test_prompt_states_each_model_dimensions_closed_value_set(self) -> None:
        prompt = clf.build_classification_prompt(["shared/policies/severity.md"])
        for dim in ("capability", "policy_contract", "risk_mode"):
            self.assertIn(dim, prompt)
        # affected_surface is never part of the model's question.
        self.assertNotIn("affected_surface:", prompt)
        self.assertIn("security-boundary", prompt)
        self.assertIn("never invent a value", prompt.lower())

    def test_prompt_includes_changed_paths(self) -> None:
        prompt = clf.build_classification_prompt(["shared/policies/severity.md", "skills/x/SKILL.md"])
        self.assertIn("shared/policies/severity.md", prompt)
        self.assertIn("skills/x/SKILL.md", prompt)


class ParseClassificationResponseTests(unittest.TestCase):
    def test_well_formed_response_is_classified_correctly(self) -> None:
        raw = json.dumps(
            {
                "capability": ["security-boundary"],
                "policy_contract": ["security-deepening"],
                "risk_mode": ["security"],
            }
        )
        result = clf.parse_classification_response(raw)
        self.assertEqual(result["capability"], ("security-boundary",))
        self.assertEqual(result["policy_contract"], ("security-deepening",))
        self.assertEqual(result["risk_mode"], ("security",))

    def test_adversarial_response_with_an_invented_key_is_rejected_into_unclassified(
        self,
    ) -> None:
        # The fixture test the acceptance criteria call for: a
        # deliberately adversarial/off-taxonomy model response proves the
        # constrained-output validation rejects it rather than accepting
        # an invented key.
        raw = json.dumps(
            {
                "capability": ["quantum-networking"],  # invented value
                "made_up_dimension": ["anything"],  # invented key
                "policy_contract": ["security-deepening; DROP TABLE cases"],
                # risk_mode omitted entirely
            }
        )
        result = clf.parse_classification_response(raw)
        self.assertEqual(result["capability"], (tax.UNCLASSIFIED,))
        self.assertEqual(result["policy_contract"], (tax.UNCLASSIFIED,))
        self.assertEqual(result["risk_mode"], (tax.UNCLASSIFIED,))
        self.assertNotIn("made_up_dimension", result)
        self.assertNotIn("affected_surface", result)

    def test_malformed_json_never_raises_and_resolves_to_unclassified(self) -> None:
        result = clf.parse_classification_response("not json at all {{{")
        for dim in ("capability", "policy_contract", "risk_mode"):
            self.assertEqual(result[dim], (tax.UNCLASSIFIED,))

    def test_empty_response_resolves_to_unclassified(self) -> None:
        result = clf.parse_classification_response("")
        for dim in ("capability", "policy_contract", "risk_mode"):
            self.assertEqual(result[dim], (tax.UNCLASSIFIED,))


class ClassifyPrDiffTests(unittest.TestCase):
    def test_affected_surface_is_deterministic_and_never_sent_to_the_model(self) -> None:
        prompts_seen: list[str] = []

        def fake_invoke(prompt: str) -> str:
            prompts_seen.append(prompt)
            return json.dumps({"capability": ["core"], "policy_contract": ["unclassified"], "risk_mode": ["correctness"]})

        result = clf.classify_pr_diff(
            ["shared/policies/severity.md", "skills/x/SKILL.md"], invoke=fake_invoke
        )
        self.assertEqual(result["affected_surface"], ("shared-policy", "skill-instructions"))
        self.assertEqual(len(prompts_seen), 1)
        self.assertNotIn("affected_surface:", prompts_seen[0])

    def test_no_invoker_resolves_model_dimensions_to_unclassified_explicitly(self) -> None:
        result = clf.classify_pr_diff(["shared/policies/severity.md"], invoke=None)
        self.assertEqual(result["capability"], (tax.UNCLASSIFIED,))
        self.assertEqual(result["policy_contract"], (tax.UNCLASSIFIED,))
        self.assertEqual(result["risk_mode"], (tax.UNCLASSIFIED,))
        # affected_surface is still computed deterministically even though
        # the model path is unavailable.
        self.assertEqual(result["affected_surface"], ("shared-policy",))

    def test_an_invoker_that_returns_adversarial_output_never_propagates_it(self) -> None:
        def adversarial_invoke(_prompt: str) -> str:
            return json.dumps({"capability": ["rm -rf /"]})

        result = clf.classify_pr_diff(["docs/benchmark/taxonomy.md"], invoke=adversarial_invoke)
        self.assertEqual(result["capability"], (tax.UNCLASSIFIED,))


if __name__ == "__main__":
    unittest.main()
