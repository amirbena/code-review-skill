#!/usr/bin/env python3
"""Test-only reference model for shared runtime-validation.md.

It uses fake processes and repositories. Not runtime logic, not packaged.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from tests.reference.review import decision_semantics as decisions


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
    """A process double that makes boundary admission observable.

    The model does not simulate a host sandbox. Boundary fields are admission
    controls, and a started process records the verified boundary only.
    """

    files: dict[str, str] = field(default_factory=lambda: {"src/app.py": "value = 1\n"})
    process_invocations: list[tuple[str, ...]] = field(default_factory=list)
    boundary_invocations: list[ExecutionBoundary] = field(default_factory=list)

    def snapshot(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self.files.items()))

    def start(self, argv: tuple[str, ...], boundary: ExecutionBoundary) -> None:
        """Record a sandboxed fake process start; no host access exists."""
        if not boundary.established:
            raise AssertionError("fake runner must not start outside the boundary")
        self.process_invocations.append(argv)
        self.boundary_invocations.append(boundary)

    def run_reproduction(
        self, reproduction: TargetedReproduction, boundary: ExecutionBoundary
    ) -> None:
        """Run a targeted reproduction inside the boundary's ephemeral workspace.

        A correct runner never touches ``files``; ``leaks`` models a buggy
        runner that writes the generated artifact into the reviewed tree so the
        caller's post-run verification has something to catch.
        """
        if not boundary.established:
            raise AssertionError("fake runner must not start outside the boundary")
        self.process_invocations.append(("<targeted-reproduction>", reproduction.kind))
        self.boundary_invocations.append(boundary)
        if reproduction.leaks:
            self.files["tests/_generated_repro.py"] = "def test_repro():\n    assert False\n"

    def restore(self, snapshot: tuple[tuple[str, str], ...]) -> None:
        """Discard everything the run left behind; recover the reviewed tree."""
        self.files = dict(snapshot)


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
    """Keep validation evidence separate from finding/decision derivation."""
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


# --------------------------------------------------------------------------- #
# Targeted validation of a suspected finding (#128)
#
# A second, narrower mode of the same policy: run the smallest safe, isolated
# reproduction of ONE suspected finding to gain runtime evidence for it. It
# reuses ExecutionBoundary / FakeRepository above; nothing here relaxes the
# trust model. Every finding ends with exactly one ValidationState.
# --------------------------------------------------------------------------- #


class ValidationState(Enum):
    """The finding-facing classification carried by every finding."""

    REASONED = "reasoned"
    RUNTIME_CONFIRMED = "runtime-confirmed"
    ATTEMPTED_INCONCLUSIVE = "attempted-inconclusive"


@dataclass(frozen=True)
class TargetedReproduction:
    """The smallest reproduction of one suspected finding."""

    kind: str = "generated"  # "selected" existing repo test, or "generated"
    deterministic: bool = True
    non_interactive: bool = True
    # eligibility: needs nothing the isolated boundary lacks
    needs_unavailable_capability: bool = False
    # discovered while preparing the run: cannot be made side-effect free
    safe: bool = True
    # simulated run behaviour
    defect_present: bool = True  # ground truth the fake run reflects
    times_out: bool = False
    ambiguous: bool = False  # ran but neither confirms nor disproves
    leaks: bool = False  # a buggy runner that writes the generated file into the tree


@dataclass(frozen=True)
class SuspectedFinding:
    """A finding still being formed, before the set is finalized."""

    id: str
    severity: decisions.Severity
    hinges_on_runtime: bool = True  # static reasoning left it genuinely uncertain
    already_confident: bool = False  # already established without a run => ineligible
    reproduction: TargetedReproduction | None = None
    boundary: ExecutionBoundary = field(default_factory=ExecutionBoundary)
    budget_seconds: float = 30.0
    run_seconds: float = 1.0


@dataclass(frozen=True)
class TargetedValidationResult:
    finding_id: str
    state: ValidationState
    raised: bool  # False => suspicion disproved, no finding is raised
    attempted: bool  # False => ineligible, nothing ran, no Validation entry
    outcome: Outcome | None = None  # the Validation-section outcome when attempted
    reason: str = ""
    evidence: str = ""


def _reproduction_run(
    finding: SuspectedFinding, repository: FakeRepository
) -> TargetedValidationResult:
    repro = finding.reproduction
    assert repro is not None
    before = repository.snapshot()
    repository.run_reproduction(repro, finding.boundary)

    if repository.snapshot() != before:
        # A generated artifact / mutation reached the tree: discard and recover.
        repository.restore(before)
        return TargetedValidationResult(
            finding.id, ValidationState.ATTEMPTED_INCONCLUSIVE, raised=True,
            attempted=True, outcome=Outcome.SKIPPED,
            reason="generated-artifact leak check failed; result discarded",
        )
    if repro.ambiguous:
        return TargetedValidationResult(
            finding.id, ValidationState.ATTEMPTED_INCONCLUSIVE, raised=True,
            attempted=True, outcome=Outcome.FAILED,
            reason="reproduction ran but neither confirmed nor disproved",
        )
    if repro.defect_present:
        return TargetedValidationResult(
            finding.id, ValidationState.RUNTIME_CONFIRMED, raised=True,
            attempted=True, outcome=Outcome.EXECUTED,
            evidence="isolated reproduction failed exactly as the finding predicts",
        )
    return TargetedValidationResult(
        finding.id, ValidationState.REASONED, raised=False,
        attempted=True, outcome=Outcome.EXECUTED,
        evidence="isolated reproduction passed; suspected defect disproved",
    )


def run_targeted_validation(
    finding: SuspectedFinding, repository: FakeRepository
) -> TargetedValidationResult:
    """Attempt the smallest safe reproduction for one suspected finding."""
    repro = finding.reproduction
    if (
        repro is None
        or finding.already_confident
        or not finding.hinges_on_runtime
        or repro.needs_unavailable_capability
        or not repro.deterministic
        or not repro.non_interactive
    ):
        return TargetedValidationResult(
            finding.id, ValidationState.REASONED, raised=True, attempted=False,
            reason="ineligible for targeted validation; static evidence stands",
        )

    if not finding.boundary.available or not finding.boundary.established:
        return TargetedValidationResult(
            finding.id, ValidationState.ATTEMPTED_INCONCLUSIVE, raised=True,
            attempted=True, outcome=Outcome.UNAVAILABLE,
            reason="isolated execution boundary unavailable or unverifiable",
        )
    if not repro.safe:
        return TargetedValidationResult(
            finding.id, ValidationState.ATTEMPTED_INCONCLUSIVE, raised=True,
            attempted=True, outcome=Outcome.SKIPPED,
            reason="reproduction cannot be made safe",
        )
    if repro.times_out or finding.run_seconds > finding.budget_seconds:
        # Terminate; never widen the budget or retry.
        return TargetedValidationResult(
            finding.id, ValidationState.ATTEMPTED_INCONCLUSIVE, raised=True,
            attempted=True, outcome=Outcome.SKIPPED, reason="budget exceeded",
        )
    return _reproduction_run(finding, repository)


def finalized_finding(
    finding: SuspectedFinding, result: TargetedValidationResult
) -> decisions.Finding | None:
    """Project a validated suspicion onto the canonical decision Finding.

    The validation state is provenance only: it never appears in, and never
    changes, the severity the decision derivation consumes.
    """
    if not result.raised:
        return None
    return decisions.Finding(finding.id, finding.severity, origin="diff")
