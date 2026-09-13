#!/usr/bin/env python3
"""Observability applicability gate and metrics-are-not-universal semantics.

Contract: shared/policies/failure-retry-recovery.md, "Observability is
applicability-gated, not universal" and the surrounding metrics guidance —
extracted from review-scope.md (Issue #264); see
test_existing_behavior_and_failure_retry_ownership.py for the rest of that
policy's behavior and test_review_scope_core_wiring.py for the
reachability/routing checks that span every extracted pass.
Prose checks only — there is deliberately no second implementation of the
rules (see policies/skill-development-policy.md, "Runbook Design").
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT
from tests.support.policy_docs import extract_section as _section
from tests.support.policy_docs import load_normalized_text as _text

FAILURE_RETRY_RECOVERY = REPO_ROOT / "shared/policies/failure-retry-recovery.md"


class ObservabilityApplicabilityGateTests(unittest.TestCase):
    """(shared semantics) observability has an explicit applicability gate;
    frontend/agent/policy changes are not automatically treated like
    backend operational flows."""

    def setUp(self) -> None:
        self.section = _section(
            _text(FAILURE_RETRY_RECOVERY),
            "### Observability is applicability-gated, not universal",
        )

    def test_gate_question_precedes_the_hierarchy(self) -> None:
        gate_index = self.section.index(
            "does this diff introduce or modify a production-operational "
            "failure mode for which detection or diagnosis is materially "
            "relevant"
        )
        hierarchy_index = self.section.index("already uses metrics, counters,")
        self.assertLess(gate_index, hierarchy_index)

    def test_commonly_relevant_examples_are_backend_operational(self) -> None:
        for example in (
            "backend/service runtime behavior",
            "payments or",
            "queues/events/webhooks",
            "external integrations",
            "asynchronous processing",
            "retries/redelivery",
            "background jobs",
        ):
            self.assertIn(example, self.section)

    def test_frontend_is_conditionally_relevant_not_default(self) -> None:
        self.assertIn("Conditionally relevant for frontend/client changes", self.section)
        self.assertIn(
            "Do not turn an ordinary frontend review into a search for "
            "backend-style metrics",
            self.section,
        )

    def test_policy_and_agent_instruction_changes_are_usually_secondary(self) -> None:
        self.assertIn("Usually secondary or not applicable", self.section)
        for example in (
            "agent instructions",
            "prompts",
            "review Skills",
            "policy Markdown",
            "static docs",
            "non-runtime configuration",
        ):
            self.assertIn(example, self.section)

    def test_runtime_agent_behavior_still_escalates_within_that_category(self) -> None:
        self.assertIn("agent orchestration", self.section)
        self.assertIn("tool-invocation failures", self.section)
        self.assertIn("scheduled/background execution", self.section)


class MetricsNotUniversallyRequiredTests(unittest.TestCase):
    """(shared semantics) metrics/alerts are not universally required; logs
    remain valid observability where appropriate; a materially undetectable
    high-impact failure can still be a finding."""

    def setUp(self) -> None:
        self.section = _section(
            _text(FAILURE_RETRY_RECOVERY),
            "## Failure state, retry safety, and recovery",
        )

    def test_established_metrics_check_is_participation_only(self) -> None:
        self.assertIn(
            "check only that the changed or new failure path participates "
            "in that existing mechanism consistently",
            self.section,
        )

    def test_logs_are_a_valid_mechanism_when_that_is_the_convention(self) -> None:
        self.assertIn(
            "If the surrounding code relies primarily on logs, check only "
            "whether the existing logging convention",
            self.section,
        )

    def test_generic_add_more_logs_is_explicitly_rejected(self) -> None:
        self.assertIn('never a generic "add more logs" recommendation', self.section)

    def test_undetectable_high_impact_failure_can_still_be_a_finding(self) -> None:
        self.assertIn(
            "a missing signal is a finding only when the diff introduces "
            "or materially changes a high-impact failure mode that would "
            "otherwise be effectively undiagnosable",
            self.section,
        )
        self.assertIn(
            "the concern is that the failure is undetectable, not merely "
            "that a particular metric is absent",
            self.section,
        )


if __name__ == "__main__":
    unittest.main()
