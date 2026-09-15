#!/usr/bin/env python3
"""Prose / documentation-contract checks for docs/threat-model/ (Issue #300).

Mirrors the style of tests/policy/review/* and tests/policy/governance/*:
these are structural/content checks over Markdown, not a second validator
for the YAML catalog itself — scripts/security/validate_threat_model.py and
tests/unit/security/test_validate_threat_model.py own that.
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT

THREAT_MODEL_DIR = REPO_ROOT / "docs" / "threat-model"
README = THREAT_MODEL_DIR / "README.md"
MODEL_DOC = THREAT_MODEL_DIR / "threat-model.md"
CATALOG_DIR = THREAT_MODEL_DIR / "catalog"
CATALOG_README = CATALOG_DIR / "README.md"
VALIDATOR = REPO_ROOT / "scripts" / "security" / "validate_threat_model.py"
TRACEABILITY_VALIDATOR = REPO_ROOT / "scripts" / "security" / "validate_threat_model_traceability.py"

REQUIRED_CATEGORIES = ("AUTH", "SBOX", "DELEG", "INJECT", "GIT", "SCOPE", "DOS")
REQUIRED_ATTACKER_MODELS = (
    "malicious_contributor",
    "prompt_injected_context",
    "compromised_agent",
    "confused_deputy",
    "runtime_misconfiguration",
    "resource_abuse",
)


class DocumentPresenceTests(unittest.TestCase):
    def test_all_expected_documents_exist(self) -> None:
        for path in (README, MODEL_DOC, CATALOG_README, VALIDATOR, TRACEABILITY_VALIDATOR):
            self.assertTrue(path.is_file(), f"missing {path}")

    def test_every_category_yaml_file_exists(self) -> None:
        expected = {
            "AUTH": "mutation-authority.yaml",
            "SBOX": "sandbox-runtime-validation.yaml",
            "DELEG": "spawn-delegation.yaml",
            "INJECT": "repository-prompt-injection.yaml",
            "GIT": "checkout-git-safety.yaml",
            "SCOPE": "scope-evidence-integrity.yaml",
            "DOS": "resource-abuse.yaml",
        }
        for category, filename in expected.items():
            with self.subTest(category=category):
                self.assertTrue((CATALOG_DIR / filename).is_file())


class ReadmeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = README.read_text(encoding="utf-8")

    def test_not_packaged_disclaimer_present(self) -> None:
        self.assertIn("not** packaged", self.text)

    def test_links_the_parent_and_sibling_issues(self) -> None:
        for issue in ("#298", "#299", "#300", "#301", "#302", "#303", "#305", "#306", "#307", "#308", "#310"):
            with self.subTest(issue=issue):
                self.assertIn(issue, self.text)

    def test_links_the_validator(self) -> None:
        self.assertIn("scripts/security/validate_threat_model.py", self.text)


class ThreatModelDocContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = MODEL_DOC.read_text(encoding="utf-8")

    def test_states_the_non_cooperative_design_constraint(self) -> None:
        text = " ".join(self.text.split())
        self.assertIn("non-cooperative", text)

    def test_names_every_trust_domain_from_the_issue(self) -> None:
        required_phrases = (
            "user / maintainer",
            "review-performing agent",
            "nested / parallel agents",
            "agent-spawn / delegation runtime",
            "GitHub integration",
            "repository and PR contents",
            "repository instruction files",
            "repository-defined executable code",
            "checkout / working copy",
            "remediation proposal",
            "mutation executor",
            "runtime-validation sandbox",
            "authorization capability source",
            "host filesystem / credentials / network",
            "external services",
        )
        lowered = self.text.lower()
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), lowered)

    def test_names_every_adversary_failure_model(self) -> None:
        for model in REQUIRED_ATTACKER_MODELS:
            with self.subTest(model=model):
                self.assertIn(f"`{model}`", self.text)

    def test_names_every_threat_domain_prefix(self) -> None:
        for category in REQUIRED_CATEGORIES:
            with self.subTest(category=category):
                self.assertIn(f"`{category}-###`", self.text)

    def test_distinguishes_threat_severity_from_review_finding_severity(self) -> None:
        self.assertIn("P0", self.text)
        self.assertIn("P1", self.text)
        self.assertIn("P2", self.text)
        self.assertIn("distinct", self.text.lower())

    def test_states_the_coverage_gap_and_not_applicable_tokens(self) -> None:
        self.assertIn("COVERAGE_GAP", self.text)
        self.assertIn("NOT_APPLICABLE", self.text)

    def test_names_dependent_issues_consuming_the_catalog(self) -> None:
        for issue in ("#299", "#305", "#306", "#307", "#308", "#310"):
            with self.subTest(issue=issue):
                self.assertIn(issue, self.text)

    def test_does_not_redefine_review_decision_semantics(self) -> None:
        # The threat model must never restate REVIEW CLEAN / CHANGES REQUIRED
        # as if it owned those decision values — it only references the rule
        # that a failure must never collapse into one.
        self.assertNotIn("REVIEW CLEAN is derived from", self.text)


class CatalogReadmeSchemaContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = CATALOG_README.read_text(encoding="utf-8")

    def test_documents_every_required_field(self) -> None:
        required_fields = (
            "id", "title", "category", "attacker_model",
            "attacker_controlled_inputs", "assumed_attacker_capabilities",
            "trusted_inputs", "protected_asset", "required_capability_state",
            "enforcement_owner", "enforcement_point", "expected_safe_outcome",
            "expected_security_event", "benchmark_family", "benchmark_reference",
            "regression_evidence", "threat_severity",
        )
        for f in required_fields:
            with self.subTest(field=f):
                self.assertIn(f"`{f}`", self.text)

    def test_states_ids_are_stable_not_derived_from_filenames_or_lines(self) -> None:
        text = " ".join(self.text.split())
        self.assertIn("never derived from a test filename or line number", text)

    def test_links_the_single_reference_validator(self) -> None:
        self.assertIn("scripts/security/validate_threat_model.py", self.text)
        self.assertIn("never a second one", self.text)

    def test_documents_coverage_gap_semantics(self) -> None:
        self.assertIn("COVERAGE_GAP", self.text)
        self.assertIn("NOT_APPLICABLE", self.text)

    def test_documents_the_traceability_contract(self) -> None:
        self.assertIn("Traceability", self.text)
        self.assertIn("#310", self.text)

    def test_links_the_traceability_validator(self) -> None:
        self.assertIn("scripts/security/validate_threat_model_traceability.py", self.text)


class TraceabilityValidatorLinkedFromReadmeTests(unittest.TestCase):
    def test_readme_links_the_traceability_validator(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("scripts/security/validate_threat_model_traceability.py", text)


if __name__ == "__main__":
    unittest.main()
