"""Change-aware verification: planning, viewports, evidence kinds, per-check status
and the structural-versus-visual regressions (Issue #771, cases 16-24, 29-44)."""

from __future__ import annotations

import unittest

from tests.reference.review import rendered_inspection as ri
from tests.reference.review import rendered_verification as rv
from tests.reference.review.rendered_verification import (
    ChangeClass,
    DiffFacts,
    DomRead,
    Evidence,
    InteractionResult,
    Kind,
    Status,
    VisualObservation,
)


def facts(*tokens: str, **kw) -> DiffFacts:
    return DiffFacts(frozenset(tokens), **kw)


def classes_of(plan) -> set[ChangeClass]:
    return {i.change_class for i in plan}


def item(plan, prop: str, kind: Kind) -> rv.PlanItem:
    return next(i for i in plan if i.property == prop and i.kind is kind)


SEEN = VisualObservation(True, True, target="/list", state="focused edge child", observation="outline cut off at container edge")
SEEN_CLEAN = VisualObservation(True, False, target="/list", state="focused", observation="outline fully visible")


class PlanningTests(unittest.TestCase):
    def test_plan_is_derived_from_the_change_class(self) -> None:
        for token, cls in (("grid", ChangeClass.GRID), ("overflow", ChangeClass.OVERFLOW), ("typography", ChangeClass.TYPOGRAPHY), ("interaction", ChangeClass.INTERACTION)):
            with self.subTest(token=token):
                self.assertEqual(classes_of(rv.build_plan(facts(token))), {cls})

    def test_irrelevant_or_trivial_changes_get_no_generic_checklist(self) -> None:
        for tokens in (set(), {"refactor"}, {"decorative-shadow"}, {"copy"}):
            with self.subTest(tokens=tokens):
                self.assertEqual(rv.build_plan(facts(*tokens)), ())
                self.assertFalse(rv.offer_would_fire(facts(*tokens)))

    def test_classes_are_closed_at_seven(self) -> None:
        self.assertEqual(len(rv.CLASSES), 7)
        for token in ("scroll-cue", "horizontal-overflow-indicator", "focus-outline"):
            self.assertEqual(rv.TOKEN_CLASS[token], ChangeClass.OVERFLOW)

    def test_scroll_cue_indicator_and_focus_outline_plan_under_overflow_only(self) -> None:
        for token in ("scroll-cue", "horizontal-overflow-indicator", "focus-outline"):
            with self.subTest(token=token):
                plan = rv.build_plan(facts(token))
                self.assertTrue(plan)
                self.assertEqual(classes_of(plan), {ChangeClass.OVERFLOW})

    def test_decorative_only_change_plans_nothing(self) -> None:
        self.assertEqual(rv.build_plan(facts("decorative-shadow")), ())

    def test_properties_inside_a_class_follow_the_diff(self) -> None:
        plan = rv.build_plan(facts("grid"))
        self.assertNotIn("breakpoint-behavior", {i.property for i in plan})
        self.assertNotIn(Kind.INTERACTION, {i.kind for i in plan})

    def test_no_screenshot_for_dom_and_interaction_only_plans(self) -> None:
        plan = rv.build_plan(facts("interaction"))
        self.assertNotIn(Kind.VISUAL, {i.kind for i in plan if i.property == "keyboard-navigation"})
        dom_interaction = [i for i in plan if i.kind is not Kind.VISUAL]
        self.assertEqual(rv.captures_needed(dom_interaction, (rv.DESKTOP,)), 0)


class ViewportAndBudgetTests(unittest.TestCase):
    def test_non_responsive_change_uses_one_viewport(self) -> None:
        self.assertEqual(rv.select_viewports(facts("overflow")).viewports, (rv.DESKTOP,))

    def test_responsive_change_selects_widths_on_both_sides_of_breakpoint(self) -> None:
        below, at = rv.select_viewports(facts("responsive", breakpoints=(768,))).viewports
        self.assertLess(below, 768)
        self.assertGreaterEqual(at, 768)

    def test_viewports_never_exceed_the_budget_and_unmet_risk_is_not_checked(self) -> None:
        selection = rv.select_viewports(facts("responsive", breakpoints=(768, 1024, 1280)))
        self.assertLessEqual(len(selection.viewports), ri.MAX_VIEWPORTS)
        self.assertTrue(selection.not_checked)
        self.assertTrue(all(reason == "budget" for _, reason in selection.not_checked))

    def test_captures_never_exceed_the_cap_and_none_is_required_per_pr(self) -> None:
        plan = rv.build_plan(facts("grid", "typography", "positioning", "visibility", "responsive"))
        self.assertLessEqual(rv.captures_needed(plan, (320, 768)), 6)
        self.assertEqual(rv.captures_needed([], (rv.DESKTOP,)), 0)

class EvidenceKindTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plan = rv.build_plan(facts("overflow", focusable_children=True))

    def test_dom_alone_never_completes_a_visual_check(self) -> None:
        visual = item(self.plan, "focus-outline-clipping", Kind.VISUAL)
        result = rv.evaluate(visual, 1440, Evidence(dom=DomRead(True, "outline: 2px solid")))
        self.assertEqual((result.status, result.reason), (Status.NOT_CHECKED, "visual evidence insufficient"))
        self.assertTrue(result.dom_support)
        self.assertFalse(rv.may_say_visually_verified("focus-outline-clipping", [result]))

    def test_regression_focus_outline_clipped_by_overflow(self) -> None:
        plan = rv.build_plan(facts("overflow", focusable_children=True))
        self.assertEqual(classes_of(plan), {ChangeClass.OVERFLOW})
        self.assertEqual({i.kind for i in plan if i.property == "focus-outline-clipping"}, {Kind.DOM, Kind.VISUAL, Kind.INTERACTION})
        dom = rv.evaluate(item(plan, "focus-outline-clipping", Kind.DOM), 1440, Evidence(dom=DomRead(False, "computed outline present")))
        visual = rv.evaluate(item(plan, "focus-outline-clipping", Kind.VISUAL), 1440, Evidence(dom=DomRead(False), visual=SEEN))
        self.assertEqual(visual.status, Status.CONFIRMED)
        self.assertEqual(dom.kind, Kind.DOM)
        self.assertTrue(rv.may_say_visually_verified("focus-outline-clipping", [dom, visual]))
        # visual observation missing: the DOM result stays, the visual check is not-checked
        missing = rv.evaluate(item(plan, "focus-outline-clipping", Kind.VISUAL), 1440, Evidence(dom=DomRead(False)))
        self.assertEqual(missing.status, Status.NOT_CHECKED)
        self.assertEqual(rv.record_kinds([dom, missing]), {"focus-outline-clipping": {"dom"}})
        self.assertFalse(rv.may_say_visually_verified("focus-outline-clipping", [dom, missing]))

    def test_input_unavailable_is_not_checked_and_computed_style_is_not_an_interaction_result(self) -> None:
        interaction = item(self.plan, "focus-outline-clipping", Kind.INTERACTION)
        result = rv.evaluate(interaction, 1440, Evidence(input_available=False, computed_focus_style_present=True, dom=DomRead(False)))
        self.assertEqual(result.slot(), "focus-outline-clipping:interaction@1440=not-checked(input unavailable)")
        ran = rv.evaluate(interaction, 1440, Evidence(interaction=InteractionResult(True)))
        self.assertEqual(ran.status, Status.CONFIRMED)

    def test_regression_grid_structure_passes_but_layout_unverified(self) -> None:
        plan = rv.build_plan(facts("grid"))
        dom = rv.evaluate(item(plan, "track-sizes", Kind.DOM), 1440, Evidence(dom=DomRead(False, "four tracks")))
        self.assertEqual(rv.record_kinds([dom]), {"track-sizes": {"dom"}})
        visual_item = item(plan, "alignment-spacing-proportions", Kind.VISUAL)
        unverified = rv.evaluate(visual_item, 1440, Evidence(dom=DomRead(False)))
        self.assertEqual(unverified.status, Status.NOT_CHECKED)
        self.assertFalse(rv.may_say_visually_verified("alignment-spacing-proportions", [dom, unverified]))
        for observation, expected in ((SEEN, Status.CONFIRMED), (SEEN_CLEAN, Status.REFUTED)):
            result = rv.evaluate(visual_item, 1440, Evidence(dom=DomRead(False), visual=observation))
            self.assertEqual(result.status, expected)

    def test_regression_scroll_cue_present_in_css_but_not_discernible(self) -> None:
        plan = rv.build_plan(facts("scroll-cue"))
        visual_item = item(plan, "scroll-cue-visibility", Kind.VISUAL)
        dom_only = rv.evaluate(visual_item, 375, Evidence(dom=DomRead(False, "gradient opacity 0.04")))
        self.assertEqual(dom_only.reason, "visual evidence insufficient")
        self.assertEqual(dom_only.status, Status.NOT_CHECKED)
        completed = rv.evaluate(visual_item, 375, Evidence(visual=SEEN))
        self.assertEqual(completed.status, Status.CONFIRMED)

    def test_passing_playwright_run_or_ci_is_never_visual_or_interaction_evidence(self) -> None:
        plan = rv.build_plan(facts("overflow", focusable_children=True))
        context = Evidence(playwright_test_passed=True, ci_status_green=True)
        results = [rv.evaluate(item(plan, "focus-outline-clipping", kind), 1440, context) for kind in (Kind.VISUAL, Kind.INTERACTION)]
        self.assertTrue(all(r.status is Status.NOT_CHECKED for r in results))
        self.assertFalse(rv.may_say_visually_verified("focus-outline-clipping", results))

    def test_record_keeps_kinds_distinct_with_viewport_and_closed_reason(self) -> None:
        plan = rv.build_plan(facts("overflow", focusable_children=True))
        results = [
            rv.evaluate(item(plan, "focus-outline-clipping", Kind.DOM), 1440, Evidence(dom=DomRead(False))),
            rv.evaluate(item(plan, "focus-outline-clipping", Kind.VISUAL), 1440, Evidence(visual=SEEN)),
            rv.evaluate(item(plan, "focus-outline-clipping", Kind.INTERACTION), 1440, Evidence(input_available=False)),
        ]
        slot = rv.render_checks_slot(results)
        self.assertIn("focus-outline-clipping:dom@1440=refuted", slot)
        self.assertIn("focus-outline-clipping:visual@1440=confirmed", slot)
        self.assertIn("focus-outline-clipping:interaction@1440=not-checked(input unavailable)", slot)

    def test_capture_failed_unreadable_or_unsettled_is_visual_evidence_insufficient(self) -> None:
        visual_item = item(rv.build_plan(facts("grid")), "alignment-spacing-proportions", Kind.VISUAL)
        cases = {
            "capture failed": Evidence(visual=SEEN, capture_possible=False),
            "unreadable": Evidence(visual=VisualObservation(True, True, capture_readable=False)),
            "did not settle": Evidence(visual=VisualObservation(False, False)),
        }
        for name, evidence in cases.items():
            with self.subTest(name=name):
                result = rv.evaluate(visual_item, 1440, evidence)
                self.assertEqual(result.reason, rv.VISUAL_ONLY_REASON)
                self.assertEqual(rv.human_status(result), "not completed")
                self.assertIn("not-checked(visual evidence insufficient)", result.slot())


