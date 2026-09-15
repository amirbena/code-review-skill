#!/usr/bin/env python3
"""Documentation-contract coverage for Issue #299: the denied-capability
security-event taxonomy.

Pins docs/security-events/{README.md,security-event-model.md}'s core
content, that it names itself authoritative over the threat-model
catalog's `expected_security_event` vocabulary, and that each packaged
policy which reports a denied-capability event actually carries a
"Reporting an event" / "Reporting a denied event" section citing the
right event names — so a later edit cannot quietly drop the taxonomy or
let a policy's reported events drift from it.
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT

SECURITY_EVENTS_DIR = REPO_ROOT / "docs" / "security-events"
README = SECURITY_EVENTS_DIR / "README.md"
MODEL_DOC = SECURITY_EVENTS_DIR / "security-event-model.md"
VALIDATOR = REPO_ROOT / "scripts" / "security" / "validate_threat_model.py"

MUTATION_AUTHORITY = REPO_ROOT / "shared" / "policies" / "mutation-authority.md"
AGENT_DELEGATION = REPO_ROOT / "shared" / "policies" / "agent-delegation.md"
RUNTIME_VALIDATION = REPO_ROOT / "shared" / "policies" / "runtime-validation.md"
REVIEW_ACTION_AUTH = (
    REPO_ROOT / "skills" / "github-pr-review" / "policies" / "review-action-authorization.md"
)

MUTATION_EVENTS = (
    "DENIED_MUTATION_CAPABILITY_ABSENT",
    "DENIED_MUTATION_UNAUTHORIZED",
    "DENIED_MUTATION_STALE_APPROVAL",
    "DENIED_MUTATION_SCOPE_ESCAPE",
    "DENIED_MUTATION_AUTHORIZATION_REPLAY",
)
SANDBOX_EVENTS = (
    "DENIED_SANDBOX_NETWORK_ACCESS",
    "DENIED_SANDBOX_CREDENTIAL_ACCESS",
    "DENIED_SANDBOX_FILESYSTEM_ACCESS",
    "DENIED_SANDBOX_RESOURCE_EXHAUSTION",
    "DENIED_SANDBOX_UNAVAILABLE_PRIMITIVE",
    "DENIED_GIT_UNSAFE_CONFIG",
    "DENIED_GIT_PATH_ESCAPE",
)
DELEGATION_EVENTS = (
    "DENIED_SPAWN_UNAUTHORIZED",
    "DENIED_SPAWN_BUDGET_EXCEEDED",
    "DENIED_SPAWN_DEPTH_EXCEEDED",
    "DENIED_DELEGATION_AUTHORITY_ESCALATION",
    "DENIED_DELEGATION_REPLAY",
)
REVIEW_ACTION_EVENTS = (
    "DENIED_REVIEW_ACTION_SELF_REVIEW",
    "DENIED_REVIEW_ACTION_UNAUTHORIZED",
    "DENIED_REVIEW_ACTION_STALE_HEAD",
)
CLASSIFICATIONS = ("expected_denial", "boundary_violation_attempt")


class DocumentPresenceTests(unittest.TestCase):
    def test_readme_and_model_doc_exist(self) -> None:
        self.assertTrue(README.exists())
        self.assertTrue(MODEL_DOC.exists())


class ReadmeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = README.read_text(encoding="utf-8")

    def test_links_issue_299(self) -> None:
        self.assertIn("#299", self.text)

    def test_not_packaged_disclaimer_present(self) -> None:
        self.assertIn("not** packaged", self.text)

    def test_names_the_dependent_enforcement_issues(self) -> None:
        for issue in ("#301", "#302", "#303", "#308"):
            self.assertIn(issue, self.text)


class ModelDocContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = MODEL_DOC.read_text(encoding="utf-8")

    def test_names_every_mutation_event(self) -> None:
        for event in MUTATION_EVENTS:
            self.assertIn(event, self.text, event)

    def test_names_every_sandbox_event(self) -> None:
        for event in SANDBOX_EVENTS:
            self.assertIn(event, self.text, event)

    def test_names_every_delegation_event(self) -> None:
        for event in DELEGATION_EVENTS:
            self.assertIn(event, self.text, event)

    def test_names_every_review_action_event(self) -> None:
        for event in REVIEW_ACTION_EVENTS:
            self.assertIn(event, self.text, event)

    def test_names_both_classifications(self) -> None:
        for value in CLASSIFICATIONS:
            self.assertIn(value, self.text, value)

    def test_states_the_deterministic_derivation_rule(self) -> None:
        self.assertIn("Deterministic derivation rule", self.text)
        self.assertIn("runtime evidence", self.text)
        self.assertIn("inferred model intent", self.text)

    def test_states_the_non_weakening_invariant(self) -> None:
        self.assertIn("never", self.text)
        self.assertIn("changes which findings exist", self.text)

    def test_states_what_an_event_must_never_record(self) -> None:
        normalized = " ".join(self.text.split())
        for banned in ("secrets", "tokens", "credential values", "raw prompts", "full patch bodies"):
            self.assertIn(banned, normalized, banned)

    def test_never_defines_a_decision_path_of_its_own(self) -> None:
        # The doc legitimately *names* REVIEW CLEAN / CHANGES REQUIRED once,
        # to state it never changes them (§2) — it must never go further and
        # define a mapping to/from them.
        self.assertNotIn("Decision:", self.text)
        self.assertNotIn("REVIEW INCOMPLETE", self.text)


class ValidatorVocabularyMatchesModelDocTests(unittest.TestCase):
    """The single machine-checkable mirror of the taxonomy must not drift
    from the design record that defines it."""

    def setUp(self) -> None:
        import sys

        sys.path.insert(0, str(REPO_ROOT / "scripts" / "security"))
        import validate_threat_model as vtm  # noqa: E402

        self.vtm = vtm
        self.doc_text = MODEL_DOC.read_text(encoding="utf-8")

    def test_every_provisional_class_is_named_in_the_model_doc(self) -> None:
        for event in self.vtm.PROVISIONAL_EVENT_CLASSES:
            if event == self.vtm.NOT_APPLICABLE:
                continue
            self.assertIn(event, self.doc_text, event)

    def test_review_action_events_are_registered_in_the_validator(self) -> None:
        for event in REVIEW_ACTION_EVENTS:
            self.assertIn(event, self.vtm.PROVISIONAL_EVENT_CLASSES, event)


class PolicyWiringTests(unittest.TestCase):
    """Every packaged policy that denies a capability must actually report
    the right event names, not just this design record describing them."""

    def test_mutation_authority_reports_its_five_events(self) -> None:
        text = MUTATION_AUTHORITY.read_text(encoding="utf-8")
        for event in MUTATION_EVENTS:
            self.assertIn(event, text, event)
        self.assertIn("classification", text)
        self.assertIn("#299", text)

    def test_agent_delegation_reports_its_five_events(self) -> None:
        text = AGENT_DELEGATION.read_text(encoding="utf-8")
        for event in DELEGATION_EVENTS:
            self.assertIn(event, text, event)
        self.assertIn("classification", text)
        self.assertIn("#299", text)

    def test_runtime_validation_reports_the_unavailable_primitive_event(self) -> None:
        text = RUNTIME_VALIDATION.read_text(encoding="utf-8")
        self.assertIn("DENIED_SANDBOX_UNAVAILABLE_PRIMITIVE", text)
        self.assertIn("#299", text)

    def test_review_action_authorization_reports_its_three_events(self) -> None:
        text = REVIEW_ACTION_AUTH.read_text(encoding="utf-8")
        for event in REVIEW_ACTION_EVENTS:
            self.assertIn(event, text, event)
        self.assertIn("classification", text)
        self.assertIn("#299", text)

    def test_no_packaged_policy_links_the_non_packaged_doc(self) -> None:
        """Citation must be by name (prose), never a Markdown link, per the
        packaged/non-packaged boundary (scripts/skill_metadata/expectations.py)."""
        for path in (MUTATION_AUTHORITY, AGENT_DELEGATION, RUNTIME_VALIDATION, REVIEW_ACTION_AUTH):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(
                "](../../docs/security-events",
                text,
                f"{path}: must cite docs/security-events by name, not a Markdown link",
            )
            self.assertNotIn(
                "](../../../docs/security-events",
                text,
                f"{path}: must cite docs/security-events by name, not a Markdown link",
            )


if __name__ == "__main__":
    unittest.main()
