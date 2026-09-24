#!/usr/bin/env python3
"""Test-only reference model for shared runtime-validation.md.

It uses fake processes and repositories. Not runtime logic, not packaged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Sequence

from tests.reference.review import decision_semantics as decisions
from tests.reference.review.invocation_options import _phrase_regex


class Outcome(Enum):
    EXECUTED = "executed"
    SKIPPED = "skipped"
    FAILED = "failed"
    UNAVAILABLE = "unavailable"


class Provenance(Enum):
    """Which execution backend (if any) ran the command.

    Mirrors shared/policies/trusted-host-execution.md. SANDBOX is the
    disposable isolation boundary; TRUSTED_HOST is the explicit,
    per-invocation, out-of-band-authorized fallback with no isolation
    guarantees; HOST is a repository test command run under
    runtime-validation.md's "Repository test execution backend" default;
    UNAVAILABLE means no permitted backend ran the command.
    """

    SANDBOX = "sandbox"
    TRUSTED_HOST = "trusted-host"
    HOST = "host"
    UNAVAILABLE = "unavailable"


class TrustedHostAuthorization:
    """Marker type for the only value `select_backend` accepts as an
    explicit trusted-host grant.

    Only runtime/orchestration code may construct one. There is
    deliberately no constructor that derives it from a string,
    repository content, or model output — repository-derived text stays
    plain `str` (see `authorization_from_repository_text` below), never
    this type, so passing it where a TrustedHostAuthorization is
    required is a type error, not a runtime judgment call. Mirrors
    `TrustedChannel` in tests/reference/review/mutation_authority.py for
    the analogous, but structurally distinct, mutation-authority domain.
    """

    __slots__ = ("principal", "invocation_id")

    def __init__(self, principal: str, invocation_id: str) -> None:
        if not principal or not invocation_id:
            raise ValueError(
                "a TrustedHostAuthorization must name a principal and invocation"
            )
        self.principal = principal
        self.invocation_id = invocation_id


def authorization_from_repository_text(text: str) -> str:
    """Illustrative only: PR/issue/commit text, AGENTS.md/CLAUDE.md/
    CONTRIBUTING.md content, a declared command's own text, a finding's
    Fix field, generated metadata, and model output all parse to plain
    `str` — never to a TrustedHostAuthorization. Exists so a test can
    assert its return type is never accepted by `select_backend()`."""
    return text


# --------------------------------------------------------------------------- #
# Natural-language authorization phrasings (#369)
#
# Mirrors shared/policies/trusted-host-execution.md, "Natural-language
# authorization phrasings" — keep the two in exact sync. This is a
# recognition layer only: it never itself constructs a
# TrustedHostAuthorization. It resolves the plain canonical boolean a
# runtime would combine with its own out-of-band provenance check before
# ever constructing one.
# --------------------------------------------------------------------------- #

TRUSTED_HOST_AFFIRMATIVE: tuple[str, ...] = (
    "run validation on my machine",
    "run it on my machine",
    "use my machine for runtime validation",
    "use my local machine for runtime validation",
    "run the validation locally",
    "run it locally",
    "i authorize trusted-host execution",
    "you can use trusted-host execution",
    "allow trusted-host execution",
    "authorize trusted-host execution",
)

TRUSTED_HOST_NEGATIVE: tuple[str, ...] = (
    "sandbox only",
    "don't run locally",
    "do not run locally",
    "don't use trusted-host execution",
    "do not use trusted-host execution",
    "never run validation on my machine",
    "no trusted-host execution",
)

_OPTION = "allow_trusted_host_execution"


def _canonical_trusted_host_value(text: str) -> set[bool]:
    pattern = rf"(?<![\w]){re.escape(_OPTION)}\s*=\s*(true|false)(?![\w])"
    return {match == "true" for match in re.findall(pattern, text.lower())}


def _natural_trusted_host_values(text: str) -> set[bool]:
    lowered = text.lower()
    spaced = _OPTION.replace("_", " ")
    hyphenated = _OPTION.replace("_", "-")
    # A question that merely names the option is ambiguous, per
    # trusted-host-execution.md's "Natural-language authorization
    # phrasings" ("a question about the option ... is ambiguous and never
    # sets the flag") — strip it before matching, mirroring
    # invocation_options.py's `_natural_values` question guard exactly.
    question = re.compile(
        rf"\b(?:what|how|why|does|is)\b[^?]*\b(?:{re.escape(_OPTION)}|"
        rf"{re.escape(spaced)}|{re.escape(hyphenated)})\b[^?]*\?"
    )
    lowered = question.sub("", lowered)
    bare = (
        rf"(?<![\w]){re.escape(_OPTION)}(?![\w=])",
        rf"(?<![\w]){re.escape(spaced)}(?![\w])",
        rf"(?<![\w]){re.escape(hyphenated)}(?![\w])",
    )
    affirmative = bare + tuple(_phrase_regex(p) for p in TRUSTED_HOST_AFFIRMATIVE)
    negative = tuple(_phrase_regex(p) for p in TRUSTED_HOST_NEGATIVE)
    values: set[bool] = set()
    if any(re.search(p, lowered) for p in negative):
        values.add(False)
    if any(re.search(p, lowered) for p in affirmative):
        values.add(True)
    return values


def resolve_allow_trusted_host_execution(
    text: str, *, structured: bool | None = None
) -> bool:
    """Resolve the one canonical `allow_trusted_host_execution` boolean.

    Precedence (trusted-host-execution.md, "Resolution precedence"):
    an explicit structured value always wins; absent one, one unambiguous
    natural-language value (affirmative or negative) resolves it;
    otherwise the default `false`. Conflicting natural-language phrasing
    (both an affirmative and a negative phrase present) falls through
    toward denial, never toward `true` — this option's fall-through and
    its default both land on `false`, unlike invocation-options.md's other
    options, whose Skill default may be `true`.
    """
    if structured is not None:
        return structured
    canonical = _canonical_trusted_host_value(text)
    if False in canonical:
        return False
    if True in canonical:
        return True
    natural = _natural_trusted_host_values(text)
    if len(natural) == 1:
        return natural.pop()
    return False


# --------------------------------------------------------------------------- #
# Repository test sandbox request (#535)
#
# Mirrors shared/policies/trusted-host-execution.md, "Repository test sandbox
# request" — keep the phrase list in exact sync. A separate value from
# allow_trusted_host_execution: neither sets nor cancels the other.
# --------------------------------------------------------------------------- #

SKILLS: tuple[str, str] = ("local-code-review", "github-pr-review")

REPOSITORY_TEST_SANDBOX_REQUEST: tuple[str, ...] = (
    "run tests in sandbox",
    "run tests in a sandbox",
    "run the tests in sandbox",
    "run the tests in a sandbox",
    "run repository tests in a sandbox",
    "sandbox the tests",
    "run tests sandboxed",
    "don't run tests on my machine",
    "do not run tests on my machine",
    "don't run tests on the host",
    "do not run tests on the host",
)

_SANDBOX_OPTION = "run_repository_tests_in_sandbox"
_NEGATED_PREFIX = r"(?<!don't\s)(?<!do\snot\s)(?<!never\s)"


class RepositoryTestSandboxRequest:
    """Marker type for the only value that selects sandbox-only execution of
    a repository test command. Like TrustedHostAuthorization, only
    runtime/orchestration code constructs one; repository-derived text
    stays plain `str` and is ignored."""

    __slots__ = ("principal", "invocation_id")

    def __init__(self, principal: str, invocation_id: str) -> None:
        if not principal or not invocation_id:
            raise ValueError(
                "a RepositoryTestSandboxRequest must name a principal and invocation"
            )
        self.principal = principal
        self.invocation_id = invocation_id


def _natural_sandbox_request(text: str) -> bool:
    lowered = text.lower()
    spaced = _SANDBOX_OPTION.replace("_", " ")
    hyphenated = _SANDBOX_OPTION.replace("_", "-")
    # A question about the sandbox is ambiguous, mirroring the
    # trusted-host question guard above; a polite request still counts.
    question = re.compile(r"\b(?:what|how|why|does|is|should)\b[^?]*sandbox[^?]*\?")
    lowered = question.sub("", lowered)
    bare = (
        rf"(?<![\w]){re.escape(_SANDBOX_OPTION)}(?![\w=])",
        rf"(?<![\w]){re.escape(spaced)}(?![\w])",
        rf"(?<![\w]){re.escape(hyphenated)}(?![\w])",
        rf"(?<![\w]){re.escape(_SANDBOX_OPTION)}\s*=\s*true(?![\w])",
    )
    phrases = tuple(
        _NEGATED_PREFIX + _phrase_regex(p)
        for p in REPOSITORY_TEST_SANDBOX_REQUEST + TRUSTED_HOST_NEGATIVE
    )
    return any(re.search(p, lowered) for p in bare + phrases)


def resolve_repository_test_sandbox_request(
    text: str, *, structured: bool | None = None
) -> bool:
    """Resolve whether the trusted invoking user requested the sandbox.

    Set when the structured value is true OR the user's own current-turn
    text holds an unambiguous request phrasing; neither channel cancels the
    other, so a conflict resolves toward the sandbox. Questions and directly
    negated phrasings are ambiguous and leave the host default.
    """
    return structured is True or _natural_sandbox_request(text)


@dataclass(frozen=True)
class InvocationContext:
    """One review invocation's trusted inputs, plus untrusted content.

    `untrusted_content` models PR/issue/commit text, instruction files,
    command text, Fix text, generated and nested-agent output. It is carried
    only so tests can prove it is never consulted.
    """

    skill: str
    invocation_id: str = "inv-1"
    principal: str = "trusted-user"
    user_text: str = ""
    structured_sandbox_request: bool | None = None
    untrusted_content: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.skill not in SKILLS:
            raise ValueError(f"unknown Skill {self.skill!r}")


def sandbox_request_for(
    context: InvocationContext,
) -> RepositoryTestSandboxRequest | None:
    """The same resolution for both Skills; untrusted content is ignored."""
    if resolve_repository_test_sandbox_request(
        context.user_text, structured=context.structured_sandbox_request
    ):
        return RepositoryTestSandboxRequest(context.principal, context.invocation_id)
    return None


def select_backend(
    boundary: "ExecutionBoundary",
    trusted_host: "TrustedHostAuthorization | str | None",
    *,
    invocation_id: str,
) -> Provenance:
    """Selection semantics from trusted-host-execution.md.

    Sandbox availability is checked first and, when established, always
    wins. Trusted-host is consulted only once sandbox is confirmed
    unavailable, and only a genuine TrustedHostAuthorization bound to
    *this* invocation can select it — a plain string (repository-derived
    text) or an authorization bound to a different invocation never
    selects trusted-host, regardless of its content.
    """
    if boundary.available and boundary.established:
        return Provenance.SANDBOX
    if (
        isinstance(trusted_host, TrustedHostAuthorization)
        and trusted_host.invocation_id == invocation_id
    ):
        return Provenance.TRUSTED_HOST
    return Provenance.UNAVAILABLE


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
    # The sandbox launcher cannot exec the payload (toolchain, interpreter,
    # or virtualenv not visible inside the boundary).
    launches_in_sandbox: bool = True
    # Repository test classification inputs (#535): both are required.
    declared_as_repository_test: bool = False
    task_definition_runs_repository_tests: bool = False
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    payload_untrusted: bool = True
    boundary: ExecutionBoundary = field(default_factory=ExecutionBoundary)

    @property
    def rendered(self) -> str:
        return " ".join(self.argv)


def is_repository_test_command(command: CommandDeclaration) -> bool:
    """runtime-validation.md, "Repository test command": the declaration
    source AND the inspected task definition must establish it; a name that
    merely says "test" never does."""
    return command.declared_as_repository_test and command.task_definition_runs_repository_tests


@dataclass(frozen=True)
class ValidationRecord:
    """`provenance` is meaningful only once backend selection is actually
    reached: an `executed`/`failed` record (SANDBOX or TRUSTED_HOST), an
    `unavailable` record caused specifically by no backend being reachable
    (UNAVAILABLE), or a `skipped` record produced *after* a selected
    backend already started the command and its result was then discarded
    (carries that backend's provenance — see `run_validation`'s
    post-run mutation-discard branch). Every other record — a `skipped`
    recorded before backend selection, or an `unavailable` from an
    unrelated cause such as a missing executable — never reached backend
    selection, so `provenance` stays `None`: absent, not `UNAVAILABLE`,
    which is reserved for the backend-caused case (shared/policies/
    trusted-host-execution.md, "Provenance and evidence")."""

    command: str
    source: str
    scope: str
    outcome: Outcome
    reason: str = ""
    exit_code: int | None = None
    evidence: str = ""
    provenance: Provenance | None = None


@dataclass
class FakeRepository:
    """A process double that makes boundary admission observable.

    The model does not simulate a host sandbox. Boundary fields are admission
    controls, and a started process records the verified boundary only.
    """

    files: dict[str, str] = field(default_factory=lambda: {"src/app.py": "value = 1\n"})
    process_invocations: list[tuple[str, ...]] = field(default_factory=list)
    boundary_invocations: list[ExecutionBoundary] = field(default_factory=list)
    host_invocations: list[tuple[str, ...]] = field(default_factory=list)
    # Simulates a payload that writes into the reviewed tree when it runs.
    payload_mutates: bool = False

    def snapshot(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self.files.items()))

    def start(self, argv: tuple[str, ...], boundary: ExecutionBoundary) -> None:
        """Record a sandboxed fake process start; no host access exists."""
        if not boundary.established:
            raise AssertionError("fake runner must not start outside the boundary")
        self.process_invocations.append(argv)
        self.boundary_invocations.append(boundary)

    def start_trusted_host(self, argv: tuple[str, ...]) -> None:
        """Record a trusted-host fake process start.

        No ExecutionBoundary is asserted here — trusted-host mode has no
        isolation boundary by construction (shared/policies/
        trusted-host-execution.md, "What trusted-host execution does not
        provide"). Only the caller's post-run mutation check (see
        `run_validation`) stands in for the sandbox's `post_run_verified`
        guarantee.
        """
        self.process_invocations.append(argv)
        self.host_invocations.append(argv)
        if self.payload_mutates:
            self.files["src/app.py"] = "value = 2\n"

    def start_host(self, argv: tuple[str, ...]) -> None:
        """Record a default-host repository test start; same exposure as
        trusted-host, no grant required."""
        self.start_trusted_host(argv)

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

    def run_reproduction_on_host(self, reproduction: TargetedReproduction) -> None:
        """Run a selected existing repository test on the host (#535)."""
        argv = ("<targeted-reproduction>", reproduction.kind)
        self.process_invocations.append(argv)
        self.host_invocations.append(argv)
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


def _sandbox_requested(
    request: "RepositoryTestSandboxRequest | str | None", invocation_id: str
) -> bool:
    return (
        isinstance(request, RepositoryTestSandboxRequest)
        and request.invocation_id == invocation_id
    )


def _record(
    command: CommandDeclaration, outcome: Outcome, reason: str,
    provenance: Provenance | None = None,
) -> ValidationRecord:
    return ValidationRecord(
        command.rendered, command.source, command.scope, outcome,
        reason=reason, provenance=provenance,
    )


def _completed(command: CommandDeclaration, backend: Provenance) -> ValidationRecord:
    outcome = Outcome.EXECUTED if command.exit_code == 0 else Outcome.FAILED
    return ValidationRecord(
        command.rendered, command.source, command.scope, outcome,
        exit_code=command.exit_code,
        evidence=command.stdout if outcome is Outcome.EXECUTED else command.stderr,
        provenance=backend,
    )


_LAUNCH_FAILURE = "sandbox could not launch the command's executable or toolchain; not executed"


def _run_repository_test(
    command: CommandDeclaration,
    repository: FakeRepository,
    sandbox_request: "RepositoryTestSandboxRequest | str | None",
    invocation_id: str,
) -> ValidationRecord:
    """runtime-validation.md, "Repository test execution backend"."""
    if not _sandbox_requested(sandbox_request, invocation_id):
        before = repository.snapshot()
        repository.start_host(command.argv)
        if repository.snapshot() != before:
            repository.restore(before)
            return _record(
                command, Outcome.SKIPPED,
                "post-run verification found an unexpected mutation; result discarded",
                Provenance.HOST,
            )
        return _completed(command, Provenance.HOST)

    # Explicit sandbox request: never a host process, whatever happens.
    if not command.boundary.available:
        return _record(
            command, Outcome.UNAVAILABLE,
            "sandbox requested but the execution boundary is unavailable; not run on host",
            Provenance.UNAVAILABLE,
        )
    if not command.boundary.established:
        return _record(
            command, Outcome.SKIPPED,
            "sandbox requested but the execution boundary cannot be verified; not run on host",
        )
    if not command.launches_in_sandbox:
        return _record(command, Outcome.UNAVAILABLE, _LAUNCH_FAILURE)
    repository.start(command.argv, command.boundary)
    return _completed(command, Provenance.SANDBOX)


def run_validation(
    declarations: Sequence[CommandDeclaration],
    repository: FakeRepository,
    *,
    trusted_host: "TrustedHostAuthorization | str | None" = None,
    invocation_id: str = "",
    sandbox_request: "RepositoryTestSandboxRequest | str | None" = None,
) -> tuple[ValidationRecord, ...]:
    """Select one narrowest command and produce one explicit outcome record.

    `trusted_host` defaults to `None`: with no argument, behavior is
    byte-for-byte identical to before this backend existed — sandbox
    unavailable still means `unavailable`, never an implicit fallback.
    A repository test command instead takes its backend from
    `_run_repository_test`; `trusted_host` never affects it, and
    `sandbox_request` never affects any other command.
    """
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

    if is_repository_test_command(command):
        return (_run_repository_test(command, repository, sandbox_request, invocation_id),)

    backend = select_backend(command.boundary, trusted_host, invocation_id=invocation_id)

    if backend is Provenance.UNAVAILABLE:
        if not command.boundary.available:
            return (
                ValidationRecord(
                    command.rendered, command.source, command.scope, Outcome.UNAVAILABLE,
                    reason="safe execution boundary is unavailable",
                    provenance=Provenance.UNAVAILABLE,
                ),
            )
        # Boundary is present but unverified, and no valid trusted-host
        # authorization was supplied for this invocation: unchanged
        # pre-existing behavior — SKIPPED, never an implicit host fallback.
        return (_record_skip(command, "required execution boundary cannot be verified"),)

    if backend is Provenance.SANDBOX:
        if not command.launches_in_sandbox:
            return (_record(command, Outcome.UNAVAILABLE, _LAUNCH_FAILURE),)
        repository.start(command.argv, command.boundary)
    else:
        before = repository.snapshot()
        repository.start_trusted_host(command.argv)
        if repository.snapshot() != before:
            repository.restore(before)
            return (
                ValidationRecord(
                    command.rendered, command.source, command.scope, Outcome.SKIPPED,
                    reason="post-run verification found an unexpected mutation; result discarded",
                    provenance=Provenance.TRUSTED_HOST,
                ),
            )

    return (_completed(command, backend),)


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
    launches_in_sandbox: bool = True  # sandbox can exec the test toolchain


@dataclass(frozen=True)
class SuspectedFinding:
    """A finding still being formed, before the set is finalized."""

    id: str
    severity: decisions.Severity
    hinges_on_runtime: bool = True  # static reasoning left it genuinely uncertain
    already_confident: bool = False  # already established without a run => ineligible
    reproduction: TargetedReproduction | None = None
    # A "selected" existing test run through a repository test command (#535).
    repository_test_command: bool = False
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
    provenance: Provenance | None = None


def _reproduction_run(
    finding: SuspectedFinding, repository: FakeRepository, backend: Provenance
) -> TargetedValidationResult:
    repro = finding.reproduction
    assert repro is not None
    before = repository.snapshot()
    if backend is Provenance.HOST:
        repository.run_reproduction_on_host(repro)
    else:
        repository.run_reproduction(repro, finding.boundary)
    result = _classify_reproduction(finding, repository, before)
    return replace(result, provenance=backend)


def _classify_reproduction(
    finding: SuspectedFinding,
    repository: FakeRepository,
    before: tuple[tuple[str, str], ...],
) -> TargetedValidationResult:
    repro = finding.reproduction
    assert repro is not None

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
            evidence="reproduction failed exactly as the finding predicts",
        )
    return TargetedValidationResult(
        finding.id, ValidationState.REASONED, raised=False,
        attempted=True, outcome=Outcome.EXECUTED,
        evidence="reproduction passed; suspected defect disproved",
    )


