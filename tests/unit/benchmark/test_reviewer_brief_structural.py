"""Deterministic structural benchmark for the private Reviewer Brief
(Issue #309, depends on #304). Covers the properties that must hold
exactly, per skills/github-pr-review/policies/reviewer-brief.md and its
template. Semantic-quality properties whose wording is intentionally
flexible (independent focus value, focus usefulness/specificity for a
human reviewer) are the rubric/reference layer instead:
docs/benchmark/reviewer-brief-examples.md. This module is the
deterministic layer the issue asks for; publication-isolation lives in
test_reviewer_brief_publication_isolation.py so leakage assertions never
share a module with content-shape assertions.
"""

from __future__ import annotations

import re
import unittest

from tests.reference.benchmark.reviewer_brief_fixtures import (
    ALL_CASES,
    REQUIRED_COVERAGE_TAGS,
    ReviewerBriefCase,
    cases_covering,
    out_of_scope_terms_present,
    pair,
)

_SEVERITY_LABEL = re.compile(r"\bP[0-2]\b")
_FINDING_BLOCK_LABELS = ("Evidence:", "Impact:", "Fix:")
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "are", "as", "at", "be", "by", "change", "changes",
        "does", "existing", "for", "fully", "how", "is", "it", "its", "no",
        "not", "of", "on", "or", "regardless", "still", "the", "this", "to",
        "was", "with",
    }
)


def _content_words(text: str) -> set[str]:
    return {word.strip(".,;:`()") for word in text.lower().split()} - _STOPWORDS


class CoverageCompletenessTests(unittest.TestCase):
    """Issue #309's own acceptance criterion: the fixture set must cover
    every required scenario. This makes that criterion machine-checked
    instead of a manual claim in a PR description."""

    def test_every_required_tag_has_at_least_one_covering_case(self) -> None:
        covered = frozenset().union(*(case.covers for case in ALL_CASES))
        missing = REQUIRED_COVERAGE_TAGS - covered
        self.assertEqual(missing, frozenset(), f"uncovered requirement tags: {missing}")

    def test_no_case_declares_an_unknown_tag(self) -> None:
        declared = frozenset().union(*(case.covers for case in ALL_CASES))
        unknown = declared - REQUIRED_COVERAGE_TAGS
        self.assertEqual(unknown, frozenset(), f"undeclared/unknown tags: {unknown}")

    def test_case_ids_are_unique(self) -> None:
        ids = [case.case_id for case in ALL_CASES]
        self.assertEqual(len(ids), len(set(ids)))


class RequiredFieldsTests(unittest.TestCase):
    def test_what_changed_is_non_empty_for_every_case(self) -> None:
        for case in ALL_CASES:
            with self.subTest(case=case.case_id):
                self.assertTrue(case.what_changed.strip())

    def test_user_provided_focus_field_is_non_empty_for_every_case(self) -> None:
        for case in ALL_CASES:
            with self.subTest(case=case.case_id):
                self.assertTrue(case.user_provided_focus_field.strip())

    def test_user_provided_focus_matches_caller_input_or_none_provided(self) -> None:
        for case in ALL_CASES:
            with self.subTest(case=case.case_id):
                if case.user_focus_input is None:
                    self.assertEqual(case.user_provided_focus_field, "none provided")
                else:
                    # Represented faithfully: the caller's own words appear,
                    # even when misleading or conflicting -- the field
                    # reflects what was supplied, not whether it is true.
                    self.assertEqual(case.user_provided_focus_field, case.user_focus_input)

    def test_manual_review_focus_has_two_to_four_bullets(self) -> None:
        for case in ALL_CASES:
            with self.subTest(case=case.case_id):
                self.assertGreaterEqual(len(case.manual_review_focus), 2)
                self.assertLessEqual(len(case.manual_review_focus), 4)

    def test_manual_review_focus_bullets_are_non_empty(self) -> None:
        for case in ALL_CASES:
            for bullet in case.manual_review_focus:
                with self.subTest(case=case.case_id, bullet=bullet):
                    self.assertTrue(bullet.strip())

    def test_open_questions_omitted_not_rendered_empty(self) -> None:
        for case in ALL_CASES:
            with self.subTest(case=case.case_id):
                if case.open_questions is not None:
                    self.assertGreater(len(case.open_questions), 0)
                    for item in case.open_questions:
                        self.assertTrue(item.strip())


