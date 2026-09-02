#!/usr/bin/env python3
"""Test-only reference model for shared runtime-validation.md.

It uses fake processes and repositories. Not runtime logic, not packaged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from tests.reference import decision_semantics as decisions


class Outcome(Enum):
    EXECUTED = "executed"
    SKIPPED = "skipped"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ExecutionBoundary:
    """Minimum disposable boundary required before untrusted payload runs."""

    available: bool = True
    filesystem_isolated: bool = True
    host_credentials_isolated: bool = True
    network_isolated: bool = True
    git_github_isolated: bool = True
    privilege_isolated: bool = True
    resource_bounded: bool = True
    disposable: bool = True
    post_run_verified: bool = True

    @property
    def established(self) -> bool:
        return all(
            (
                self.filesystem_isolated,
                self.host_credentials_isolated,
                self.network_isolated,
                self.git_github_isolated,
                self.privilege_isolated,
                self.resource_bounded,
                self.disposable,
                self.post_run_verified,
            )
        )


@dataclass(frozen=True)
class CommandDeclaration:
    """One exact command declaration supplied by an existing target source."""

    argv: tuple[str, ...]
    source: str = "AGENTS.md: validation"
    scope: str = "focused"
    relevant: bool = True
    trusted: bool = True
    justification: str = ""
    unsafe_reason: str = ""
    requires_secret: bool = False
    requires_service: bool = False
    requires_network: bool = False
    interactive: bool = False
    writes_target: bool = False
    available: bool = True
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    payload_untrusted: bool = True
    boundary: ExecutionBoundary = field(default_factory=ExecutionBoundary)

    @property
    def rendered(self) -> str:
        return " ".join(self.argv)


@dataclass(frozen=True)
class ValidationRecord:
    command: str
    source: str
    scope: str
    outcome: Outcome
    reason: str = ""
    exit_code: int | None = None
    evidence: str = ""


@dataclass
class FakeRepository:
    """A repository/process double whose state makes mutation observable."""

    files: dict[str, str] = field(default_factory=lambda: {"src/app.py": "value = 1\n"})
    host_sentinel: str = ""
    host_secret: str = ""
    unrelated_files: dict[str, str] = field(default_factory=dict)
    process_invocations: list[tuple[str, ...]] = field(default_factory=list)
    boundary_invocations: list[ExecutionBoundary] = field(default_factory=list)
    git_writes: int = 0
    github_writes: int = 0
    host_accesses: int = 0
    network_attempts: int = 0

    def snapshot(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self.files.items()))

    def start(self, argv: tuple[str, ...], boundary: ExecutionBoundary) -> None:
        """Record a sandboxed fake process start; no host access exists."""
        if not boundary.established:
            raise AssertionError("fake runner must not start outside the boundary")
        self.process_invocations.append(argv)
        self.boundary_invocations.append(boundary)


def _selected(declarations: Sequence[CommandDeclaration]) -> CommandDeclaration | None:
    relevant = [item for item in declarations if item.relevant]
    focused = [item for item in relevant if item.scope == "focused"]
    if focused:
        return focused[0]
    broader = [item for item in relevant if item.scope == "broader"]
    return broader[0] if broader else None


def _record_skip(command: CommandDeclaration, reason: str) -> ValidationRecord:
    return ValidationRecord(command.rendered, command.source, command.scope, Outcome.SKIPPED, reason=reason)


def run_validation(
    declarations: Sequence[CommandDeclaration], repository: FakeRepository
) -> tuple[ValidationRecord, ...]:
    """Select one narrowest command and produce one explicit outcome record."""
    if not declarations:
        return (
            ValidationRecord(
                "<none>", "target repository instructions", "none", Outcome.SKIPPED,
                reason="no declared command",
            ),
        )

    command = _selected(declarations)
    if command is None:
        return (
            ValidationRecord(
                "<none relevant>", "target repository instructions", "none", Outcome.SKIPPED,
                reason="no relevant declared command",
            ),
        )
    if not command.trusted:
        return (_record_skip(command, "command is not trustworthily declared"),)
    if not command.payload_untrusted:
        return (_record_skip(command, "execution payload trust cannot be assumed"),)
    if command.scope == "broader" and not command.justification:
        return (_record_skip(command, "broader command lacks blast-radius justification"),)
    if command.unsafe_reason:
        return (_record_skip(command, command.unsafe_reason),)
    if command.requires_secret:
        return (_record_skip(command, "requires a secret or credential"),)
    if command.requires_service:
        return (_record_skip(command, "requires an unavailable service"),)
    if command.requires_network:
        return (_record_skip(command, "requires network or external state"),)
    if command.interactive:
        return (_record_skip(command, "requires interactive input"),)
    if command.writes_target:
        return (_record_skip(command, "may mutate the target repository"),)
    if not command.available:
        return (
            ValidationRecord(
                command.rendered, command.source, command.scope, Outcome.UNAVAILABLE,
                reason="required executable or local capability is unavailable",
            ),
        )
    if not command.boundary.available:
        return (
            ValidationRecord(
                command.rendered,
                command.source,
                command.scope,
                Outcome.UNAVAILABLE,
                reason="safe execution boundary is unavailable",
            ),
        )
    if not command.boundary.established:
        return (_record_skip(command, "required execution boundary cannot be verified"),)

    repository.start(command.argv, command.boundary)
    outcome = Outcome.EXECUTED if command.exit_code == 0 else Outcome.FAILED
    return (
        ValidationRecord(
            command.rendered, command.source, command.scope, outcome,
            exit_code=command.exit_code,
            evidence=command.stdout if outcome is Outcome.EXECUTED else command.stderr,
        ),
    )


def apply_validation_to_review(
    findings: Sequence[decisions.Finding], records: Sequence[ValidationRecord]
) -> tuple[tuple[decisions.Finding, ...], decisions.Decision]:
    """Validation evidence cannot erase findings or create a second decision."""
    del records  # Records are evidence; the caller separately adds failures.
    retained = tuple(findings)
    return retained, decisions.derive_decision(retained)


def failure_finding(
    record: ValidationRecord, impact: decisions.Severity
) -> decisions.Finding:
    """Map a failed command to a finding whose severity is supplied by impact."""
    if record.outcome is not Outcome.FAILED:
        raise ValueError("only failed validation produces validation finding material")
    return decisions.Finding("validation-failure", impact, origin="validation")