class ReasonVocabularyTests(unittest.TestCase):
    def test_reason_set_is_closed_at_six_tokens(self) -> None:
        self.assertEqual(len(rv.REASONS), 6)
        self.assertIn("visual evidence insufficient", rv.REASONS)

    def test_other_tokens_are_rejected(self) -> None:
        bad = rv.CheckResult("p", Kind.VISUAL, 1440, Status.NOT_CHECKED, "no screenshot")
        with self.assertRaises(ValueError):
            rv.validate_result(bad)

    def test_visual_token_is_rejected_on_dom_and_interaction_checks(self) -> None:
        for kind in (Kind.DOM, Kind.INTERACTION):
            with self.subTest(kind=kind):
                with self.assertRaises(ValueError):
                    rv.validate_result(rv.CheckResult("p", kind, 1440, Status.NOT_CHECKED, rv.VISUAL_ONLY_REASON))

    def test_every_other_reason_is_valid_where_applicable(self) -> None:
        for reason in rv.REASONS[:-1]:
            rv.validate_result(rv.CheckResult("p", Kind.INTERACTION, 1440, Status.NOT_CHECKED, reason))

    def test_human_text_never_replaces_the_token_in_the_slot(self) -> None:
        result = rv.CheckResult("p", Kind.VISUAL, 375, Status.NOT_CHECKED, rv.VISUAL_ONLY_REASON)
        self.assertEqual(rv.human_status(result), "not completed")
        self.assertIn("not-checked(visual evidence insufficient)", rv.render_checks_slot([result]))
        self.assertNotIn("not completed", rv.render_checks_slot([result]))


class InputGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.interaction = item(rv.build_plan(facts("interaction")), "keyboard-navigation", Kind.INTERACTION)

    def test_write_dependent_item_is_mutation_blocked(self) -> None:
        result = rv.evaluate(self.interaction, 1440, Evidence(needs_write=True))
        self.assertEqual(result.reason, "mutation blocked")

    def test_activation_on_non_disposable_target_is_not_checked(self) -> None:
        result = rv.evaluate(self.interaction, 1440, Evidence(needs_activation=True, target_disposable=False))
        self.assertEqual(result.reason, "target not disposable")

    def test_budget_and_timeout_reasons(self) -> None:
        self.assertEqual(rv.evaluate(self.interaction, 1440, Evidence(over_budget=True)).reason, "budget")
        self.assertEqual(rv.evaluate(self.interaction, 1440, Evidence(timed_out=True)).reason, "timeout")


if __name__ == "__main__":
    unittest.main()
