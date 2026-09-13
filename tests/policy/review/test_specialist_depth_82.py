#!/usr/bin/env python3
"""Pins the specialist-depth composition contract (Issue #82).

Defines how a reviewer decides, for a dimension already identified as
materially implicated by the base semantic-implication pass (#211), whether
the available evidence justifies deeper domain-specific reasoning, and how
0..N such deepening capabilities compose into one review — reusing #87's
bounded-expansion/stop-condition contract for cascading activation and
#258's remediation-scope-boundary contract rather than letting review depth
alone expand required remediation. These assertions protect the
cross-document invariant, not merely that each file mentions the feature:

1. one canonical shared policy owns the activation/composition contract;
   `review-scope.md` routes to it rather than restating it, the same way it
   already routes to `remediation-scope-boundary.md` and
   `root-cause-consolidation.md`;
2. base per-dimension consideration (#211) is never gated, narrowed, or
   replaced by a domain-specific deepening capability;
3. cascading activation reuses #87's expansion/stop-condition contract —
   no second expansion model;
4. review depth never by itself expands required remediation — #258's
   contract governs that exclusively;
5. explicit user focus is additive only;
6. no persona/profile terminology, no new runtime plugin machinery, no new
   finding/severity/evidence schema;
7. both Skills' runbooks/reasoning policies wire it identically, alongside
   "Semantic Implication Review."
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

POLICY = REPO_ROOT / "shared/policies/specialist-depth.md"
REVIEW_SCOPE = REPO_ROOT / "shared/policies/review-scope.md"
REPOSITORY_EXPANSION = REPO_ROOT / "shared/policies/repository-expansion.md"
REVIEW_STOPPING = REPO_ROOT / "shared/policies/review-stopping-criteria.md"
REMEDIATION_SCOPE = REPO_ROOT / "shared/policies/remediation-scope-boundary.md"
SEVERITY = REPO_ROOT / "shared/policies/severity.md"
INVOCATION = REPO_ROOT / "shared/policies/invocation-options.md"
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
    """One canonical shared policy owns the contract; review-scope.md
    routes to it rather than restating it."""

    def test_policy_file_exists_and_declares_scope(self) -> None:
        t = _norm(POLICY)
        self.assertIn(
            "Applies identically to local-code-review and github-pr-review",
            t,
        )

    def test_review_scope_routes_without_restating(self) -> None:
        raw = REVIEW_SCOPE.read_text(encoding="utf-8")
        t = _norm(REVIEW_SCOPE)
        self.assertIn("## Domain-specific deepening pass", raw)
        self.assertIn(
            "owned by [specialist-depth.md](specialist-depth.md)", t
        )
        self.assertIn("not restated here", t)
        # review-scope.md must not restate the worked examples themselves
        self.assertNotIn("misleading superficial signal", t)

    def test_dangling_sentence_now_routes_instead_of_deferring(self) -> None:
        t = _norm(REVIEW_SCOPE)
        self.assertIn(
            "owned by \"Domain-specific deepening pass\" below, not by "
            "this section",
            t,
        )
        self.assertNotIn("is outside this section's scope", t)

    def test_policy_indexed_in_readme(self) -> None:
        raw = POLICIES_README.read_text(encoding="utf-8")
        self.assertIn("specialist-depth.md", raw)


class BaseObligationUnconditionalTests(unittest.TestCase):
    """A domain-specific deepening capability never decides whether a
    dimension is considered at all — #211's base pass owns that,
    unconditionally."""

    def test_policy_states_it_never_decides_dimension_consideration(self) -> None:
        t = _norm(POLICY)
        self.assertIn(
            "whether a dimension is considered at all is decided there, "
            "unconditionally",
            t,
        )

    def test_review_scope_states_deepening_never_gates_base_pass(self) -> None:
        t = _norm(REVIEW_SCOPE)
        self.assertIn(
            "a domain-specific deepening capability never decides whether "
            "a dimension is considered at all",
            t,
        )


class EvidenceDrivenActivationTests(unittest.TestCase):
    """Activation is evidence-driven, never a file-type/path/framework
    router."""

    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_signals_never_independently_sufficient(self) -> None:
        self.assertIn(
            "None is independently sufficient to require or suppress "
            "domain-specific deepening",
            self.text,
        )

    def test_sql_worked_contrast_present(self) -> None:
        self.assertIn(
            'is not equivalent to "run database specialist depth."',
            self.text,
        )

    def test_implication_without_expected_file_type_present(self) -> None:
        self.assertIn(
            "database implications can arise from application code that "
            "touches no .sql file and no migration directory at all",
            self.text,
        )


class CompositionAndCascadingTests(unittest.TestCase):
    """0..N composability and cascading activation bounded by #87."""

    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_zero_to_n_composability_stated(self) -> None:
        self.assertIn(
            "A review may require zero, one, or several domain-specific "
            "deepening capabilities",
            self.text,
        )

    def test_capabilities_compose_never_independent_verdicts(self) -> None:
        self.assertIn(
            "they never produce independent reviewer verdicts, "
            "independent severity scales, or independent output schemas",
            self.text,
        )

    def test_cascading_reuses_repository_expansion_contract(self) -> None:
        self.assertIn("not a second expansion mechanism", self.text)
        self.assertIn(
            "reuses [repository-expansion.md](repository-expansion.md)'s "
            "fixed trigger/ring/ceiling procedure and "
            "[review-stopping-criteria.md](review-stopping-criteria.md)'s "
            "coverage and stop conditions",
            self.text,
        )

    def test_no_second_expansion_model_in_nongoals(self) -> None:
        self.assertIn(
            "cascading activation reuses their existing trigger catalog, "
            "ring procedure, and stop conditions rather than introducing "
            "a second expansion or stopping model",
            self.text,
        )

    def test_repository_expansion_and_stopping_files_unchanged_owners(self) -> None:
        expansion_raw = REPOSITORY_EXPANSION.read_text(encoding="utf-8")
        stopping_raw = REVIEW_STOPPING.read_text(encoding="utf-8")
        policy_raw = POLICY.read_text(encoding="utf-8")
        # the canonical trigger catalog / stop-condition text lives only in
        # its own owning files, not duplicated into specialist-depth.md
        self.assertTrue(expansion_raw.strip())
        self.assertTrue(stopping_raw.strip())
        self.assertNotIn("## Fixed trigger catalog", policy_raw)


