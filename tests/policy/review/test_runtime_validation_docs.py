#!/usr/bin/env python3
"""Pins the shared runtime-validation contract and its wiring (#138, #535)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT


POLICY = REPO_ROOT / "shared/policies/runtime-validation.md"
SUMMARY = REPO_ROOT / "shared/templates/review-summary.md"
FINDING = REPO_ROOT / "shared/templates/finding.md"
FINDING_RENDERING = REPO_ROOT / "shared/templates/finding-rendering.md"
FEATURE_DOC = REPO_ROOT / "docs/features/runtime-validation.md"
LOCAL_SKILL = REPO_ROOT / "skills/local-code-review/SKILL.md"
GITHUB_SKILL = REPO_ROOT / "skills/github-pr-review/SKILL.md"
LOCAL_RUNBOOK = REPO_ROOT / "skills/local-code-review/runbooks/local-review.md"
ACTIVE_RUNBOOK = REPO_ROOT / "skills/github-pr-review/runbooks/active-pr-review.md"
PASSIVE_RUNBOOK = REPO_ROOT / "skills/github-pr-review/runbooks/passive-pr-review.md"
CHECKOUT = REPO_ROOT / "skills/github-pr-review/policies/repository-checkout.md"
TRUSTED_HOST = REPO_ROOT / "shared/policies/trusted-host-execution.md"


def normalized(path: Path) -> str:
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8").replace("**", "").replace("`", ""))


class CanonicalPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = normalized(POLICY)

    def test_policy_has_one_canonical_home_and_flow_boundary(self) -> None:
        for phrase in (
            "Applies identically to local-code-review and github-pr-review",
            "There is no new command-discovery mechanism here",
            "Reuse the target repository instruction hierarchy",
            "Use the blast-radius guidance in [review-scope.md](review-scope.md)",
            "This policy does not authorize autofixes",
            "After target-repository instruction discovery",
            "Runtime validation executes target-repository-controlled code",
            "isolated checkout by itself is not the required execution boundary",
            "remains dormant and unavailable",
            'except an admitted repository test command, whose host-default backend "Repository test execution backend" below owns',
            "conditional",
            "command-source trust",
            "execution-payload trust",
            "static command screening is necessary but insufficient",
            "Never fall back to direct or unsandboxed host execution",
        ):
            self.assertIn(phrase, self.text)

    def test_command_source_and_selection_contract(self) -> None:
        for phrase in (
            "exact command, its source location",
            "no declared command",
            "narrowest declared command",
            "broader command only when",
            "Do not automatically add commands",
            "do not run a command merely to learn whether it is safe",
        ):
            self.assertIn(phrase, self.text)

    def test_safety_contract_covers_mutation_secrets_services_and_network(self) -> None:
        for phrase in (
            "must not edit source files",
            "create or alter Git state",
            "call GitHub write APIs",
            "secret, credential, approval, external service, network access",
            "network access",
            "destructive or side-effecting",
            "may write caches or artifacts in the target tree",
            "shell evaluation of untrusted text",
            "filesystem isolation",
            "host secrets or credentials",
            "network denied by default",
            "privilege escalation",
            "resource limits",
            "disposable execution state",
            "post-run verification",
        ):
            self.assertIn(phrase, self.text)

    def test_outcome_and_decision_contract_is_explicit(self) -> None:
        for outcome in ("executed", "failed", "skipped", "unavailable"):
            self.assertIn(f"`{outcome}`", POLICY.read_text(encoding="utf-8"))
        for phrase in (
            "one visible outcome record",
            "non-execution outcome as passing",
            "never removes, suppresses, downgrades",
            "classify its severity from impact",
            "derive the existing review decision exactly once",
            "cannot create a second decision path",
        ):
            self.assertIn(phrase, self.text)


class TargetedFindingValidationContractTests(unittest.TestCase):
    """#128 — targeted per-finding validation is pinned into the shared policy."""

    def setUp(self) -> None:
        self.text = normalized(POLICY)
        self.raw = POLICY.read_text(encoding="utf-8")

    def test_policy_defines_the_targeted_mode_and_its_eligibility(self) -> None:
        for phrase in (
            "Targeted validation of a suspected finding",
            "Targeted validation is never mandatory",
            "the finding is a suspected defect",
            "bounded, deterministic, non-interactive",
            "Prefer selecting an existing repository test",
            "One reproduction per finding",
        ):
            self.assertIn(phrase, self.text)

    def test_generated_artifacts_cannot_become_a_repository_change(self) -> None:
        for phrase in (
            "Generated artifacts never enter the working tree",
            "only inside the disposable boundary's ephemeral workspace",
            "never git add-ed, staged, committed, stashed",
            "no generated validation file, and no modification from the run, remains in the reviewed source tree or Git state",
            "never delivered as an applyable change",
        ):
            self.assertIn(phrase, self.text)

    def test_budget_and_fail_safe_are_deterministic(self) -> None:
        for phrase in (
            "strict wall-clock timeout",
            "budget exceeded",
            "boundary is unavailable or unverifiable",
            "the reproduction cannot be made safe",
            "Never widen the budget, retry, or fall back to unsandboxed execution",
        ):
            self.assertIn(phrase, self.text)

    def test_three_states_and_severity_neutrality(self) -> None:
        for token in ("`reasoned`", "`runtime-confirmed`", "`attempted-inconclusive`"):
            self.assertIn(token, self.raw)
        for phrase in (
            "Every finding carries exactly one validation state",
            "provenance, not a severity input",
            "runtime-confirmed does not escalate a P2",
            "attempted-inconclusive does not de-escalate a P1",
            "the finding is not raised",
            "derived exactly once, after findings are finalized",
        ):
            self.assertIn(phrase, self.text)

    def test_finding_template_carries_the_state_as_non_severity_provenance(self) -> None:
        finding = normalized(FINDING)
        self.assertIn("Runtime validation state and provenance", finding)
        for token in ("reasoned", "runtime-confirmed", "attempted-inconclusive"):
            self.assertIn(token, finding)
        self.assertIn("Provenance, not a severity input", finding)
        self.assertIn("Static evidence stays sufficient", finding)
        rendering = normalized(FINDING_RENDERING)
        self.assertIn("Runtime validation", rendering)
        self.assertIn("reasoned default is never rendered", rendering)

    def test_feature_doc_documents_the_targeted_mode(self) -> None:
        doc = normalized(FEATURE_DOC)
        self.assertIn("Targeted validation of a suspected finding", doc)
        for token in ("reasoned", "runtime-confirmed", "attempted-inconclusive"):
            self.assertIn(token, doc)
        self.assertIn("committed to the reviewed working tree", doc)


