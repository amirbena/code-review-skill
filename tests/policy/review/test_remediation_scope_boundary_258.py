#!/usr/bin/env python3
"""Pins the remediation-scope-boundary contract (Issue #258).

Separates a finding's validity/severity from *how much remediation the
current task/PR boundary must absorb* as a mandatory, single-owner
reasoning step applied identically by both Skills, in every invocation
mode. These assertions protect the cross-document invariant, not merely
that each file mentions the feature:

1. one canonical shared policy owns the three-part reasoning sequence and
   the worked examples; `review-scope.md` routes to it rather than
   restating it, the same way it already routes to
   `root-cause-consolidation.md`;
2. both Skills' runbooks apply it identically, after severity/classification
   and before finalizing findings;
3. `invocation-options.md` states explicitly that `human_review_output` /
   `senior_mode` adds no new behavior here — only wording;
4. the finding contract/rendering gains one optional `Follow-up` field,
   never a substitute for a required `Fix`, never a severity input;
5. it never duplicates `severity.md`'s mechanical blocking derivation or
   `root-cause-consolidation.md`'s consolidation pass.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

POLICY = REPO_ROOT / "shared/policies/remediation-scope-boundary.md"
REVIEW_SCOPE = REPO_ROOT / "shared/policies/review-scope.md"
SEVERITY = REPO_ROOT / "shared/policies/severity.md"
ROOT_CAUSE = REPO_ROOT / "shared/policies/root-cause-consolidation.md"
REMEDIATION_GUIDANCE = REPO_ROOT / "shared/policies/remediation-guidance.md"
INVOCATION = REPO_ROOT / "shared/policies/invocation-options.md"
FINDING_TMPL = REPO_ROOT / "shared/templates/finding.md"
FINDING_RENDERING = REPO_ROOT / "shared/templates/finding-rendering.md"
POLICIES_README = REPO_ROOT / "shared/policies/README.md"

GH_REASONING = REPO_ROOT / "skills/github-pr-review/policies/review-reasoning.md"
GH_ACTIVE = REPO_ROOT / "skills/github-pr-review/runbooks/active-pr-review.md"
GH_PASSIVE = REPO_ROOT / "skills/github-pr-review/runbooks/passive-pr-review.md"
GH_SKILL = REPO_ROOT / "skills/github-pr-review/SKILL.md"
LOCAL_RUNBOOK = REPO_ROOT / "skills/local-code-review/runbooks/local-review.md"
LOCAL_SKILL = REPO_ROOT / "skills/local-code-review/SKILL.md"


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class CanonicalOwnerTests(unittest.TestCase):
    """One canonical shared policy owns the reasoning; review-scope.md
    routes to it rather than restating it."""

    def test_policy_file_exists_and_declares_scope(self) -> None:
        t = _norm(POLICY)
        self.assertIn(
            "Applies identically to local-code-review and github-pr-review",
            t,
        )
        self.assertIn("mandatory reasoning step", t)

    def test_review_scope_routes_without_restating(self) -> None:
        t = _norm(REVIEW_SCOPE)
        raw = REVIEW_SCOPE.read_text(encoding="utf-8")
        self.assertIn("## Remediation-scope boundary pass", raw)
        self.assertIn(
            "owned by [remediation-scope-boundary.md](remediation-scope-boundary.md)",
            t,
        )
        self.assertIn("not restated here", t)
        # review-scope.md must not restate the worked examples themselves
        self.assertNotIn("Blocking local defect", t)

    def test_policy_indexed_in_readme(self) -> None:
        raw = POLICIES_README.read_text(encoding="utf-8")
        self.assertIn("remediation-scope-boundary.md", raw)


class ThreePartReasoningTests(unittest.TestCase):
    """The three-part sequence and its outcomes are stated once, in the
    canonical policy."""

    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_three_questions_present(self) -> None:
        for phrase in (
            "Validity and severity",
            "Is remediation required for the current change",
            "How much of that remediation belongs inside the current task/PR",
        ):
            self.assertIn(phrase, self.text)

    def test_three_outcomes_present(self) -> None:
        for phrase in (
            "Bounded local fix is sufficient",
            "Valid concern, broader remediation is separate follow-up",
            "Broader work is genuinely required",
        ):
            self.assertIn(phrase, self.text)

    def test_never_widens_or_shrinks_severity(self) -> None:
        self.assertIn(
            "a P0/P1 still blocks on its bounded fix even when a related "
            "broader concern exists",
            self.text,
        )

    def test_never_defers_genuinely_required_work(self) -> None:
        self.assertIn(
            "do not defer it to a follow-up merely to keep the current "
            "change small",
            self.text,
        )

    def test_worked_examples_present(self) -> None:
        for phrase in (
            "Blocking local defect + broader future concern",
            "Architectural finding whose minimal fix is sufficient",
            "Broader work genuinely required",
        ):
            self.assertIn(phrase, self.text)

    def test_no_new_invocation_flag(self) -> None:
        self.assertIn("No new user-facing invocation flag", self.text)


class NoDuplicationTests(unittest.TestCase):
    """The policy owns its own dimension and defers everything else to
    its existing owner."""

    def test_defers_severity_definitions(self) -> None:
        t = _norm(POLICY)
        self.assertIn(
            "remain solely owned by [severity.md](severity.md) and the "
            "finding-identity/lifecycle model",
            t,
        )
        # the mechanical P0/P1/P2 definitions are not restated
        severity_raw = SEVERITY.read_text(encoding="utf-8")
        self.assertIn("## Decision derivation (mechanical)", severity_raw)
        policy_raw = POLICY.read_text(encoding="utf-8")
        self.assertNotIn("## Decision derivation", policy_raw)

    def test_defers_consolidation(self) -> None:
        t = _norm(POLICY)
        self.assertIn("does not duplicate", t)
        root_cause_raw = ROOT_CAUSE.read_text(encoding="utf-8")
        self.assertIn("## Root-cause and model-completeness pass", root_cause_raw)
        policy_raw = POLICY.read_text(encoding="utf-8")
        self.assertNotIn("## Root-cause", policy_raw)


class RemediationGuidanceWiringTests(unittest.TestCase):
    """remediation-guidance.md's Fix direction reflects the smallest
    remediation, with broader concerns surfaced separately."""

    def test_fix_states_smallest_remediation(self) -> None:
        t = _norm(REMEDIATION_GUIDANCE)
        self.assertIn(
            "the smallest remediation that restores the current change's "
            "contract",
            t,
        )
        self.assertIn("remediation-scope-boundary.md", t)

    def test_broader_concern_is_never_folded_into_fix(self) -> None:
        t = _norm(REMEDIATION_GUIDANCE)
        self.assertIn("never merged into Fix as if it were required", t)


class InvocationOptionsSeniorModeTests(unittest.TestCase):
    """senior_mode / human_review_output confirmed presentation-only for
    this dimension, per the issue's explicit acceptance criterion."""

    def test_presentation_only_list_covers_remediation_scope(self) -> None:
        t = _norm(INVOCATION)
        self.assertIn("remediation-scope-boundary.md", t)
        self.assertIn(
            "on vs. off produces the same finding set, severities, and "
            "remediation-scope-boundary outcomes",
            t,
        )

    def test_senior_mode_owns_wording_only(self) -> None:
        t = _norm(INVOCATION)
        self.assertIn("only wording differs", t)