class RemediationScopeOrthogonalityTests(unittest.TestCase):
    """Review depth never by itself expands required remediation; #258's
    contract governs that exclusively."""

    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_orthogonality_invariant_stated(self) -> None:
        self.assertIn(
            "The fact that reasoning went deeper must never, by itself, "
            "expand what the current task/PR is required to remediate",
            self.text,
        )

    def test_defers_to_remediation_scope_boundary_contract(self) -> None:
        self.assertIn(
            "remains governed exclusively by "
            "[remediation-scope-boundary.md](remediation-scope-boundary.md)'s "
            "three-part reasoning sequence",
            self.text,
        )
        policy_raw = POLICY.read_text(encoding="utf-8")
        remediation_raw = REMEDIATION_SCOPE.read_text(encoding="utf-8")
        self.assertIn(
            "## Three-part reasoning (mandatory, per material finding)",
            remediation_raw,
        )
        self.assertNotIn("## Three-part reasoning", policy_raw)

    def test_case_g_depth_vs_remediation_scope_present(self) -> None:
        self.assertIn("Case G", self.text)
        self.assertIn(
            "the deeper analysis that produced it does not by itself "
            "enlarge what the current change must fix",
            self.text,
        )


class UserFocusAdditiveOnlyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_additive_only_rule_present(self) -> None:
        self.assertIn(
            "Explicit focus is an override on depth, not the activation "
            "mechanism",
            self.text,
        )

    def test_never_clauses_present(self) -> None:
        for phrase in (
            "narrow the base review",
            "suppress other materially implicated dimensions",
            "lower the evidence bar",
            "change severity or remediation-scope-boundary semantics",
        ):
            self.assertIn(phrase, self.text)