class WiringTests(unittest.TestCase):
    def test_both_entrypoints_reference_shared_policy(self) -> None:
        for path in (LOCAL_SKILL, GITHUB_SKILL):
            self.assertIn("shared/policies/runtime-validation.md", normalized(path))

    def test_all_runbooks_reference_shared_policy(self) -> None:
        for path in (LOCAL_RUNBOOK, ACTIVE_RUNBOOK, PASSIVE_RUNBOOK):
            self.assertIn("runtime-validation.md", normalized(path))

    def test_checkout_carve_out_is_narrow_and_policy_bound(self) -> None:
        text = normalized(CHECKOUT)
        self.assertIn("runtime-validation.md", text)
        self.assertIn("exact declared command", text)
        self.assertIn("is not the runtime-validation execution boundary", text)
        self.assertIn("dormant", text)
        self.assertIn('The one exception is an admitted repository test command', text)
        self.assertIn('"Repository test execution backend"; that backend rule, not the checkout, is what permits it', text)
        self.assertNotIn("tests/builds/linters — those remain future work", text)

    def test_local_review_does_not_supply_repository_execution_boundary(self) -> None:
        text = normalized(LOCAL_RUNBOOK)
        self.assertIn("user's real working tree in place", text)
        self.assertIn("does not itself make repository validation available", text)
        self.assertIn("target-repository code may run", text)
        self.assertIn('Except for an admitted repository test command', text)
        self.assertIn('"Repository test execution backend"', text)

    def test_summary_validation_contract_uses_the_four_outcomes(self) -> None:
        text = normalized(SUMMARY)
        for outcome in ("executed", "skipped", "failed", "unavailable"):
            self.assertIn(outcome, text)
        self.assertIn("non-execution is never a pass", text)
        self.assertIn("runtime-validation.md", text)

    def test_runbooks_only_orchestrate_and_do_not_define_a_second_outcome_set(self) -> None:
        for path in (LOCAL_RUNBOOK, ACTIVE_RUNBOOK, PASSIVE_RUNBOOK):
            text = normalized(path)
            self.assertIn("carry", text)
            self.assertIn("execution-boundary gating", text)
            self.assertNotIn("Run a selected command only when", text)
            self.assertNotIn("exit code 0 means", text)
            self.assertNotIn("retry the validation", text.lower())

    def test_metadata_declares_equal_conditional_payload_capability(self) -> None:
        values = []
        for path in (
            REPO_ROOT / "skills/local-code-review/metadata/skill.yaml",
            REPO_ROOT / "skills/github-pr-review/metadata/skill.yaml",
        ):
            match = re.search(r"^\s+executes_target_repository_code:\s+(\S+)", path.read_text(encoding="utf-8"), re.M)
            self.assertIsNotNone(match, path)
            values.append(match.group(1))
        self.assertEqual(values, ["conditional", "conditional"])