class FindingContractFollowUpFieldTests(unittest.TestCase):
    """The `Follow-up` field is optional, never a severity input, and
    never a substitute for a required Fix."""

    def test_field_documented_in_fields_list(self) -> None:
        raw = FINDING_TMPL.read_text(encoding="utf-8")
        self.assertIn("**follow-up** — optional", raw)
        t = _norm(FINDING_TMPL)
        self.assertIn(
            "it is never a substitute for a required Fix", t
        )

    def test_field_documented_in_optional_fields_section(self) -> None:
        raw = FINDING_TMPL.read_text(encoding="utf-8")
        idx = raw.find("## Optional and surface-specific fields")
        self.assertNotEqual(idx, -1)
        self.assertIn("follow-up", raw[idx:].lower())

    def test_rendering_examples_present(self) -> None:
        raw = FINDING_RENDERING.read_text(encoding="utf-8")
        self.assertIn("Follow-up:", raw)
        t = _norm(FINDING_RENDERING)
        self.assertIn(
            "there is no separate Follow-up: line on this surface", t
        )


class SkillWiringTests(unittest.TestCase):
    """Both Skills apply the reasoning identically, after classification
    and before finalizing findings."""

    def test_github_review_reasoning_has_section(self) -> None:
        raw = GH_REASONING.read_text(encoding="utf-8")
        self.assertIn("## Remediation-Scope Boundary Review", raw)
        t = _norm(GH_REASONING)
        self.assertIn("remediation-scope-boundary.md", t)

    def test_github_active_runbook_applies_it_after_classification(self) -> None:
        t = _norm(GH_ACTIVE)
        self.assertIn("Remediation-Scope Boundary Review", t)
        self.assertIn("to each material finding before finalizing", t)

    def test_github_passive_runbook_applies_it_after_classification(self) -> None:
        t = _norm(GH_PASSIVE)
        self.assertIn("Remediation-Scope Boundary Review", t)

    def test_local_runbook_applies_it_after_classification(self) -> None:
        t = _norm(LOCAL_RUNBOOK)
        self.assertIn("remediation-scope-boundary.md", t)
        self.assertIn(
            "this never changes the severity or decision derivation just "
            "assigned",
            t,
        )

    def test_both_skill_runbooks_reach_the_policy(self) -> None:
        # Wired via each Skill's runbook/reasoning policy, the same way
        # root-cause-consolidation.md is — not restated in SKILL.md's own
        # line-ceilinged entrypoint list (kept slim per the repository's
        # SoftLineCeilings governance guard).
        for path in (GH_ACTIVE, GH_PASSIVE, LOCAL_RUNBOOK):
            raw = path.read_text(encoding="utf-8")
            self.assertIn("remediation-scope-boundary.md", raw)
        for path in (GH_SKILL, LOCAL_SKILL):
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("remediation-scope-boundary.md", raw)


class NoLexicalDriftTests(unittest.TestCase):
    """Guard against the wiring silently rotting: every consuming file
    must spell the policy filename exactly, so a rename cannot go
    unnoticed by a partial grep."""

    ALL_CONSUMERS = (
        REVIEW_SCOPE,
        REMEDIATION_GUIDANCE,
        INVOCATION,
        FINDING_TMPL,
        FINDING_RENDERING,
        POLICIES_README,
        GH_REASONING,
        GH_ACTIVE,
        GH_PASSIVE,
        LOCAL_RUNBOOK,
    )

    def test_every_consumer_names_the_policy(self) -> None:
        for path in self.ALL_CONSUMERS:
            raw = path.read_text(encoding="utf-8")
            self.assertIn(
                "remediation-scope-boundary.md",
                raw,
                msg=f"{path} does not reference remediation-scope-boundary.md",
            )


if __name__ == "__main__":
    unittest.main()