class SeverityLabelDisciplineTests(unittest.TestCase):
    """No P0/P1/P2 labels in the brief unless citing an actual finalized
    finding already reported elsewhere (reviewer-brief.md, "Required
    fields")."""

    def test_no_bare_severity_labels_unless_referencing_a_finalized_finding(self) -> None:
        for case in ALL_CASES:
            with self.subTest(case=case.case_id):
                has_label = any(
                    _SEVERITY_LABEL.search(field) for field in case.brief_field_strings()
                )
                if has_label:
                    self.assertTrue(
                        case.references_finalized_finding,
                        f"{case.case_id} uses a P0/P1/P2 label without "
                        "referencing a finalized finding",
                    )


class NoFindingBlockDuplicationTests(unittest.TestCase):
    """Manual review focus must not duplicate full Evidence/Impact/Fix
    finding blocks (reviewer-brief.md, "Required fields" and "Guardrails";
    #309's "finalized findings" coverage requirement)."""

    def test_manual_review_focus_never_contains_finding_block_labels(self) -> None:
        for case in ALL_CASES:
            for bullet in case.manual_review_focus:
                for label in _FINDING_BLOCK_LABELS:
                    with self.subTest(case=case.case_id, label=label, bullet=bullet):
                        self.assertNotIn(label, bullet)

    def test_manual_review_focus_never_repeats_a_github_finding_verbatim(self) -> None:
        for case in cases_covering("findings-inform-focus-no-duplication"):
            for bullet in case.manual_review_focus:
                with self.subTest(case=case.case_id, bullet=bullet):
                    self.assertNotIn(bullet, case.github_review_body)
                    for comment in case.github_inline_comments:
                        self.assertNotIn(bullet, comment)


class IndependentFocusValueTests(unittest.TestCase):
    """The reviewer must be able to add value beyond the caller's own
    wording (reviewer-brief.md, "User-provided focus is an attention
    signal"). Structurally: at least one manual-review-focus bullet must
    not be a restatement of the supplied focus text."""

    def test_independent_focus_present_when_declared(self) -> None:
        for case in ALL_CASES:
            if not case.independent_focus_present:
                continue
            with self.subTest(case=case.case_id):
                if case.user_focus_input is None:
                    # every bullet is reviewer-derived by construction
                    continue
                focus_words = _content_words(case.user_focus_input)
                independently_derived = [
                    bullet
                    for bullet in case.manual_review_focus
                    if len(_content_words(bullet) & focus_words) < 2
                ]
                self.assertTrue(
                    independently_derived,
                    f"{case.case_id} has no manual-review-focus bullet that "
                    "goes beyond the caller's own wording",
                )


class MisleadingAndConflictingFocusGroundingTests(unittest.TestCase):
    def test_forbidden_terms_absent_from_what_changed_and_manual_focus(self) -> None:
        for case in ALL_CASES:
            if not case.forbidden_terms:
                continue
            haystack = "\n".join((case.what_changed, *case.manual_review_focus))
            for term in case.forbidden_terms:
                with self.subTest(case=case.case_id, term=term):
                    self.assertNotIn(term, haystack)

    def test_misleading_focus_still_faithfully_represented_verbatim(self) -> None:
        for case in cases_covering("misleading-focus-grounded"):
            with self.subTest(case=case.case_id):
                self.assertEqual(case.user_provided_focus_field, case.user_focus_input)

    def test_conflicting_focus_case_states_the_repository_truth(self) -> None:
        for case in cases_covering("conflicting-focus-repo-wins"):
            with self.subTest(case=case.case_id):
                self.assertIn("removes", case.what_changed.lower())


class CleanReviewNotDegenerateTests(unittest.TestCase):
    def test_clean_review_brief_is_not_bare_review_clean(self) -> None:
        for case in ALL_CASES:
            if case.decision != "clean":
                continue
            with self.subTest(case=case.case_id):
                self.assertNotEqual(case.what_changed.strip().upper(), "REVIEW CLEAN")
                self.assertGreaterEqual(len(case.manual_review_focus), 2)


class ScopeDisciplineTests(unittest.TestCase):
    """Delta / stacked / partitioned cases must summarize only the
    effective reviewed target, never the full history/stack/partition
    notes (reviewer-brief.md, "Composition with invocation modes")."""

    def test_delta_case_stays_within_the_reviewed_delta(self) -> None:
        for case in cases_covering("delta-review-effective-delta-only"):
            with self.subTest(case=case.case_id):
                self.assertTrue(case.forbidden_terms, "delta case must declare out-of-scope markers")
                self.assertEqual(out_of_scope_terms_present(case), ())

    def test_stacked_case_covers_owned_layer_only(self) -> None:
        for case in cases_covering("stacked-pr-effective-layer-only"):
            with self.subTest(case=case.case_id):
                self.assertTrue(case.forbidden_terms, "stacked case must declare out-of-scope markers")
                self.assertEqual(out_of_scope_terms_present(case), ())

    def test_partitioned_case_has_no_per_partition_notes(self) -> None:
        for case in cases_covering("large-pr-aggregate-not-partition-notes"):
            with self.subTest(case=case.case_id):
                self.assertTrue(case.forbidden_terms, "partitioned case must declare out-of-scope markers")
                self.assertEqual(out_of_scope_terms_present(case), ())


