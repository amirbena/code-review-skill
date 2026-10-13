#!/usr/bin/env python3
"""Contract: shared/policies/dependency-graph-regression.md and the
docs/dependency-graph-regression/ design record (Issue #723).

Prose and wiring checks only. The policy is a contract that stays unwired
until #724, so these also pin that nothing packaged references it yet.
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import (
    GITHUB_ACTIVE_RUNBOOK,
    GITHUB_PASSIVE_RUNBOOK,
    GITHUB_REASONING,
    GITHUB_REVIEW_INDEX,
    GITHUB_SKILL_MD,
    LOCAL_RUNBOOK,
    LOCAL_SKILL_MD,
)
from tests.support.policy_docs import load_normalized_text as _text

POLICY = REPO_ROOT / "shared/policies/dependency-graph-regression.md"
MODEL = REPO_ROOT / "docs/dependency-graph-regression/dependency-graph-regression-model.md"
ACQUISITION = REPO_ROOT / "docs/dependency-graph-regression/resolution-acquisition.md"
ROOT_CAUSE = REPO_ROOT / "docs/dependency-graph-regression/root-cause-replay.md"
METADATA = REPO_ROOT / "docs/dependency-graph-regression/metadata-only-resolution.md"
FIDELITY = REPO_ROOT / "docs/dependency-graph-regression/fidelity-study.md"
README = REPO_ROOT / "docs/dependency-graph-regression/README.md"

EVIDENCE_STATES = ("available", "missing", "partial", "stale", "untrusted", "mismatched")
DELTA_RECORDS = ("added", "removed", "version-changed", "scope-changed", "newly-evicted", "newly-conflicting")
CATEGORIES = (
    "Binary/API incompatibility",
    "Runtime classpath conflict",
    "Incompatible library families",
    "Cryptographic provider conflict",
    "Compliance-sensitive substitution",
    "Convergence problem",
    "Missing/incompatible peer",
)


class PolicyContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY).replace("`", "").replace("**", "")

    def test_states_core_invariant(self) -> None:
        self.assertIn(
            "A resolved graph is evidence of what resolves, never proof of what breaks; "
            "and no acquired, bound graph means no graph claim.",
            self.text,
        )

    def test_declares_itself_unwired(self) -> None:
        self.assertIn("contract only, unwired", self.text.lower())

    def test_defines_every_evidence_state(self) -> None:
        for state in EVIDENCE_STATES:
            with self.subTest(state=state):
                self.assertIn(f"| {state} |", self.text)

    def test_defines_every_delta_record(self) -> None:
        for record in DELTA_RECORDS:
            with self.subTest(record=record):
                self.assertIn(f"| {record} |", self.text)

    def test_defines_every_compatibility_category(self) -> None:
        for category in CATEGORIES:
            with self.subTest(category=category):
                self.assertIn(f"| {category} |", self.text)

    def test_separates_the_two_stages(self) -> None:
        self.assertIn("A delta record is never a finding.", self.text)
        self.assertIn("never adds a node, edge, or version that is absent", self.text)

    def test_unsupported_evidence_is_never_finding_evidence(self) -> None:
        self.assertIn("stale, untrusted, and mismatched evidence is never finding evidence", self.text.lower())

    def test_grants_no_execution_or_network(self) -> None:
        for phrase in (
            "never grants execution or network access",
            "Acquisition failure never falls back",
            "maintainer-approved amendment",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_states_no_literal_p3(self) -> None:
        self.assertIn("No literal P3 exists", self.text)

    def test_names_no_hardcoded_library_rule(self) -> None:
        self.assertIn("No library family (BouncyCastle included) is hardcoded", self.text)


class ContractSectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = _text(POLICY).replace("`", "").replace("**", "")

    def test_distinguishes_completeness_from_fidelity(self) -> None:
        for phrase in ("Completeness versus fidelity", "available requires both complete and established", "unestablished", "false negative", "false positive"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), self.text.lower())

    def test_fail_closed_table_covers_every_required_input(self) -> None:
        section = self.text.split("Fail-closed resolution inputs", 1)[1].split("Production-enablement gates", 1)[0].lower()
        for phrase in ("profile activation not established", "missing transitive", "extensions", "version range", "snapshot", "base and head differ", "never treated as a leaf"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, section)

    def test_knowledge_source_contract_separates_presence_from_incompatibility(self) -> None:
        for phrase in (
            "A graph proves that dependencies are present",
            "does not by itself prove that they are incompatible",
            "support no conclusion",
            "never presented as fact",
            "pre-existing and not attributable",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.text)

    def test_every_enablement_gate_is_listed(self) -> None:
        section = self.text.split("Production-enablement gates", 1)[1]
        for gate in ("G1 ", "G2 ", "G3 ", "G4 ", "G5 ", "G6 ", "G7 ", "G8 "):
            with self.subTest(gate=gate):
                self.assertIn(f"| {gate}", section)
        self.assertIn("approved in principle and not enabled", self.text)


class DesignRecordTests(unittest.TestCase):
    def test_every_document_exists(self) -> None:
        for path in (README, MODEL, ACQUISITION, ROOT_CAUSE, METADATA, FIDELITY):
            self.assertTrue(path.is_file(), f"missing {path}")

    def test_root_cause_classifies_every_hypothesis(self) -> None:
        text = _text(ROOT_CAUSE)
        for phrase in ("Missing graph evidence", "Activation", "Reasoning", "Severity suppression", "Not determinable"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_acquisition_decides_every_path_and_leaves_boundaries_unchanged(self) -> None:
        text = _text(ACQUISITION)
        for phrase in (
            "caller-supplied",
            "static-lockfile",
            "repository-ci-artifact",
            "Offline resolution",
            "trusted-host",
            "Approved amendments: none",
            "is not reduced",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), text.lower())

    def test_metadata_research_classifies_the_approach_and_grants_nothing(self) -> None:
        text = _text(METADATA)
        for phrase in (
            "Feasible only with explicitly approved new boundaries",
            "Running Maven against an untrusted project",
            "Parsing Maven metadata as inert data",
            "Resolving through an isolated resolver",
            "do not reduce Maven scope",
            "nothing in this record grants it",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), text.lower())

    def test_fidelity_study_states_approvals_and_keeps_everything_inactive(self) -> None:
        text = _text(FIDELITY)
        for phrase in ("D1", "D4", "D5", "D6", "dedicated, read-only cache", "authorizes nothing", "Maven stays in scope"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_policy_lists_metadata_resolution_as_not_admitted(self) -> None:
        text = _text(POLICY)
        self.assertIn("metadata-resolution", text)
        self.assertIn("Approved in principle; not enabled", text)
        self.assertIn("Network access and credential access are not authorized", text)

    def test_incident_delta_is_marked_unavailable_and_not_assumed_introduced(self) -> None:
        text = _text(MODEL)
        self.assertIn("exact Base/Head delta is unavailable", text)
        self.assertIn("nothing in this record claims the BOM upgrade first introduced non-FIPS dependencies", text)

    def test_model_has_worked_examples_for_incident_npm_and_gradle(self) -> None:
        text = _text(MODEL)
        for phrase in ("the incident", "npm", "Gradle"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


class UnwiredTests(unittest.TestCase):
    """No SKILL.md, runbook, capability manifest, or package manifest may reference the policy until #724."""

    GATEKEEPERS = (
        LOCAL_SKILL_MD,
        GITHUB_SKILL_MD,
        LOCAL_RUNBOOK,
        GITHUB_ACTIVE_RUNBOOK,
        GITHUB_PASSIVE_RUNBOOK,
        GITHUB_REVIEW_INDEX,
        GITHUB_REASONING,
        REPO_ROOT / "skills/local-code-review/metadata/skill.yaml",
        REPO_ROOT / "skills/github-pr-review/metadata/skill.yaml",
        REPO_ROOT / "scripts/packaging/package-manifest.json",
        REPO_ROOT / "scripts/packaging/generate_package_manifest.py",
    )

    def test_no_gatekeeper_references_the_policy(self) -> None:
        offenders = [str(p.relative_to(REPO_ROOT)) for p in self.GATEKEEPERS if "dependency-graph-regression" in p.read_text(encoding="utf-8")]
        self.assertEqual(offenders, [], "the dependency-graph policy must stay unwired until #724")


if __name__ == "__main__":
    unittest.main()
