#!/usr/bin/env python3
"""Fixture matrix for shared runtime-validation.md (#138)."""

from __future__ import annotations

from dataclasses import replace
import unittest

from tests.reference import runtime_validation as rv
from tests.reference.decision_semantics import Decision, Finding, Severity, derive_decision


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


if __name__ == "__main__":
    unittest.main()
