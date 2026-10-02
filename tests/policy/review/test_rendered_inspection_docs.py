#!/usr/bin/env python3
"""Contract: shared/policies/rendered-inspection.md as the single canonical
home of rendered-UI inspection (Issue #616, Epic #614).

Prose checks over the shared policy, its consumers, and its manifest, plus
behavior checks over the test-only reference model.
"""

from __future__ import annotations

import re
import unittest

from tests.reference.review import rendered_inspection as ri
from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import GITHUB_ACTIVE_RUNBOOK
from tests.support.policy_docs import GITHUB_PASSIVE_RUNBOOK
from tests.support.policy_docs import LOCAL_RUNBOOK
from tests.support.policy_docs import load_normalized_text as _text


def _plain(phrase: str) -> str:
    return phrase.replace("**", "").replace("`", "")


POLICY = REPO_ROOT / "shared/policies/rendered-inspection.md"
REVIEW_SUMMARY = REPO_ROOT / "shared/templates/review-summary.md"
REVIEW_SCOPE = REPO_ROOT / "shared/policies/review-scope.md"
STOPPING = REPO_ROOT / "shared/policies/review-stopping-criteria.md"
RUNTIME_VALIDATION = REPO_ROOT / "shared/policies/runtime-validation.md"
LOCAL_TEMPLATE = REPO_ROOT / "skills/local-code-review/templates/local-review-report.md"
GITHUB_TEMPLATE = REPO_ROOT / "skills/github-pr-review/templates/external-review-summary.md"
CAPABILITY = REPO_ROOT / "capabilities/rendered-inspection/capability.yaml"

RUNBOOKS = (LOCAL_RUNBOOK, GITHUB_ACTIVE_RUNBOOK, GITHUB_PASSIVE_RUNBOOK)

# Semantics owned by the shared policy and stated nowhere else.
OWNED_PHRASES = (
    "Inert and silent otherwise",
    "No-fabrication rule",
    "Objective/subjective boundary test",
    "one cap shared by *every* observation source",
)


class InertOnNonUiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY)

    def test_trigger_requires_all_three_conditions(self) -> None:
        for phrase in (
            "**all** of these hold",
            "materially** alters rendered output",
            "a render could add evidence",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_inert_means_no_output_question_or_evidence_read(self) -> None:
        for phrase in (
            "no inspection plan, no question, no `Validation` entry",
            "no `not-applicable` line",
            "no evidence read beyond",
            "byte-identical",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_model_is_inert_when_any_condition_fails(self) -> None:
        for facts in (
            ri.ChangeFacts(False, True, True),
            ri.ChangeFacts(True, False, True),
            ri.ChangeFacts(True, True, False),
        ):
            with self.subTest(facts=facts):
                self.assertFalse(ri.trigger_fires(facts))
                self.assertIsNone(ri.output_for(facts))
        self.assertEqual(ri.output_for(ri.ChangeFacts(True, True, True)), "active")

    def test_inert_renders_no_section(self) -> None:
        self.assertEqual(ri.render_observations_section(()), "")


class NoFabricationTests(unittest.TestCase):
    def test_policy_forbids_claiming_an_unrendered_page(self) -> None:
        text = _text(POLICY)
        self.assertIn(_plain("A render is never claimed"), text)
        self.assertIn(_plain("unless a page was actually rendered"), text)

    def test_only_an_inspected_outcome_may_emit_visual_output(self) -> None:
        for outcome in ri.Outcome:
            with self.subTest(outcome=outcome):
                self.assertEqual(
                    ri.may_emit_visual_output(outcome), outcome is ri.Outcome.INSPECTED
                )

    def test_no_pages_rendered_is_never_inspected(self) -> None:
        attempt = ri.Attempt(True, True, True, True, pages_rendered=0)
        self.assertIsNot(ri.map_outcome(attempt), ri.Outcome.INSPECTED)

    def test_stale_target_is_inconclusive_and_missing_capability_unavailable(self) -> None:
        self.assertIs(
            ri.map_outcome(ri.Attempt(True, True, False, True, 2)),
            ri.Outcome.ATTEMPTED_INCONCLUSIVE,
        )
        self.assertIs(
            ri.map_outcome(ri.Attempt(True, False, True, True, 0)), ri.Outcome.UNAVAILABLE
        )

    def test_unrendered_concern_is_not_reported(self) -> None:
        concern = ri.Concern("clipped button", user_blocked_misled_or_excluded=True)
        for outcome in (ri.Outcome.SKIPPED, ri.Outcome.UNAVAILABLE):
            self.assertIs(ri.route_concern(concern, outcome), ri.Route.NOT_REPORTED)


class SeverityAndObservationSeparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY)

    def test_objective_defects_are_normal_findings_with_causal_link(self) -> None:
        for phrase in (
            "is a **normal finding**",
            "real impact",
            "causal link",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_polish_is_never_a_finding(self) -> None:
        for phrase in (
            "never a P0/P1/P2 finding",
            "separate, severity-less",
            "never changes severity, finding identity, coverage, or the Decision",
            "never published as an inline comment",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_subjective_rendered_concern_becomes_an_observation(self) -> None:
        concern = ri.Concern("spacing feels tight", rendered_target_id="/home", state="default")
        self.assertIs(ri.route_concern(concern, ri.Outcome.INSPECTED), ri.Route.OBSERVATION)

    def test_polish_without_a_rendered_page_and_state_is_dropped(self) -> None:
        concern = ri.Concern("spacing feels tight")
        self.assertIs(ri.route_concern(concern, ri.Outcome.INSPECTED), ri.Route.NOT_REPORTED)

    def test_concrete_cost_promotes_to_a_finding(self) -> None:
        for kwargs in (
            {"user_blocked_misled_or_excluded": True},
            {"requirement_unmet": True},
            {"measurable_engineering_cost": True},
        ):
            with self.subTest(kwargs=kwargs):
                concern = ri.Concern(
                    "control hidden", rendered_target_id="/x", state="open", **kwargs
                )
                self.assertIs(ri.route_concern(concern, ri.Outcome.INSPECTED), ri.Route.FINDING)

    def test_preexisting_defect_not_caused_by_change_is_not_attributed(self) -> None:
        concern = ri.Concern("overlap", requirement_unmet=True, caused_by_change=False)
        self.assertIs(ri.route_concern(concern, ri.Outcome.INSPECTED), ri.Route.NOT_REPORTED)

    def test_review_summary_places_observations_before_validation(self) -> None:
        raw = REVIEW_SUMMARY.read_text(encoding="utf-8")
        observations = raw.index("### Rendered observations")
        validation = raw.index("### Validation", observations)
        self.assertLess(observations, validation)
        text = _text(REVIEW_SUMMARY)
        self.assertIn(_plain("omitted completely"), text)
        self.assertIn(_plain("never fed to the Decision tally"), text)


class ObservationCapTests(unittest.TestCase):
    def test_policy_states_one_shared_cap_of_three_and_grounding(self) -> None:
        text = _text(POLICY)
        self.assertIn(_plain("at most **3**"), text)
        self.assertIn(_plain("every* observation source"), text)
        self.assertIn(_plain("actually **rendered**"), text)
        self.assertIn(_plain("never consume the cap"), text)

    def test_cap_keeps_three_by_priority_then_views_then_id(self) -> None:
        observations = [
            ri.Observation("/c", "s", "c", views=1),
            ri.Observation("/a", "s", "a", views=1),
            ri.Observation("/b", "s", "b", views=5),
            ri.Observation("/a", "t", "a2", views=3),
        ]
        kept = ri.cap_observations(observations, plan_order=["/a", "/b", "/c"])
        self.assertEqual(len(kept), ri.MAX_OBSERVATIONS)
        self.assertEqual([o.text for o in kept], ["a2", "a", "b"])

    def test_budget_bounds(self) -> None:
        targets = [ri.Target(f"/t{i}", ("desktop", "mobile", "tablet")) for i in range(5)]
        plan = ri.bound_plan(targets)
        self.assertEqual(len(plan.targets), ri.MAX_TARGETS)
        self.assertTrue(all(len(t.viewports) <= ri.MAX_VIEWPORTS for t in plan.targets))
        self.assertLessEqual(plan.captures, ri.MAX_CAPTURES)

    def test_evidence_record_design_reference_line_is_optional(self) -> None:
        common = dict(
            target_source="declared",
            sha="abc123",
            viewports=["desktop"],
            states=["default"],
            observed="no clipping",
        )
        analytical = ri.render_record(ri.Mode.ANALYTICAL, ri.Outcome.INSPECTED, **common)
        self.assertNotIn("Design reference", analytical)
        referenced = ri.render_record(
            ri.Mode.DESIGN_REFERENCE,
            ri.Outcome.INSPECTED,
            design_reference="frame 12",
            **common,
        )
        self.assertIn("Design reference: frame 12", referenced)
        text = _text(POLICY)
        self.assertIn(_plain("Optional design-reference line"), text)
        self.assertIn(_plain("**absent**"), text)

    def test_policy_defines_both_modes_and_leaves_design_decisions_out(self) -> None:
        text = _text(POLICY)
        self.assertIn(_plain("`analytical`"), text)
        self.assertIn(_plain("`design-reference`"), text)
        self.assertIn(_plain("never triggers an inspection and never widens"), text)


class NoCoverageOrDecisionEffectTests(unittest.TestCase):
    def test_policy_and_stopping_criteria_state_no_effect(self) -> None:
        self.assertIn(
            _plain("never `REVIEW INCOMPLETE` material"), _text(POLICY)
        )
        stopping = _text(STOPPING)
        self.assertIn(_plain("rendered-inspection.md"), stopping)
        self.assertIn(_plain("never a required pass at any depth"), stopping)

    def test_every_outcome_leaves_coverage_and_decision_unchanged(self) -> None:
        for outcome in ri.Outcome:
            for base in ("complete", "incomplete"):
                with self.subTest(outcome=outcome, base=base):
                    effect = ri.coverage_effect(outcome, base)
                    self.assertEqual(effect.coverage, base)
                    self.assertFalse(effect.decision_changed)

    def test_non_inspected_outcomes_are_never_a_pass(self) -> None:
        text = _text(POLICY)
        self.assertIn(_plain("never shown as a pass"), text)


class UserFacingDepthOwnerTests(unittest.TestCase):
    def test_review_scope_names_the_depth_owner_additively(self) -> None:
        text = _text(REVIEW_SCOPE)
        self.assertIn("rendered-inspection.md", text)
        self.assertIn(_plain("never gates or replaces this base obligation"), text)
        self.assertNotIn("no dedicated owner contract exists yet in this repository; this base obligation", text)

    def test_runtime_validation_names_the_second_step_in_the_same_slot(self) -> None:
        text = _text(RUNTIME_VALIDATION)
        self.assertIn(_plain("second optional evidence step in this same slot"), text)


class BothSkillsConsumeIdenticallyTests(unittest.TestCase):
    def test_every_runbook_names_the_shared_policy_and_inert_rule(self) -> None:
        for path in RUNBOOKS:
            with self.subTest(path=path.name):
                text = _text(path)
                self.assertIn("rendered-inspection.md", text)
                self.assertIn("rendered inspection", text.lower())
                self.assertIn(_plain("never changes coverage or the Decision"), text)

    def test_runbooks_sit_beside_runtime_validation(self) -> None:
        for path in RUNBOOKS:
            with self.subTest(path=path.name):
                raw = path.read_text(encoding="utf-8")
                self.assertLess(raw.index("runtime-validation.md"), raw.index("rendered-inspection.md"))

    def test_owned_phrases_appear_only_in_the_shared_policy(self) -> None:
        for path in (REVIEW_SUMMARY, LOCAL_TEMPLATE, GITHUB_TEMPLATE, REVIEW_SCOPE, *RUNBOOKS):
            text = _text(path)
            for phrase in OWNED_PHRASES:
                with self.subTest(path=path.name, phrase=phrase):
                    self.assertNotIn(_plain(phrase), text)

    def test_both_delivery_templates_link_the_shared_policy_and_stay_body_only(self) -> None:
        for path in (LOCAL_TEMPLATE, GITHUB_TEMPLATE):
            with self.subTest(path=path.name):
                text = _text(path)
                self.assertIn("rendered-inspection.md", text)
                self.assertIn(_plain("Rendered observations"), text)
        self.assertIn(
            _plain("never an inline comment or a review event"), _text(GITHUB_TEMPLATE)
        )


class UntrustedContentAndNeutralityTests(unittest.TestCase):
    def test_page_and_console_content_are_untrusted_data(self) -> None:
        text = _text(POLICY)
        for phrase in ("**untrusted data**", "console", "redacts the value", "no secret or real credential"):
            self.assertIn(_plain(phrase), text)

    def test_canonical_files_are_runtime_neutral(self) -> None:
        for path in (POLICY, CAPABILITY):
            text = path.read_text(encoding="utf-8").lower()
            for token in ("playwright", "puppeteer", "selenium", "claude", "anthropic"):
                with self.subTest(path=path.name, token=token):
                    self.assertNotIn(token, text)


class ManifestAndPackagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = CAPABILITY.read_text(encoding="utf-8")

    def test_manifest_is_on_activation_for_both_adapters(self) -> None:
        self.assertIn("loads: on-activation", self.manifest)
        self.assertIn("adapters: [local, github]", self.manifest)
        self.assertIn("shared/policies/rendered-inspection.md", self.manifest)
        self.assertIn("benchmark: tests/reference/review/rendered_inspection.py", self.manifest)
        self.assertTrue((REPO_ROOT / "tests/reference/review/rendered_inspection.py").is_file())

    def test_manifest_forbids_coverage_effect_and_installation(self) -> None:
        text = _plain(self.manifest)
        self.assertIn("REVIEW INCOMPLETE", text)
        self.assertIn("installing a browser", text)

    def test_policy_links_only_into_shared(self) -> None:
        raw = POLICY.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)#]+)", raw):
            with self.subTest(target=target):
                resolved = (POLICY.parent / target).resolve()
                self.assertTrue(resolved.is_file(), target)
                self.assertTrue(resolved.is_relative_to(REPO_ROOT / "shared"), target)
        self.assertNotIn("docs/", raw)
        self.assertNotIn("AGENTS.md", raw)
        self.assertIn("Rendered-UI Inspection Contract", raw)

    def test_shared_summary_does_not_link_into_skills_or_docs(self) -> None:
        raw = REVIEW_SUMMARY.read_text(encoding="utf-8")
        self.assertNotRegex(raw, r"\]\([^)]*(skills/|docs/)")


if __name__ == "__main__":
    unittest.main()