class ScopeDisciplineCheckerCatchesViolationTests(unittest.TestCase):
    """A scope-discipline assertion that could never fail is worthless
    (the same principle
    test_reviewer_brief_publication_isolation.py's LeakCheckerCatchesARealLeakTests
    applies to publication leakage). This proves out_of_scope_terms_present()
    actually detects a delta/stacked-PR scope violation -- the exact
    regression shape #309's "summarizes the effective reviewed
    delta/layer, not the full history/stack" requirement exists to catch
    -- using deliberately broken fixtures, never one of the real corpus
    cases above. Each canary reuses a real case's own forbidden_terms so
    the canary is proven to violate the same scope those terms guard."""

    def test_checker_flags_a_delta_brief_that_leaks_prior_round_files(self) -> None:
        real_case = cases_covering("delta-review-effective-delta-only")[0]
        leaky = ReviewerBriefCase(
            case_id="__negative_canary_delta_leaks_full_history__",
            covers=frozenset(),
            mode="active",
            human_review_output=False,
            decision="clean",
            user_focus_input=None,
            what_changed=(
                "This delta fixes the retry-idempotency gap and also "
                "restates the full review history, including the earlier "
                f"changes to `{real_case.forbidden_terms[0]}` and "
                f"`{real_case.forbidden_terms[1]}`."
            ),
            user_provided_focus_field="none provided",
            manual_review_focus=(
                "Confirm the regression test exercises the double-submit path.",
                "Re-skim the idempotency-key check for the prior off-by-one.",
            ),
            open_questions=None,
            independent_focus_present=True,
            references_finalized_finding=False,
            forbidden_terms=real_case.forbidden_terms,
        )
        self.assertEqual(out_of_scope_terms_present(leaky), real_case.forbidden_terms)

    def test_checker_flags_a_stacked_brief_that_re_analyzes_the_lower_layer(self) -> None:
        real_case = cases_covering("stacked-pr-effective-layer-only")[0]
        leaky = ReviewerBriefCase(
            case_id="__negative_canary_stacked_reanalyzes_lower_layer__",
            covers=frozenset(),
            mode="active",
            human_review_output=False,
            decision="changes-required",
            user_focus_input=None,
            what_changed="Covers both #52's retry wrapper and #41's own diff in full.",
            user_provided_focus_field="none provided",
            manual_review_focus=(
                f"Re-review {real_case.forbidden_terms[0]} from #41's internal implementation.",
                "Confirm the wrapper's backoff policy.",
            ),
            open_questions=None,
            independent_focus_present=True,
            references_finalized_finding=False,
            forbidden_terms=real_case.forbidden_terms,
        )
        self.assertEqual(
            frozenset(out_of_scope_terms_present(leaky)), frozenset(real_case.forbidden_terms)
        )


class HumanReviewOutputSemanticInvarianceTests(unittest.TestCase):
    """`human_review_output` may change wording/compactness only, never
    the semantic fields or their content (reviewer-brief.md, "Composition
    with invocation modes")."""

    def test_pair_exists_with_matching_and_differing_flag(self) -> None:
        matched = pair("human-review-output-pair")
        self.assertEqual(len(matched), 2)
        flags = {case.human_review_output for case in matched}
        self.assertEqual(flags, {True, False})

    def test_pair_shares_required_semantic_keywords(self) -> None:
        matched = pair("human-review-output-pair")
        self.assertEqual(len(matched), 2)
        for case in matched:
            self.assertIsNotNone(case.required_keywords)
            haystack = case.full_brief_text().lower()
            for keyword in case.required_keywords:
                with self.subTest(case=case.case_id, keyword=keyword):
                    self.assertIn(keyword, haystack)

    def test_pair_represents_the_same_user_focus(self) -> None:
        matched = pair("human-review-output-pair")
        focuses = {case.user_provided_focus_field for case in matched}
        self.assertEqual(len(focuses), 1)

    def test_pair_manual_focus_bullet_counts_both_in_two_to_four_range(self) -> None:
        matched = pair("human-review-output-pair")
        for case in matched:
            self.assertGreaterEqual(len(case.manual_review_focus), 2)
            self.assertLessEqual(len(case.manual_review_focus), 4)


if __name__ == "__main__":
    unittest.main()
