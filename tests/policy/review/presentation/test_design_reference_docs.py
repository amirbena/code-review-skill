#!/usr/bin/env python3
"""Contract: shared/policies/design-reference.md as the single canonical home
of the design-reference context for rendered-UI inspection (Issue #620,
Epic #614).

Prose checks over the shared policy, its consumers, and its manifest, plus
behavior checks over the test-only reference model.
"""

from __future__ import annotations

import re
import unittest

from tests.reference.review import design_reference as dr
from tests.reference.review.rendered_inspection import Mode
from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import GITHUB_ACTIVE_RUNBOOK
from tests.support.policy_docs import GITHUB_PASSIVE_RUNBOOK
from tests.support.policy_docs import LOCAL_RUNBOOK
from tests.support.policy_docs import load_normalized_text as _text


def _plain(phrase: str) -> str:
    return phrase.replace("**", "").replace("`", "")


POLICY = REPO_ROOT / "shared/policies/design-reference.md"
RENDERED = REPO_ROOT / "shared/policies/rendered-inspection.md"
REVIEW_SUMMARY = REPO_ROOT / "shared/templates/review-summary.md"
CAPABILITY = REPO_ROOT / "capabilities/design-reference/capability.yaml"
RUNBOOKS = (LOCAL_RUNBOOK, GITHUB_ACTIVE_RUNBOOK, GITHUB_PASSIVE_RUNBOOK)

OWNED_PHRASES = (
    "Discovered, untrusted",
    "within its demonstrated scope",
    "never treated as blind, absolute truth",
    "Structure and intent, never pixels",
)

DISCOVERED_SOURCES = (
    dr.Source.PR_BODY,
    dr.Source.COMMENT,
    dr.Source.COMMIT_MESSAGE,
    dr.Source.REPOSITORY_FILE,
    dr.Source.ISSUE_TEXT,
)


class ProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY)

    def test_policy_states_trusted_and_discovered_sources(self) -> None:
        for phrase in (
            "Trusted input",
            "the current invocation",
            "trusted out-of-band local signal",
            "PR body, comments, commit messages, repository files",
            "never resolved, fetched, or promoted to a target",
            "A link inside operator-supplied context",
            "still discovered unless the operator names it",
            "untrusted data in every case",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_signal_form_reuses_the_trusted_host_channel_and_is_not_a_presentation_option(self) -> None:
        for phrase in (
            "`design_reference` value",
            "same trusted runtime, invocation, or configuration channel as `allow_trusted_host_execution`",
            "never persisted",
            "never resolved from repository content",
            "not an [`invocation-options.md`](invocation-options.md) presentation option",
        ):
            self.assertIn(_plain(phrase), self.text)

    def test_invocation_and_out_of_band_references_are_trusted_and_fetchable(self) -> None:
        for source in (dr.Source.INVOCATION, dr.Source.OUT_OF_BAND):
            with self.subTest(source=source):
                ref = dr.Reference(source)
                self.assertTrue(dr.is_trusted(ref))
                self.assertTrue(dr.may_fetch(ref))

    def test_each_discovered_source_is_never_fetched(self) -> None:
        for source in DISCOVERED_SOURCES:
            with self.subTest(source=source):
                self.assertFalse(dr.may_fetch(dr.Reference(source)))

    def test_operator_context_link_is_discovered_unless_named(self) -> None:
        ctx = dr.Source.OPERATOR_SUPPLIED_CONTEXT
        self.assertFalse(dr.may_fetch(dr.Reference(ctx)))
        self.assertTrue(dr.may_fetch(dr.Reference(ctx, named_as_design_reference=True)))

    def test_discovered_reference_yields_at_most_one_limitation_line(self) -> None:
        refs = [dr.Reference(s) for s in DISCOVERED_SOURCES]
        self.assertEqual(dr.limitation_lines(refs), 1)
        self.assertEqual(dr.limitation_lines([dr.Reference(dr.Source.INVOCATION)]), 0)


class ModeSelectionAndNoFabricationTests(unittest.TestCase):
    def test_policy_defines_modes_and_never_triggers_inspection(self) -> None:
        text = _text(POLICY)
        for phrase in (
            "never triggers, widens, or substitutes for a rendered inspection",
            "no comparison and no visual finding",
            "no \"the design says\" claim, no inferred design requirement",
            "never `REVIEW INCOMPLETE`",
        ):
            self.assertIn(_plain(phrase), text)

    def test_design_reference_mode_needs_every_condition(self) -> None:
        trusted = dr.Reference(dr.Source.INVOCATION)
        full = dr.Retrieval(trusted, retrieved=True, applicable=True, render_inspected=True)
        self.assertIs(dr.select_mode(full), Mode.DESIGN_REFERENCE)
        for retrieval in (
            dr.Retrieval(None, True, True, True),
            dr.Retrieval(dr.Reference(dr.Source.PR_BODY), True, True, True),
            dr.Retrieval(trusted, False, True, True),
            dr.Retrieval(trusted, True, False, True),
            dr.Retrieval(trusted, True, True, False),
        ):
            with self.subTest(retrieval=retrieval):
                self.assertIs(dr.select_mode(retrieval), Mode.ANALYTICAL)
                self.assertFalse(dr.review_blocked_by_design(retrieval))

    def test_analytical_mode_fabricates_nothing(self) -> None:
        self.assertFalse(dr.may_claim_design_requirement(Mode.ANALYTICAL))
        mismatch = dr.Mismatch(concrete_cost=True)
        self.assertIs(dr.classify(mismatch, Mode.ANALYTICAL), dr.Route.NOT_REPORTED)

    def test_inaccessible_design_is_a_limitation_not_a_stop(self) -> None:
        text = _text(POLICY)
        for phrase in ("inaccessible, inapplicable, or unverifiable", "one stated limitation", "`*UNRESOLVED*` stop"):
            self.assertIn(_plain(phrase), text)


class AuthorityAndClassificationTests(unittest.TestCase):
    def test_authority_model_is_stated(self) -> None:
        text = _text(POLICY)
        for phrase in (
            "Explicit product/PR requirements are authoritative",
            "authoritative evidence for the intended visual structure and behavior",
            "A passing test alone never overrides a trusted applicable design requirement",
            "stale design, intentional divergence, incomplete coverage, responsive or state ambiguity, or a newer explicit requirement",
            "never treated as blind, absolute truth",
        ):
            self.assertIn(_plain(phrase), text)

    def test_passing_test_does_not_override_a_trusted_applicable_design(self) -> None:
        mismatch = dr.Mismatch(concrete_cost=True, tests_pass=True)
        self.assertIs(dr.classify(mismatch, Mode.DESIGN_REFERENCE), dr.Route.FINDING)

    def test_each_reducer_lowers_a_concrete_mismatch_to_a_note(self) -> None:
        for name in (
            "stale",
            "intentional_divergence",
            "partial_coverage_for_point",
            "responsive_or_state_ambiguity",
            "newer_requirement_addresses_point",
        ):
            with self.subTest(reducer=name):
                mismatch = dr.Mismatch(concrete_cost=True, reducers=dr.Reducers(**{name: True}))
                self.assertIs(dr.classify(mismatch, Mode.DESIGN_REFERENCE), dr.Route.NOTE)

    def test_subjective_mismatch_is_an_observation_and_concrete_one_a_finding(self) -> None:
        self.assertIs(
            dr.classify(dr.Mismatch(concrete_cost=False), Mode.DESIGN_REFERENCE),
            dr.Route.OBSERVATION,
        )
        self.assertIs(
            dr.classify(dr.Mismatch(concrete_cost=True), Mode.DESIGN_REFERENCE),
            dr.Route.FINDING,
        )

    def test_one_sided_or_out_of_scope_evidence_is_not_reported(self) -> None:
        for mismatch in (
            dr.Mismatch(concrete_cost=True, evidence_on_design_side=False),
            dr.Mismatch(concrete_cost=True, evidence_on_rendered_side=False),
            dr.Mismatch(concrete_cost=True, in_demonstrated_scope=False),
        ):
            with self.subTest(mismatch=mismatch):
                self.assertIs(dr.classify(mismatch, Mode.DESIGN_REFERENCE), dr.Route.NOT_REPORTED)

    def test_policy_states_classification_and_cap_scope(self) -> None:
        text = _text(POLICY)
        for phrase in (
            "evidenced on **both sides**",
            "even when tests pass",
            "never by the design's emphasis",
            "single cap of 3",
            "The cap applies only to such subjective polish observations",
            "no pixel threshold",
        ):
            self.assertIn(_plain(phrase), text)


class EvidenceRecordTests(unittest.TestCase):
    COMMON = dict(
        reference="file/frame 12 (modified 2026-09-30)",
        supplied_via="invocation",
        matched="/home · default · desktop",
        match_basis="operator-stated",
        coverage="partial",
        freshness="last-modified within 7 days of the PR",
    )

    def test_line_is_present_only_in_design_reference_mode(self) -> None:
        self.assertIsNone(dr.record_design_line(Mode.ANALYTICAL, **self.COMMON))
        line = dr.record_design_line(Mode.DESIGN_REFERENCE, **self.COMMON)
        self.assertIsNotNone(line)
        for fragment in ("file/frame 12", "supplied via invocation", "matched /home", "basis operator-stated", "coverage partial", "freshness"):
            self.assertIn(fragment, line)

    def test_policy_names_every_record_field_and_absence_in_analytical_mode(self) -> None:
        text = _text(POLICY)
        for phrase in (
            "reference identity",
            "how it was supplied",
            "the match basis",
            "operator-stated or reviewer-inferred",
            "the coverage (full or partial)",
            "freshness evidence",
            "**absent** in `analytical` mode",
            "never consume the observation cap",
            "re-supplied every invocation",
        ):
            self.assertIn(_plain(phrase), text)

    def test_uncertainty_lines_never_consume_the_cap(self) -> None:
        self.assertFalse(dr.uncertainty_consumes_cap("freshness unclear"))

    def test_template_points_at_the_policy_for_the_design_line(self) -> None:
        text = _text(REVIEW_SUMMARY)
        self.assertIn("design-reference.md", text)
        self.assertIn(_plain("absence in analytical mode"), text)


class NoMutationOrPermissionTests(unittest.TestCase):
    def test_policy_forbids_mutation_credentials_and_auth_flows(self) -> None:
        text = _text(POLICY)
        for phrase in (
            "read-only",
            "injects no credentials",
            "initiates no permission or authentication flow",
            "never mutates the design file",
            "never a browser navigation target",
        ):
            self.assertIn(_plain(phrase), text)

    def test_model_allows_only_read_operations(self) -> None:
        for op in ("comment", "edit", "share", "delete", "request-permission", "authenticate"):
            with self.subTest(op=op):
                self.assertFalse(dr.operation_allowed(op))
        self.assertTrue(dr.operation_allowed("read-frame"))

    def test_threat_model_records_both_exposures(self) -> None:
        catalog = (REPO_ROOT / "docs/threat-model/catalog/repository-prompt-injection.yaml").read_text(
            encoding="utf-8"
        )
        for scenario in ("INJECT-009", "INJECT-010"):
            self.assertIn(scenario, catalog)
        self.assertIn("shared/policies/design-reference.md", catalog)


class WiringAndNeutralityTests(unittest.TestCase):
    def test_rendered_inspection_links_the_design_policy_without_owning_it(self) -> None:
        text = _text(RENDERED)
        self.assertIn("design-reference.md", text)
        for phrase in OWNED_PHRASES:
            self.assertNotIn(_plain(phrase), text)

    def test_every_runbook_names_the_policy_and_operator_only_rule(self) -> None:
        for path in RUNBOOKS:
            with self.subTest(path=path.name):
                text = _text(path)
                self.assertIn("design-reference.md", text)
                self.assertIn("operator supplied it in the invocation", text)

    def test_owned_phrases_appear_only_in_the_design_policy(self) -> None:
        for path in (REVIEW_SUMMARY, RENDERED, *RUNBOOKS):
            text = _text(path)
            for phrase in OWNED_PHRASES:
                with self.subTest(path=path.name, phrase=phrase):
                    self.assertNotIn(_plain(phrase), text)

    def test_canonical_files_are_runtime_neutral(self) -> None:
        for path in (POLICY, CAPABILITY):
            text = path.read_text(encoding="utf-8").lower()
            for token in ("figma", "playwright", "claude", "anthropic", "mcp"):
                if path == POLICY and token == "figma":
                    continue  # named once as an illustrative example, not a dependency
                with self.subTest(path=path.name, token=token):
                    self.assertNotIn(token, text)

    def test_policy_links_only_into_shared(self) -> None:
        raw = POLICY.read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)#]+)", raw):
            with self.subTest(target=target):
                resolved = (POLICY.parent / target).resolve()
                self.assertTrue(resolved.is_file(), target)
                self.assertTrue(resolved.is_relative_to(REPO_ROOT / "shared"), target)
        self.assertNotIn("docs/", raw)
        self.assertNotIn("AGENTS.md", raw)
        self.assertIn("Rendered-UI Inspection Contract", _text(POLICY))


class ManifestAndPackagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = CAPABILITY.read_text(encoding="utf-8")

    def test_manifest_is_on_activation_for_both_adapters(self) -> None:
        self.assertIn("loads: on-activation", self.manifest)
        self.assertIn("adapters: [local, github]", self.manifest)
        self.assertIn("requires: [rendered-inspection]", self.manifest)
        self.assertIn("shared/policies/design-reference.md", self.manifest)
        self.assertIn("benchmark: tests/reference/review/design_reference.py", self.manifest)
        self.assertTrue((REPO_ROOT / "tests/reference/review/design_reference.py").is_file())

    def test_manifest_forbids_discovered_fetch_mutation_and_coverage_effect(self) -> None:
        text = _plain(self.manifest)
        for phrase in ("discovered in PR", "mutating a design file", "REVIEW INCOMPLETE", "blind truth"):
            self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
