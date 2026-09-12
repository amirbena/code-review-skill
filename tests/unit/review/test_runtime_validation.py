#!/usr/bin/env python3
"""Fixture matrix for shared runtime-validation.md (#138)."""

from __future__ import annotations

from dataclasses import replace
import unittest

from tests.reference.review import runtime_validation as rv
from tests.reference.review.decision_semantics import Decision, Finding, Severity, derive_decision


def command(*argv: str, **kwargs) -> rv.CommandDeclaration:
    return rv.CommandDeclaration(argv=argv, **kwargs)


class RuntimeValidationFixtureMatrix(unittest.TestCase):
    def test_conventional_command_payload_is_untrusted_but_runs_only_in_boundary(self) -> None:
        declaration = command("pytest", "tests/", source="AGENTS.md: validation")
        repo = rv.FakeRepository()
        records = rv.run_validation([declaration], repo)
        self.assertTrue(declaration.payload_untrusted)
        self.assertEqual(records[0].outcome, rv.Outcome.EXECUTED)
        self.assertEqual(len(repo.boundary_invocations), 1)
        self.assertTrue(repo.boundary_invocations[0].established)

    def test_payload_trust_cannot_be_used_as_a_host_execution_bypass(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation(
            [command("pytest", "tests/", payload_untrusted=False)], repo
        )
        self.assertEqual(records[0].outcome, rv.Outcome.SKIPPED)
        self.assertIn("payload trust", records[0].reason)
        self.assertEqual(repo.process_invocations, [])

    def test_missing_execution_boundary_is_unavailable_without_host_fallback(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation(
            [command("pytest", "tests/", boundary=rv.ExecutionBoundary(available=False))], repo
        )
        self.assertEqual(records[0].outcome, rv.Outcome.UNAVAILABLE)
        self.assertIn("boundary", records[0].reason)
        self.assertEqual(repo.process_invocations, [])

    def test_unverified_execution_boundary_is_skipped_without_host_fallback(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation(
            [command("pytest", "tests/", boundary=rv.ExecutionBoundary(post_run_verified=False))], repo
        )
        self.assertEqual(records[0].outcome, rv.Outcome.SKIPPED)
        self.assertIn("cannot be verified", records[0].reason)
        self.assertEqual(repo.process_invocations, [])

    def test_boundary_network_isolation_is_required_even_for_conventional_command(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation(
            [command("pytest", "tests/", boundary=rv.ExecutionBoundary(network_isolated=False))], repo
        )
        self.assertEqual(records[0].outcome, rv.Outcome.SKIPPED)
        self.assertIn("boundary", records[0].reason)
        self.assertEqual(repo.process_invocations, [])

    def test_every_unverified_boundary_property_prevents_process_start(self) -> None:
        properties = (
            "filesystem_isolated",
            "host_credentials_isolated",
            "network_isolated",
            "git_github_isolated",
            "privilege_isolated",
            "resource_bounded",
            "disposable",
            "post_run_verified",
        )
        for property_name in properties:
            with self.subTest(property_name=property_name):
                repo = rv.FakeRepository()
                boundary = replace(rv.ExecutionBoundary(), **{property_name: False})
                records = rv.run_validation([command("pytest", "tests/", boundary=boundary)], repo)
                self.assertEqual(records[0].outcome, rv.Outcome.SKIPPED)
                self.assertIn("boundary", records[0].reason)
                self.assertEqual(repo.process_invocations, [])

    def test_focused_declared_command_passes(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation([command("pytest", "tests/unit/test_app.py", stdout="1 passed")], repo)
        self.assertEqual(records[0].outcome, rv.Outcome.EXECUTED)
        self.assertEqual(records[0].exit_code, 0)
        self.assertEqual(repo.process_invocations, [("pytest", "tests/unit/test_app.py")])

    def test_focused_declared_command_fails(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation(
            [command("pytest", "tests/unit/test_app.py", exit_code=1, stderr="assertion failed")], repo
        )
        self.assertEqual(records[0].outcome, rv.Outcome.FAILED)
        self.assertEqual(records[0].exit_code, 1)
        self.assertEqual(records[0].evidence, "assertion failed")

    def test_justified_broader_command_is_selected_when_no_focused_command_exists(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation(
            [command("make", "test", scope="broader", justification="shared API changed")], repo
        )
        self.assertEqual(records[0].outcome, rv.Outcome.EXECUTED)
        self.assertEqual(records[0].scope, "broader")

    def test_focused_command_wins_over_broader_command(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation(
            [
                command("make", "all", scope="broader", justification="large blast radius"),
                command("pytest", "tests/unit/test_app.py"),
            ],
            repo,
        )
        self.assertEqual(records[0].command, "pytest tests/unit/test_app.py")

    def test_no_declared_command_is_explicitly_skipped(self) -> None:
        records = rv.run_validation([], rv.FakeRepository())
        self.assertEqual(records[0].outcome, rv.Outcome.SKIPPED)
        self.assertEqual(records[0].reason, "no declared command")

    def test_unsafe_destructive_command_is_skipped_without_starting(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation(
            [command("pytest", "--fix", unsafe_reason="autofix/destructive task")], repo
        )
        self.assertEqual(records[0].outcome, rv.Outcome.SKIPPED)
        self.assertIn("autofix", records[0].reason)
        self.assertEqual(repo.process_invocations, [])

    def test_secret_dependent_command_is_skipped(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation([command("make", "integration", requires_secret=True)], repo)
        self.assertEqual(records[0].outcome, rv.Outcome.SKIPPED)
        self.assertIn("secret", records[0].reason)

    def test_service_dependent_command_is_skipped(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation([command("pytest", "tests/e2e", requires_service=True)], repo)
        self.assertEqual(records[0].outcome, rv.Outcome.SKIPPED)
        self.assertIn("service", records[0].reason)

    def test_network_dependent_command_is_skipped(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation([command("curl", "https://example.test", requires_network=True)], repo)
        self.assertEqual(records[0].outcome, rv.Outcome.SKIPPED)
        self.assertIn("network", records[0].reason)

    def test_command_unavailable_is_distinct_from_skipped(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation([command("cargo", "test", available=False)], repo)
        self.assertEqual(records[0].outcome, rv.Outcome.UNAVAILABLE)
        self.assertEqual(repo.process_invocations, [])

    def test_untrusted_declaration_is_not_executed(self) -> None:
        repo = rv.FakeRepository()
        records = rv.run_validation([command("pytest", trusted=False)], repo)
        self.assertEqual(records[0].outcome, rv.Outcome.SKIPPED)
        self.assertIn("trustworthily", records[0].reason)


class RuntimeValidationSafetyAndDecisionTests(unittest.TestCase):
    def test_source_tree_remains_unchanged_on_all_paths(self) -> None:
        declarations = [
            command("pytest", "tests/unit/test_app.py"),
            command("make", "fix", unsafe_reason="format/autofix"),
            command("make", "integration", requires_service=True),
            command("missing-tool", available=False),
        ]
        for declaration in declarations:
            with self.subTest(declaration=declaration.rendered):
                repo = rv.FakeRepository()
                before = repo.snapshot()
                rv.run_validation([declaration], repo)
                self.assertEqual(repo.snapshot(), before)

    def test_validation_evidence_cannot_create_a_second_decision_path(self) -> None:
        findings = (Finding("existing", Severity.P2),)
        records = rv.run_validation(
            [command("pytest", "tests/unit/test_app.py", exit_code=1)], rv.FakeRepository()
        )
        self.assertEqual(records[0].outcome, rv.Outcome.FAILED)
        retained, decision = rv.apply_validation_to_review(
            findings, records
        )
        self.assertEqual(retained, findings)
        self.assertEqual(decision, derive_decision(findings))
        self.assertEqual(decision, Decision.CLEAN)

    def test_failed_validation_is_finding_material_with_impact_derived_severity(self) -> None:
        record = rv.run_validation(
            [command("pytest", "tests/unit/test_app.py", exit_code=1)], rv.FakeRepository()
        )[0]
        finding = rv.failure_finding(record, Severity.P2)
        self.assertEqual(finding.severity, Severity.P2)
        self.assertEqual(derive_decision([finding]), Decision.CLEAN)

    def test_failing_validation_with_blocking_impact_blocks_mechanically(self) -> None:
        record = rv.run_validation(
            [command("pytest", "tests/unit/test_app.py", exit_code=1)], rv.FakeRepository()
        )[0]
        finding = rv.failure_finding(record, Severity.P1)
        self.assertEqual(derive_decision([finding]), Decision.CHANGES_REQUIRED)

    def test_every_record_has_one_canonical_outcome(self) -> None:
        records = [
            rv.run_validation([command("pytest")], rv.FakeRepository())[0],
            rv.run_validation([command("pytest", exit_code=1)], rv.FakeRepository())[0],
            rv.run_validation([command("pytest", unsafe_reason="destructive")], rv.FakeRepository())[0],
            rv.run_validation([command("pytest", available=False)], rv.FakeRepository())[0],
        ]
        self.assertEqual(
            {record.outcome for record in records},
            {rv.Outcome.EXECUTED, rv.Outcome.FAILED, rv.Outcome.SKIPPED, rv.Outcome.UNAVAILABLE},
        )


class TargetedFindingValidationLifecycle(unittest.TestCase):
    """Lifecycle matrix for targeted per-finding validation (#128)."""

    def suspected(self, **kwargs) -> rv.SuspectedFinding:
        kwargs.setdefault("id", "F1")
        kwargs.setdefault("severity", Severity.P1)
        kwargs.setdefault("reproduction", rv.TargetedReproduction())
        return rv.SuspectedFinding(**kwargs)

    def test_runtime_confirmed_when_isolated_reproduction_reproduces_the_defect(self) -> None:
        repo = rv.FakeRepository()
        finding = self.suspected(reproduction=rv.TargetedReproduction(defect_present=True))
        result = rv.run_targeted_validation(finding, repo)
        self.assertEqual(result.state, rv.ValidationState.RUNTIME_CONFIRMED)
        self.assertEqual(result.outcome, rv.Outcome.EXECUTED)
        self.assertTrue(result.raised and result.attempted)
        self.assertTrue(result.evidence)
        self.assertEqual(len(repo.boundary_invocations), 1)

    def test_disproved_suspicion_raises_no_finding_but_records_pass_evidence(self) -> None:
        repo = rv.FakeRepository()
        finding = self.suspected(reproduction=rv.TargetedReproduction(defect_present=False))
        result = rv.run_targeted_validation(finding, repo)
        self.assertFalse(result.raised)
        self.assertEqual(result.state, rv.ValidationState.REASONED)
        self.assertEqual(result.outcome, rv.Outcome.EXECUTED)
        self.assertIn("disproved", result.evidence)
        self.assertIsNone(rv.finalized_finding(finding, result))

    def test_ambiguous_run_is_attempted_inconclusive(self) -> None:
        repo = rv.FakeRepository()
        finding = self.suspected(reproduction=rv.TargetedReproduction(ambiguous=True))
        result = rv.run_targeted_validation(finding, repo)
        self.assertEqual(result.state, rv.ValidationState.ATTEMPTED_INCONCLUSIVE)
        self.assertIn("neither confirmed nor disproved", result.reason)

    def test_timeout_terminates_and_is_attempted_inconclusive_without_retry(self) -> None:
        repo = rv.FakeRepository()
        finding = self.suspected(run_seconds=120.0, budget_seconds=30.0)
        result = rv.run_targeted_validation(finding, repo)
        self.assertEqual(result.state, rv.ValidationState.ATTEMPTED_INCONCLUSIVE)
        self.assertEqual(result.reason, "budget exceeded")
        self.assertEqual(repo.process_invocations, [])

    def test_times_out_flag_is_also_budget_exceeded(self) -> None:
        result = rv.run_targeted_validation(
            self.suspected(reproduction=rv.TargetedReproduction(times_out=True)),
            rv.FakeRepository(),
        )
        self.assertEqual(result.state, rv.ValidationState.ATTEMPTED_INCONCLUSIVE)
        self.assertEqual(result.reason, "budget exceeded")

    def test_unsafe_reproduction_is_attempted_inconclusive_and_never_starts(self) -> None:
        repo = rv.FakeRepository()
        result = rv.run_targeted_validation(
            self.suspected(reproduction=rv.TargetedReproduction(safe=False)), repo
        )
        self.assertEqual(result.state, rv.ValidationState.ATTEMPTED_INCONCLUSIVE)
        self.assertIn("cannot be made safe", result.reason)
        self.assertEqual(result.outcome, rv.Outcome.SKIPPED)
        self.assertEqual(repo.process_invocations, [])

    def test_unavailable_boundary_is_attempted_inconclusive_without_host_fallback(self) -> None:
        repo = rv.FakeRepository()
        for boundary in (
            rv.ExecutionBoundary(available=False),
            rv.ExecutionBoundary(post_run_verified=False),
        ):
            with self.subTest(boundary=boundary):
                result = rv.run_targeted_validation(self.suspected(boundary=boundary), repo)
                self.assertEqual(result.state, rv.ValidationState.ATTEMPTED_INCONCLUSIVE)
                self.assertEqual(result.outcome, rv.Outcome.UNAVAILABLE)
        self.assertEqual(repo.process_invocations, [])

    def test_ineligible_finding_stays_reasoned_and_is_never_attempted(self) -> None:
        repo = rv.FakeRepository()
        for finding in (
            self.suspected(reproduction=None),
            self.suspected(already_confident=True),
            self.suspected(hinges_on_runtime=False),
            self.suspected(reproduction=rv.TargetedReproduction(needs_unavailable_capability=True)),
        ):
            with self.subTest(finding=finding):
                result = rv.run_targeted_validation(finding, repo)
                self.assertEqual(result.state, rv.ValidationState.REASONED)
                self.assertFalse(result.attempted)
                self.assertIsNone(result.outcome)
        self.assertEqual(repo.process_invocations, [])

    def test_generated_artifact_leak_is_caught_discarded_and_marked_inconclusive(self) -> None:
        repo = rv.FakeRepository()
        before = repo.snapshot()
        result = rv.run_targeted_validation(
            self.suspected(reproduction=rv.TargetedReproduction(leaks=True)), repo
        )
        self.assertEqual(result.state, rv.ValidationState.ATTEMPTED_INCONCLUSIVE)
        self.assertIn("leak", result.reason)
        self.assertEqual(repo.snapshot(), before, "reviewed tree must be recovered")

    def test_reviewed_tree_is_unchanged_on_every_targeted_path(self) -> None:
        cases = [
            self.suspected(reproduction=rv.TargetedReproduction(defect_present=True)),
            self.suspected(reproduction=rv.TargetedReproduction(defect_present=False)),
            self.suspected(reproduction=rv.TargetedReproduction(ambiguous=True)),
            self.suspected(reproduction=rv.TargetedReproduction(safe=False)),
            self.suspected(reproduction=rv.TargetedReproduction(leaks=True)),
            self.suspected(boundary=rv.ExecutionBoundary(available=False)),
            self.suspected(run_seconds=999.0),
            self.suspected(reproduction=None),
        ]
        for finding in cases:
            with self.subTest(finding=finding):
                repo = rv.FakeRepository()
                before = repo.snapshot()
                rv.run_targeted_validation(finding, repo)
                self.assertEqual(repo.snapshot(), before)

    def test_every_finding_exposes_exactly_one_of_three_states(self) -> None:
        observed = {
            rv.run_targeted_validation(finding, rv.FakeRepository()).state
            for finding in (
                self.suspected(reproduction=rv.TargetedReproduction(defect_present=True)),
                self.suspected(reproduction=None),
                self.suspected(reproduction=rv.TargetedReproduction(ambiguous=True)),
            )
        }
        self.assertEqual(
            observed,
            {
                rv.ValidationState.RUNTIME_CONFIRMED,
                rv.ValidationState.REASONED,
                rv.ValidationState.ATTEMPTED_INCONCLUSIVE,
            },
        )
        for state in rv.ValidationState:
            self.assertIn(state.value, {"reasoned", "runtime-confirmed", "attempted-inconclusive"})

    def test_validation_state_never_changes_severity_or_decision(self) -> None:
        for state_repro, expected in (
            (rv.TargetedReproduction(defect_present=True), rv.ValidationState.RUNTIME_CONFIRMED),
            (rv.TargetedReproduction(ambiguous=True), rv.ValidationState.ATTEMPTED_INCONCLUSIVE),
        ):
            finding = self.suspected(severity=Severity.P2, reproduction=state_repro)
            result = rv.run_targeted_validation(finding, rv.FakeRepository())
            self.assertEqual(result.state, expected)
            projected = rv.finalized_finding(finding, result)
            self.assertEqual(projected.severity, Severity.P2)
            self.assertEqual(derive_decision([projected]), Decision.CLEAN)

        blocking = self.suspected(
            severity=Severity.P1,
            reproduction=rv.TargetedReproduction(ambiguous=True),
        )
        result = rv.run_targeted_validation(blocking, rv.FakeRepository())
        self.assertEqual(result.state, rv.ValidationState.ATTEMPTED_INCONCLUSIVE)
        projected = rv.finalized_finding(blocking, result)
        self.assertEqual(derive_decision([projected]), Decision.CHANGES_REQUIRED)


if __name__ == "__main__":
    unittest.main()