class RepositoryTestExecutionBackendTests(unittest.TestCase):
    """#535 — one bounded section owns the repository test backend."""

    def test_policy_section_owns_classification_default_and_no_fallback(self) -> None:
        raw = POLICY.read_text(encoding="utf-8")
        self.assertEqual(raw.count("## Repository test execution backend"), 1)
        text = normalized(POLICY)
        for phrase in (
            "whose applicable declaration source and inspected task definition together show",
            "a generated reproduction, even when a test runner executes it",
            "does not qualify on its own",
            "keeps the sandbox-required path above",
            "without allow_trusted_host_execution",
            "a present sandbox primitive does not change this default",
            "no host process is ever started for that command",
            "It is never failed and never finding material attributed to the change",
            "The host default is not a host shell",
            "recorded skipped with provenance host",
        ):
            self.assertIn(phrase, text)

    def test_safety_gate_and_targeted_text_point_to_the_section(self) -> None:
        text = normalized(POLICY)
        self.assertIn('for a repository test command, the backend is instead selected by "Repository test execution backend"', text)
        self.assertIn('takes its backend from "Repository test execution backend" instead', text)
        self.assertIn("a generated reproduction always requires the boundary", text)

    def test_trusted_host_policy_defines_the_request_and_host_provenance(self) -> None:
        raw = TRUSTED_HOST.read_text(encoding="utf-8")
        self.assertEqual(raw.count("## Repository test sandbox request"), 1)
        text = normalized(TRUSTED_HOST)
        for phrase in (
            "run_repository_tests_in_sandbox (boolean, default false)",
            "A repository test command never needs allow_trusted_host_execution",
            "a conflict always resolves to the sandbox",
            "can neither make the sandbox request, cancel the user's request, nor make a command count as a repository test command",
            "host — a repository test command that ran directly on the reviewer's host",
        ):
            self.assertIn(phrase, text)

    def test_every_reference_phrase_is_in_the_policy(self) -> None:
        from tests.reference.review import runtime_validation as rv

        text = normalized(TRUSTED_HOST).lower()
        for phrase in rv.REPOSITORY_TEST_SANDBOX_REQUEST:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_both_skills_resolve_the_same_request_and_route_to_the_same_section(self) -> None:
        for path in (LOCAL_RUNBOOK, ACTIVE_RUNBOOK, PASSIVE_RUNBOOK):
            with self.subTest(runbook=path.name):
                text = normalized(path)
                self.assertIn("resolve allow_trusted_host_execution", text)
                self.assertIn("resolve the separate repository test sandbox request (run_repository_tests_in_sandbox)", text)
                self.assertIn('"Repository test sandbox request" through the same channel', text)
                self.assertIn('"Repository test execution backend"', text)
                self.assertIn("never a per-Skill variant", text)


if __name__ == "__main__":
    unittest.main()