def _targeted_backend(
    finding: SuspectedFinding,
    sandbox_request: "RepositoryTestSandboxRequest | str | None",
    invocation_id: str,
) -> Provenance:
    repro = finding.reproduction
    assert repro is not None
    host_default = (
        repro.kind == "selected"
        and finding.repository_test_command
        and not _sandbox_requested(sandbox_request, invocation_id)
    )
    return Provenance.HOST if host_default else Provenance.SANDBOX


def run_targeted_validation(
    finding: SuspectedFinding,
    repository: FakeRepository,
    *,
    sandbox_request: "RepositoryTestSandboxRequest | str | None" = None,
    invocation_id: str = "",
) -> TargetedValidationResult:
    """Attempt the smallest safe reproduction for one suspected finding.

    A generated reproduction always requires the boundary; a selected
    existing test run through a repository test command runs on the host
    unless the sandbox was requested, and then never falls back.
    """
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

    backend = _targeted_backend(finding, sandbox_request, invocation_id)
    if backend is Provenance.SANDBOX:
        if not finding.boundary.available or not finding.boundary.established:
            return TargetedValidationResult(
                finding.id, ValidationState.ATTEMPTED_INCONCLUSIVE, raised=True,
                attempted=True, outcome=Outcome.UNAVAILABLE,
                reason="isolated execution boundary unavailable or unverifiable",
            )
        if not repro.launches_in_sandbox:
            return TargetedValidationResult(
                finding.id, ValidationState.ATTEMPTED_INCONCLUSIVE, raised=True,
                attempted=True, outcome=Outcome.UNAVAILABLE, reason=_LAUNCH_FAILURE,
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
    return _reproduction_run(finding, repository, backend)


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