class TerminologyAndNoPersonaTests(unittest.TestCase):
    """No stale persona/profile terminology; no new runtime plugin
    machinery; no new finding/severity/evidence schema."""

    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_uses_deepening_capability_terminology(self) -> None:
        self.assertIn("domain-specific deepening capability", self.text)
        self.assertIn("adaptive deepening", self.text)

    def test_rejects_persona_and_selectable_profile_language(self) -> None:
        self.assertIn(
            "the model is not a persona system", self.text
        )
        # the banned terms appear exactly once each, inside the explicit
        # "do not use" sentence that names them to reject them — never as
        # a description of how activation actually works
        self.assertEqual(self.text.count("selectable profile"), 1)
        self.assertEqual(self.text.count("reviewer persona"), 1)
        self.assertIn(
            'Do not use "selectable profile," "selected profile," or '
            '"reviewer persona"',
            self.text,
        )

    def test_rejects_plugin_engine_requirements(self) -> None:
        for phrase in (
            "a generic plugin registry",
            "a deterministic file/path",
            "an external orchestration service",
            "a new agent per domain",
            "persistent activation state",
            "a user-facing specialist selector",
        ):
            self.assertIn(phrase, self.text)

    def test_no_new_output_schema(self) -> None:
        self.assertIn(
            "it introduces no new finding/severity/evidence schema", " ".join(
                REVIEW_SCOPE.read_text(encoding="utf-8").split()
            )
        )


class WorkedExamplesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _norm(POLICY)

    def test_all_seven_cases_present(self) -> None:
        for case in ("Case A", "Case B", "Case C", "Case D", "Case E", "Case F", "Case G"):
            self.assertIn(case, self.text)


class InvocationOptionsPresentationOnlyTests(unittest.TestCase):
    def test_presentation_only_clause_present(self) -> None:
        t = _norm(INVOCATION)
        self.assertIn("specialist-depth.md", t)
        self.assertIn(
            "on vs. off produces the same set of engaged capabilities and "
            "the same findings, only wording differs",
            t,
        )


class SkillWiringTests(unittest.TestCase):
    """Both Skills apply the contract identically, alongside Semantic
    Implication Review."""

    def test_github_review_reasoning_has_section(self) -> None:
        raw = GH_REASONING.read_text(encoding="utf-8")
        self.assertIn("## Domain-Specific Deepening Review", raw)
        t = _norm(GH_REASONING)
        self.assertIn("specialist-depth.md", t)

    def test_github_active_runbook_references_it(self) -> None:
        t = _norm(GH_ACTIVE)
        self.assertIn("Domain-Specific Deepening Review", t)
        self.assertIn("specialist-depth.md", t)

    def test_github_passive_runbook_references_it(self) -> None:
        t = _norm(GH_PASSIVE)
        self.assertIn("Domain-Specific Deepening Review", t)
        self.assertIn("specialist-depth.md", t)

    def test_local_runbook_references_it(self) -> None:
        t = _norm(LOCAL_RUNBOOK)
        self.assertIn("specialist-depth.md", t)
        self.assertIn("Domain-specific deepening pass", t)

    def test_both_skill_runbooks_reach_the_policy_not_skill_md(self) -> None:
        # Wired via each Skill's runbook/reasoning policy, the same way
        # remediation-scope-boundary.md is — not restated in SKILL.md's own
        # line-ceilinged entrypoint list.
        for path in (GH_ACTIVE, GH_PASSIVE, LOCAL_RUNBOOK):
            raw = path.read_text(encoding="utf-8")
            self.assertIn("specialist-depth.md", raw)
        for path in (GH_SKILL, LOCAL_SKILL):
            raw = path.read_text(encoding="utf-8")
            self.assertNotIn("specialist-depth.md", raw)


class NoLexicalDriftTests(unittest.TestCase):
    """Guard against the wiring silently rotting: every consuming file
    must spell the policy filename exactly, so a rename cannot go
    unnoticed by a partial grep."""

    ALL_CONSUMERS = (
        REVIEW_SCOPE,
        INVOCATION,
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
                "specialist-depth.md",
                raw,
                msg=f"{path} does not reference specialist-depth.md",
            )


if __name__ == "__main__":
    unittest.main()
