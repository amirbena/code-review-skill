#!/usr/bin/env python3
"""Dependency / supply-chain deepening review.

Contract: shared/policies/review-scope.md ("Dependency / supply-chain
deepening review" section — the Infrastructure / deployment dimension's
depth owner, Issue #181). Unlike the other extracted passes, this section
lives inline in review-scope.md itself rather than in its own canonical
policy file (see test_review_scope_core_wiring.py for the
reachability/routing checks that span every extracted pass).
Prose checks only — there is deliberately no second implementation of the
rules (see policies/skill-development-policy.md, "Runbook Design").
"""

from __future__ import annotations

import unittest

from tests.support.policy_docs import REVIEW_SCOPE
from tests.support.policy_docs import extract_section as _section
from tests.support.policy_docs import load_normalized_text as _text
from tests.support.shared_policy_wiring import SectionForwarding, SectionForwardingMixin


class DependencySupplyChainDeepeningSectionTests(unittest.TestCase):
    """(shared semantics) the dependency/supply-chain deepening pass
    reasons about materially implicated compatibility, expansion,
    provenance, and build/runtime risk in a changed dependency manifest,
    lockfile, container base-image reference, or CI/automation action
    reference — never merely because one of those files changed — ties the
    outcome to the existing severity/evidence model, and fails closed on
    an unrecognized format rather than inventing a finding (Issue #181)."""

    def setUp(self) -> None:
        self.section = _section(
            _text(REVIEW_SCOPE),
            "## Dependency / supply-chain deepening review",
            "## Change-risk signals and review depth",
        )

    def test_recognized_inputs_are_named(self) -> None:
        for recognized_input in (
            "package.json",
            "requirements.txt",
            "go.mod",
            "Cargo.toml",
            "build.gradle",
            "Dockerfile",
            "GitHub Actions workflow",
        ):
            self.assertIn(recognized_input, self.section)

    def test_recognition_signal_is_never_itself_the_finding(self) -> None:
        self.assertIn("it is never itself the finding", self.section)
        self.assertIn(
            "a manifest, lockfile, build file, or package-related filename "
            "changing does not by itself activate this pass",
            self.section,
        )

    def test_all_concern_areas_are_present(self) -> None:
        for concern in (
            "Major-version compatibility",
            "Runtime/platform requirement changes",
            "Dependency expansion",
            "Provenance / trust and unpinned automation references",
            "Build/runtime incompatibility",
        ):
            self.assertIn(concern, self.section)

    def test_concern_areas_require_evidence_not_mere_file_change(self) -> None:
        self.assertIn(
            "never merely because the qualifying file changed",
            self.section,
        )
        self.assertIn("not itself a finding", self.section)

    def test_fail_closed_rule_on_unrecognized_format(self) -> None:
        self.assertIn(
            "Fail-closed on an unrecognized manifest, lockfile, or "
            "build-file format",
            self.section,
        )
        self.assertIn("raises no speculative finding for it", self.section)

    def test_reuses_existing_fail_closed_discipline_not_a_new_standard(self) -> None:
        self.assertIn("API / contract compatibility review", self.section)
        self.assertIn(
            "Architectural placement and execution-lifecycle fidelity",
            self.section,
        )
        self.assertIn(
            "not a new evidence standard invented for this section alone",
            self.section,
        )

    def test_no_new_severity_or_score_and_ties_to_existing_model(self) -> None:
        self.assertIn(
            "adds no new severity, finding category, or score", self.section
        )
        self.assertIn("evidence.md", self.section)
        self.assertIn("severity.md", self.section)

    def test_design_record_named_not_linked(self) -> None:
        self.assertIn(
            "dependency/supply-chain deepening model design record",
            self.section,
        )
        self.assertIn("not linked because", self.section)

    def test_never_a_generic_linter_or_file_type_router(self) -> None:
        self.assertIn("not a generic", self.section)
        self.assertIn("dependency-update linter", self.section)
        self.assertIn("vulnerability/CVE", self.section)
        self.assertIn(
            "never by itself sufficient to engage this pass", self.section
        )
        self.assertIn("never a file-type or path router", self.section)

    def test_it_is_the_depth_owner_of_infrastructure_deployment(self) -> None:
        self.assertIn(
            'of the "Infrastructure / deployment"', self.section
        )
        self.assertIn("Semantic change-implication reasoning", self.section)
        self.assertIn("not a second scope model", self.section)

    def test_does_not_resolve_install_or_enforce_undefined_policy(self) -> None:
        self.assertIn("does not resolve or install", self.section)
        self.assertIn("dedicated vulnerability/SCA scanner", self.section)
        self.assertIn(
            "does not enforce a dependency policy this repository has not",
            self.section,
        )

    def test_dimension_depth_owner_line_names_this_section(self) -> None:
        text = _text(REVIEW_SCOPE)
        dimension_section = _section(
            text,
            "Infrastructure / deployment",
            "Security / trust boundaries",
        )
        self.assertIn(
            "Dependency / supply-chain deepening review", dimension_section
        )


class DependencySupplyChainDeepeningWiredIntoBothSkillsTests(SectionForwardingMixin, unittest.TestCase):
    forwarding = SectionForwarding(
        name="dependency-supply-chain-deepening",
        reasoning_heading="## Dependency / Supply-Chain Deepening Review",
        shared_phrase="Dependency / supply-chain deepening review",
        index_phrase="dependency / supply-chain",
        runbook_heading="Dependency / Supply-Chain Deepening Review",
        local_window_start="Dependency / supply-chain deepening review",
    )


if __name__ == "__main__":
    unittest.main()
