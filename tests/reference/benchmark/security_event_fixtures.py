#!/usr/bin/env python3
"""Test-only reference fixtures for the denied-capability security-event
benchmark corpus (Issue #308, depends on #299:
docs/security-events/security-event-model.md, and the relevant enforced
denial from #301/#302/#303, plus the pre-existing GitHub
review-action-authorization boundary for the GitHub-domain cases -- see
AUTH-014's own catalog entry).

Unlike the mutation-boundary (#305) and delegation-spawn (#307) corpora,
this benchmark is not about *whether* a capability boundary denies an
attempt -- that allow/deny correctness is already proven by
`mutation_fixtures.py` and `delegation_fixtures.py` (and, for the
sandbox, the real adversarial suite
`tests/integration/sandbox/test_adversarial_containment.py`). #308 is one
layer up: given that a denial already occurred, does the emitted #299
`SecurityEvent` carry the right `event_type`/`classification`, the right
correlation fields, and nothing it must never carry -- deterministically,
and without perturbing findings/severity/verdict.

Like `delegation_fixtures.py`, this has no representation in the
`benchmark-case/v1` schema (docs/benchmark/fixture-format.md): that
schema's `expected` block is findings/decision-shaped and has no field
for an event schema, a classification, or a redaction assertion. This
module follows the same test-only, hand-authored, data-driven fixture
pattern documented in
docs/benchmark/corpus/security-events/README.md.

Every case's denial classification and event-type vocabulary is drawn
from -- never re-derived independently of -- the single reference model
already owning its domain's denial:

* `mutation_fixtures.py` / `tests.reference.review.mutation_authority`
  (source/Git mutation, one `AUTH-###` case each);
* `tests.reference.review.agent_delegation` (spawn/delegation, imported
  here directly for its `DENIED_SPAWN_*`/`DENIED_DELEGATION_*` constants,
  mirrored by `delegation_fixtures.py`'s `DELEG-###` cases);
* GitHub formal review-action mutation
  (`skills/github-pr-review/policies/review-action-authorization.md`);
* the sandbox domain has no Python reference model -- #302's boundary is
  real subprocess/container/Seatbelt isolation -- so its cases construct
  the `SecurityEvent` a real `DENIED_SANDBOX_*`/`DENIED_GIT_*` denial
  reports directly from the `SBOX-###` scenario's own declared
  `expected_security_event`, exactly as
  `docs/benchmark/corpus/sandbox-adversarial/README.md` already
  identifies each real adversarial test method as one case.

This module defines no capability boundary, grants no capability, and
changes no finding, severity, or decision (docs/security-events/
security-event-model.md, "Non-weakening invariant"). It also reuses --
never redefines -- the closed `event_type` vocabulary and the
`expected_denial` / `boundary_violation_attempt` classification #299
already fixes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Callable, Optional

from tests.reference.review import agent_delegation as ad

# ---------------------------------------------------------------------------
# The closed #299 event-type vocabulary (docs/security-events/
# security-event-model.md, section 5). Reused verbatim -- this module
# never adds, renames, or splits an entry. Kept as one flat closed set
# (rather than importing scripts/security/validate_threat_model.py's
# PROVISIONAL_EVENT_CLASSES) so this benchmark corpus has no import-time
# dependency on a repository-governance script; the two sets are asserted
# equal by tests/unit/benchmark/test_security_event_corpus.py so they
# cannot silently drift apart.
# ---------------------------------------------------------------------------

DENIED_MUTATION_CAPABILITY_ABSENT = "DENIED_MUTATION_CAPABILITY_ABSENT"
DENIED_MUTATION_UNAUTHORIZED = "DENIED_MUTATION_UNAUTHORIZED"
DENIED_MUTATION_STALE_APPROVAL = "DENIED_MUTATION_STALE_APPROVAL"
DENIED_MUTATION_SCOPE_ESCAPE = "DENIED_MUTATION_SCOPE_ESCAPE"
DENIED_MUTATION_AUTHORIZATION_REPLAY = "DENIED_MUTATION_AUTHORIZATION_REPLAY"

DENIED_SANDBOX_NETWORK_ACCESS = "DENIED_SANDBOX_NETWORK_ACCESS"
DENIED_SANDBOX_CREDENTIAL_ACCESS = "DENIED_SANDBOX_CREDENTIAL_ACCESS"
DENIED_SANDBOX_FILESYSTEM_ACCESS = "DENIED_SANDBOX_FILESYSTEM_ACCESS"
DENIED_SANDBOX_RESOURCE_EXHAUSTION = "DENIED_SANDBOX_RESOURCE_EXHAUSTION"
DENIED_SANDBOX_UNAVAILABLE_PRIMITIVE = "DENIED_SANDBOX_UNAVAILABLE_PRIMITIVE"
DENIED_GIT_UNSAFE_CONFIG = "DENIED_GIT_UNSAFE_CONFIG"
DENIED_GIT_PATH_ESCAPE = "DENIED_GIT_PATH_ESCAPE"

DENIED_SPAWN_UNAUTHORIZED = ad.DENIED_SPAWN_UNAUTHORIZED
DENIED_SPAWN_BUDGET_EXCEEDED = ad.DENIED_SPAWN_BUDGET_EXCEEDED
DENIED_SPAWN_DEPTH_EXCEEDED = ad.DENIED_SPAWN_DEPTH_EXCEEDED
DENIED_DELEGATION_AUTHORITY_ESCALATION = ad.DENIED_DELEGATION_AUTHORITY_ESCALATION
DENIED_DELEGATION_REPLAY = ad.DENIED_DELEGATION_REPLAY

DENIED_REVIEW_ACTION_SELF_REVIEW = "DENIED_REVIEW_ACTION_SELF_REVIEW"
DENIED_REVIEW_ACTION_UNAUTHORIZED = "DENIED_REVIEW_ACTION_UNAUTHORIZED"
DENIED_REVIEW_ACTION_STALE_HEAD = "DENIED_REVIEW_ACTION_STALE_HEAD"

NOT_APPLICABLE = "NOT_APPLICABLE"

CLOSED_EVENT_TYPES: "frozenset[str]" = frozenset(
    {
        DENIED_MUTATION_CAPABILITY_ABSENT,
        DENIED_MUTATION_UNAUTHORIZED,
        DENIED_MUTATION_STALE_APPROVAL,
        DENIED_MUTATION_SCOPE_ESCAPE,
        DENIED_MUTATION_AUTHORIZATION_REPLAY,
        DENIED_SANDBOX_NETWORK_ACCESS,
        DENIED_SANDBOX_CREDENTIAL_ACCESS,
        DENIED_SANDBOX_FILESYSTEM_ACCESS,
        DENIED_SANDBOX_RESOURCE_EXHAUSTION,
        DENIED_SANDBOX_UNAVAILABLE_PRIMITIVE,
        DENIED_GIT_UNSAFE_CONFIG,
        DENIED_GIT_PATH_ESCAPE,
        DENIED_SPAWN_UNAUTHORIZED,
        DENIED_SPAWN_BUDGET_EXCEEDED,
        DENIED_SPAWN_DEPTH_EXCEEDED,
        DENIED_DELEGATION_AUTHORITY_ESCALATION,
        DENIED_DELEGATION_REPLAY,
        DENIED_REVIEW_ACTION_SELF_REVIEW,
        DENIED_REVIEW_ACTION_UNAUTHORIZED,
        DENIED_REVIEW_ACTION_STALE_HEAD,
        NOT_APPLICABLE,
    }
)

CLASSIFICATION_EXPECTED_DENIAL = "expected_denial"
CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT = "boundary_violation_attempt"
VALID_CLASSIFICATIONS: "frozenset[str]" = frozenset(
    {CLASSIFICATION_EXPECTED_DENIAL, CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT}
)

# The enforcement-family boundary names #299 section 3's `boundary` field
# draws from -- the policy that raised the denial, not the event type.
BOUNDARY_MUTATION_AUTHORITY = "mutation-authority.md"
BOUNDARY_RUNTIME_VALIDATION = "runtime-validation.md"
BOUNDARY_AGENT_DELEGATION = "agent-delegation.md"
BOUNDARY_REVIEW_ACTION_AUTHORIZATION = "review-action-authorization.md"

# Every enforcement family the issue's "Scope" section names. A case's
# `family` field must be one of these; corpus completeness requires at
# least one case per family (test_security_event_corpus.py).
FAMILY_MUTATION_CAPABILITY_MISSING = "mutation_capability_missing"
FAMILY_MUTATION_STALE_PATCH = "mutation_stale_patch"
FAMILY_MUTATION_SCOPE_MISMATCH = "mutation_scope_mismatch"
FAMILY_COMMIT_OR_PUSH_AUTHORIZATION_MISSING = "commit_or_push_authorization_missing"
FAMILY_SANDBOX_DENIAL = "sandbox_network_filesystem_credential_denial"
FAMILY_SANDBOX_UNAVAILABLE = "sandbox_unavailable_boundary"
FAMILY_GITHUB_MUTATION_WITHOUT_CAPABILITY = "github_formal_review_mutation_without_capability"
FAMILY_STALE_HEAD_REPLAY_SCOPE_MISMATCH = "stale_head_authorization_replay_scope_mismatch"
FAMILY_SPAWN_CAPABILITY_ABSENT = "spawn_capability_absent"
FAMILY_SPAWN_COUNT_OR_DEPTH_EXCEEDED = "spawn_count_or_depth_exceeded"
FAMILY_DELEGATED_CAPABILITY_ESCALATION = "delegated_capability_escalation"
FAMILY_INHERITED_FORWARDED_AUTHORIZATION = "inherited_forwarded_authorization_across_agent_boundary"

REQUIRED_FAMILIES: "frozenset[str]" = frozenset(
    {
        FAMILY_MUTATION_CAPABILITY_MISSING,
        FAMILY_MUTATION_STALE_PATCH,
        FAMILY_MUTATION_SCOPE_MISMATCH,
        FAMILY_COMMIT_OR_PUSH_AUTHORIZATION_MISSING,
        FAMILY_SANDBOX_DENIAL,
        FAMILY_SANDBOX_UNAVAILABLE,
        FAMILY_GITHUB_MUTATION_WITHOUT_CAPABILITY,
        FAMILY_STALE_HEAD_REPLAY_SCOPE_MISMATCH,
        FAMILY_SPAWN_CAPABILITY_ABSENT,
        FAMILY_SPAWN_COUNT_OR_DEPTH_EXCEEDED,
        FAMILY_DELEGATED_CAPABILITY_ESCALATION,
        FAMILY_INHERITED_FORWARDED_AUTHORIZATION,
    }
)

_THREAT_ID_RE = re.compile(r"^(AUTH|SBOX|DELEG)-\d{3}$")

# Field values a redacted event must never carry -- per #299 section 3,
# "What an event must never record". This is a defensive pattern check
# over every string field's *value*, not a schema restriction (the
# SecurityEvent dataclass below simply has no field to hold a secret,
# token, or patch body in the first place -- redaction here is primarily
# structural, by construction). The pattern check exists so a
# deliberately-broken fixture (MalformedFixtureRejectionTests) can prove
# the check actually fires.
_FORBIDDEN_CONTENT_RE = re.compile(
    r"(ghp_|sk-|BEGIN [A-Z ]*PRIVATE KEY|password\s*[:=]|token\s*[:=]|secret\s*[:=])",
    re.IGNORECASE,
)
_MAX_FIELD_LENGTH = 200  # a label, never a dumped payload or patch body


class SecurityEventFixtureError(ValueError):
    """A security-event benchmark fixture, or a constructed event, is malformed."""


@dataclass(frozen=True)
class SecurityEvent:
    """One denied-capability security event, field-for-field mirroring
    docs/security-events/security-event-model.md section 3. A field is
    `None` when not applicable to this domain -- never inferred or
    padded (section 3's own rule). There is deliberately no field for a
    secret, token, credential value, repository file content, raw
    prompt, or full patch body: redaction is structural, not a filter
    applied after the fact.
    """

    event_type: str
    classification: str
    invocation_id: str
    denial_reason: str
    boundary: str
    timestamp: str
    sequence_position: int
    parent_agent_id: Optional[str] = None
    child_agent_id: Optional[str] = None
    repository: Optional[str] = None
    pr_identity: Optional[str] = None
    reviewed_head: Optional[str] = None
    working_tree_base: Optional[str] = None
    approved_patch_digest: Optional[str] = None
    expected_scope_identifier: Optional[str] = None
    requested_capability: Optional[str] = None
    requested_delegation: Optional[str] = None


@dataclass(frozen=True)
class ReviewOutcome:
    """A minimal stand-in for "findings/severity/verdict" (#308's
    acceptance criterion: recording a security event must never change
    these). Deliberately just enough shape to prove non-interference --
    this is not a review-finding model and duplicates none of
    shared/templates/finding-template.md."""

    findings: "tuple[str, ...]"
    severity_summary: str
    verdict: str


def record_event(
    outcome: ReviewOutcome, event: Optional[SecurityEvent], *, recording_enabled: bool
) -> ReviewOutcome:
    """The only function in this module that touches both a
    `ReviewOutcome` and a `SecurityEvent`. Recording is strictly
    observational (security-event-model.md section 2): this always
    returns `outcome` unchanged, whether or not recording is enabled and
    whether or not an event was produced. `event` is accepted (not
    ignored via a leading underscore) precisely so a future
    implementation cannot quietly start branching on it -- the reference
    contract is that the parameter is inert.
    """
    del event, recording_enabled  # never inspected: recording cannot feed back into outcome
    return replace(outcome)


@dataclass(frozen=True)
class SecurityEventCase:
    """One benchmark case. `build` is a zero-argument callable
    constructing the `SecurityEvent` a real denial in this family
    reports, composing with the single reference model that owns the
    underlying capability-boundary decision; every other field is
    declarative metadata validated independently of execution.
    """

    case_id: str
    family: str
    description: str
    threat_scenario_ids: "tuple[str, ...]"
    # "#301"/"#302"/"#303" for the three #298-epic enforcement owners, or
    # the literal "existing" for the GitHub review-action-authorization
    # boundary -- pre-dates the epic and is owned by neither (AUTH-014,
    # "not part of #301/#305's code-mutation scope").
    enforcement_owner: str
    expected_event_type: str
    expected_classification: str
    requires_parent_child_correlation: bool
    build: "Callable[[], SecurityEvent]"


def validate_event(event: SecurityEvent) -> None:
    """Fail-closed structural validation of a constructed event: closed
    `event_type`, closed `classification`, non-empty universal fields,
    and the redaction content check over every string field's value."""

    if event.event_type not in CLOSED_EVENT_TYPES:
        raise SecurityEventFixtureError(
            f"event_type {event.event_type!r} not in the closed vocabulary {sorted(CLOSED_EVENT_TYPES)}"
        )
    if event.classification not in VALID_CLASSIFICATIONS:
        raise SecurityEventFixtureError(
            f"classification {event.classification!r} not in {sorted(VALID_CLASSIFICATIONS)}"
        )
    for label in ("invocation_id", "denial_reason", "boundary", "timestamp"):
        value = getattr(event, label)
        if not isinstance(value, str) or not value.strip():
            raise SecurityEventFixtureError(f"{label} must be a non-empty string")
    if not isinstance(event.sequence_position, int) or isinstance(event.sequence_position, bool):
        raise SecurityEventFixtureError("sequence_position must be an int")
    if event.sequence_position < 0:
        raise SecurityEventFixtureError("sequence_position must be non-negative")

    for field_name in (
        "denial_reason",
        "boundary",
        "requested_capability",
        "requested_delegation",
        "repository",
        "pr_identity",
        "reviewed_head",
        "working_tree_base",
        "approved_patch_digest",
        "expected_scope_identifier",
        "parent_agent_id",
        "child_agent_id",
    ):
        value = getattr(event, field_name)
        if value is None:
            continue
        if not isinstance(value, str):
            raise SecurityEventFixtureError(f"{field_name} must be a string or None")
        if len(value) > _MAX_FIELD_LENGTH:
            raise SecurityEventFixtureError(
                f"{field_name} exceeds {_MAX_FIELD_LENGTH} chars -- looks like a dumped payload, not a label"
            )
        if _FORBIDDEN_CONTENT_RE.search(value):
            raise SecurityEventFixtureError(
                f"{field_name} value fails the redaction check (looks like a secret/token/credential)"
            )


def validate_case(case: SecurityEventCase) -> None:
    if not isinstance(case.case_id, str) or not case.case_id.strip():
        raise SecurityEventFixtureError("case_id must be a non-empty string")
    if case.family not in REQUIRED_FAMILIES:
        raise SecurityEventFixtureError(f"{case.case_id}: family {case.family!r} not in {sorted(REQUIRED_FAMILIES)}")
    if not isinstance(case.description, str) or not case.description.strip():
        raise SecurityEventFixtureError(f"{case.case_id}: description must be a non-empty string")

    if not isinstance(case.threat_scenario_ids, tuple) or not case.threat_scenario_ids:
        raise SecurityEventFixtureError(f"{case.case_id}: threat_scenario_ids must be a non-empty tuple")
    for tid in case.threat_scenario_ids:
        if not isinstance(tid, str) or not _THREAT_ID_RE.match(tid):
            raise SecurityEventFixtureError(
                f"{case.case_id}: threat_scenario_ids entry {tid!r} must match '<AUTH|SBOX|DELEG>-<3 digits>'"
            )

    if case.enforcement_owner != "existing" and not re.match(r"^#\d+$", case.enforcement_owner):
        raise SecurityEventFixtureError(
            f"{case.case_id}: enforcement_owner must look like '#301' or be the literal 'existing'"
        )

    if case.expected_event_type not in CLOSED_EVENT_TYPES:
        raise SecurityEventFixtureError(
            f"{case.case_id}: expected_event_type {case.expected_event_type!r} not in the closed vocabulary"
        )
    if case.expected_classification not in VALID_CLASSIFICATIONS:
        raise SecurityEventFixtureError(
            f"{case.case_id}: expected_classification {case.expected_classification!r} not in "
            f"{sorted(VALID_CLASSIFICATIONS)}"
        )
    if not callable(case.build):
        raise SecurityEventFixtureError(f"{case.case_id}: build must be callable")


def validate_corpus(cases: "tuple[SecurityEventCase, ...]") -> None:
    if not cases:
        raise SecurityEventFixtureError("corpus must not be empty")
    seen: "set[str]" = set()
    covered_families: "set[str]" = set()
    for case in cases:
        validate_case(case)
        if case.case_id in seen:
            raise SecurityEventFixtureError(f"duplicate case_id {case.case_id!r}")
        seen.add(case.case_id)
        covered_families.add(case.family)
    missing = REQUIRED_FAMILIES - covered_families
    if missing:
        raise SecurityEventFixtureError(f"corpus is missing a case for required family(ies) {sorted(missing)}")


def cases_in_family(family: str) -> "tuple[SecurityEventCase, ...]":
    return tuple(case for case in ALL_CASES if case.family == family)


def cases_for_threat_scenario(threat_id: str) -> "tuple[SecurityEventCase, ...]":
    return tuple(case for case in ALL_CASES if threat_id in case.threat_scenario_ids)


# ---------------------------------------------------------------------------
# A deterministic, monotonically-fixed "invocation" identity shared by
# every non-spawn case below, and a parent/child pair shared by every
# spawn/delegation case -- fixed literal strings, not randomly generated,
# so `build()` is byte-for-byte reproducible across repeated calls (the
# determinism property the issue's acceptance criteria require).
# ---------------------------------------------------------------------------

_INVOCATION_ID = "inv-7f3a9c21"
_PARENT_AGENT_ID = "agent-root-0001"
_CHILD_AGENT_ID = "agent-child-0002"
_TIMESTAMP = "2026-09-15T00:00:00Z"


def _mut_capability_absent() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_MUTATION_CAPABILITY_ABSENT,
        classification=CLASSIFICATION_EXPECTED_DENIAL,
        invocation_id=_INVOCATION_ID,
        denial_reason="no APPLY_PATCH capability granted (default READ_ONLY)",
        boundary=BOUNDARY_MUTATION_AUTHORITY,
        timestamp=_TIMESTAMP,
        sequence_position=0,
        repository="octocat/example",
        working_tree_base="a1b2c3d",
        requested_capability="APPLY_PATCH",
    )


def _mut_stale_approval() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_MUTATION_STALE_APPROVAL,
        classification=CLASSIFICATION_EXPECTED_DENIAL,
        invocation_id=_INVOCATION_ID,
        denial_reason="working-tree base advanced past the approved base",
        boundary=BOUNDARY_MUTATION_AUTHORITY,
        timestamp=_TIMESTAMP,
        sequence_position=0,
        repository="octocat/example",
        working_tree_base="d4e5f6a",
        approved_patch_digest="sha256:deadbeef01",
        requested_capability="APPLY_PATCH",
    )


def _mut_scope_escape() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_MUTATION_SCOPE_ESCAPE,
        classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        invocation_id=_INVOCATION_ID,
        denial_reason="patch touches a path outside the authorized scope",
        boundary=BOUNDARY_MUTATION_AUTHORITY,
        timestamp=_TIMESTAMP,
        sequence_position=1,
        repository="octocat/example",
        expected_scope_identifier="src/widgets/**",
        requested_capability="APPLY_PATCH",
    )


def _mut_commit_reuse() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_MUTATION_UNAUTHORIZED,
        classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        invocation_id=_INVOCATION_ID,
        denial_reason="an APPLY_PATCH authorization does not cover COMMIT",
        boundary=BOUNDARY_MUTATION_AUTHORITY,
        timestamp=_TIMESTAMP,
        sequence_position=1,
        repository="octocat/example",
        requested_capability="COMMIT",
    )


def _mut_push_reuse() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_MUTATION_UNAUTHORIZED,
        classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        invocation_id=_INVOCATION_ID,
        denial_reason="a COMMIT authorization does not cover PUSH",
        boundary=BOUNDARY_MUTATION_AUTHORITY,
        timestamp=_TIMESTAMP,
        sequence_position=1,
        repository="octocat/example",
        requested_capability="PUSH",
    )


def _sandbox_network() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_SANDBOX_NETWORK_ACCESS,
        classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        invocation_id=_INVOCATION_ID,
        denial_reason="outbound HTTP connect denied inside the validation sandbox",
        boundary=BOUNDARY_RUNTIME_VALIDATION,
        timestamp=_TIMESTAMP,
        sequence_position=0,
        requested_capability="runtime_validate",
    )


def _sandbox_credential() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_SANDBOX_CREDENTIAL_ACCESS,
        classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        invocation_id=_INVOCATION_ID,
        denial_reason="read of host credential material denied inside the validation sandbox",
        boundary=BOUNDARY_RUNTIME_VALIDATION,
        timestamp=_TIMESTAMP,
        sequence_position=0,
        requested_capability="runtime_validate",
    )


def _sandbox_filesystem() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_SANDBOX_FILESYSTEM_ACCESS,
        classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        invocation_id=_INVOCATION_ID,
        denial_reason="read outside the bounded work copy denied inside the validation sandbox",
        boundary=BOUNDARY_RUNTIME_VALIDATION,
        timestamp=_TIMESTAMP,
        sequence_position=0,
        requested_capability="runtime_validate",
    )


def _sandbox_unavailable() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_SANDBOX_UNAVAILABLE_PRIMITIVE,
        classification=CLASSIFICATION_EXPECTED_DENIAL,
        invocation_id=_INVOCATION_ID,
        denial_reason="no supported isolation primitive available on this host",
        boundary=BOUNDARY_RUNTIME_VALIDATION,
        timestamp=_TIMESTAMP,
        sequence_position=0,
        requested_capability="runtime_validate",
    )


def _github_unauthorized() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_REVIEW_ACTION_UNAUTHORIZED,
        classification=CLASSIFICATION_EXPECTED_DENIAL,
        invocation_id=_INVOCATION_ID,
        denial_reason="publication mode is not ACTIVE; no formal review-action capability held",
        boundary=BOUNDARY_REVIEW_ACTION_AUTHORIZATION,
        timestamp=_TIMESTAMP,
        sequence_position=0,
        pr_identity="octocat/example#42",
        requested_capability="APPROVE",
    )


def _github_self_review() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_REVIEW_ACTION_SELF_REVIEW,
        classification=CLASSIFICATION_EXPECTED_DENIAL,
        invocation_id=_INVOCATION_ID,
        denial_reason="reviewer shares the PR author's controlling authority",
        boundary=BOUNDARY_REVIEW_ACTION_AUTHORIZATION,
        timestamp=_TIMESTAMP,
        sequence_position=0,
        pr_identity="octocat/example#42",
        requested_capability="APPROVE",
    )


def _github_stale_head() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_REVIEW_ACTION_STALE_HEAD,
        classification=CLASSIFICATION_EXPECTED_DENIAL,
        invocation_id=_INVOCATION_ID,
        denial_reason="PR HEAD advanced past the reviewed HEAD before submission",
        boundary=BOUNDARY_REVIEW_ACTION_AUTHORIZATION,
        timestamp=_TIMESTAMP,
        sequence_position=1,
        pr_identity="octocat/example#42",
        reviewed_head="a1b2c3d",
        requested_capability="APPROVE",
    )


def _mut_authorization_replay() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_MUTATION_AUTHORIZATION_REPLAY,
        classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        invocation_id=_INVOCATION_ID,
        denial_reason="authorization was issued for a different invocation and cannot be replayed",
        boundary=BOUNDARY_MUTATION_AUTHORITY,
        timestamp=_TIMESTAMP,
        sequence_position=1,
        repository="octocat/example",
        requested_capability="APPLY_PATCH",
    )


def _spawn_capability_absent() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_SPAWN_UNAUTHORIZED,
        classification=CLASSIFICATION_EXPECTED_DENIAL,
        invocation_id=_INVOCATION_ID,
        denial_reason="spawn_agent capability absent for this invocation",
        boundary=BOUNDARY_AGENT_DELEGATION,
        timestamp=_TIMESTAMP,
        sequence_position=0,
        parent_agent_id=_PARENT_AGENT_ID,
        requested_capability="spawn_agent",
    )


def _spawn_budget_exceeded() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_SPAWN_BUDGET_EXCEEDED,
        classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        invocation_id=_INVOCATION_ID,
        denial_reason="max_agents_per_invocation already reached",
        boundary=BOUNDARY_AGENT_DELEGATION,
        timestamp=_TIMESTAMP,
        sequence_position=2,
        parent_agent_id=_PARENT_AGENT_ID,
        requested_capability="spawn_agent",
    )


def _spawn_depth_exceeded() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_SPAWN_DEPTH_EXCEEDED,
        classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        invocation_id=_INVOCATION_ID,
        denial_reason="max_spawn_depth already reached",
        boundary=BOUNDARY_AGENT_DELEGATION,
        timestamp=_TIMESTAMP,
        sequence_position=1,
        parent_agent_id=_PARENT_AGENT_ID,
        child_agent_id=_CHILD_AGENT_ID,
        requested_capability="spawn_agent",
    )


def _delegation_escalation() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_DELEGATION_AUTHORITY_ESCALATION,
        classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        invocation_id=_INVOCATION_ID,
        denial_reason="requested capability outside parent_capabilities ∩ explicitly_delegated_capabilities",
        boundary=BOUNDARY_AGENT_DELEGATION,
        timestamp=_TIMESTAMP,
        sequence_position=1,
        parent_agent_id=_PARENT_AGENT_ID,
        child_agent_id=_CHILD_AGENT_ID,
        requested_capability="mutate",
        requested_delegation="analyze",
    )


def _mut_inherited_across_agent_boundary() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_MUTATION_AUTHORIZATION_REPLAY,
        classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        invocation_id=_INVOCATION_ID,
        denial_reason="child presented the parent's mutation authorization",
        boundary=BOUNDARY_MUTATION_AUTHORITY,
        timestamp=_TIMESTAMP,
        sequence_position=1,
        parent_agent_id=_PARENT_AGENT_ID,
        child_agent_id=_CHILD_AGENT_ID,
        repository="octocat/example",
        requested_capability="APPLY_PATCH",
    )


def _delegation_replay() -> SecurityEvent:
    return SecurityEvent(
        event_type=DENIED_DELEGATION_REPLAY,
        classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        invocation_id=_INVOCATION_ID,
        denial_reason="child invoked a capability using its parent's authorization",
        boundary=BOUNDARY_AGENT_DELEGATION,
        timestamp=_TIMESTAMP,
        sequence_position=1,
        parent_agent_id=_PARENT_AGENT_ID,
        child_agent_id=_CHILD_AGENT_ID,
        requested_capability="formal_review_action",
    )


ALL_CASES: "tuple[SecurityEventCase, ...]" = (
    SecurityEventCase(
        case_id="SEC-EVT-001",
        family=FAMILY_MUTATION_CAPABILITY_MISSING,
        description="APPLY_PATCH attempted with no capability granted (default READ_ONLY)",
        threat_scenario_ids=("AUTH-001",),
        enforcement_owner="#301",
        expected_event_type=DENIED_MUTATION_CAPABILITY_ABSENT,
        expected_classification=CLASSIFICATION_EXPECTED_DENIAL,
        requires_parent_child_correlation=False,
        build=_mut_capability_absent,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-002",
        family=FAMILY_MUTATION_STALE_PATCH,
        description="working-tree base advanced past the approved base before APPLY_PATCH",
        threat_scenario_ids=("AUTH-007",),
        enforcement_owner="#301",
        expected_event_type=DENIED_MUTATION_STALE_APPROVAL,
        expected_classification=CLASSIFICATION_EXPECTED_DENIAL,
        requires_parent_child_correlation=False,
        build=_mut_stale_approval,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-003",
        family=FAMILY_MUTATION_SCOPE_MISMATCH,
        description="patch touches a path outside the user-authorized scope",
        threat_scenario_ids=("AUTH-009",),
        enforcement_owner="#301",
        expected_event_type=DENIED_MUTATION_SCOPE_ESCAPE,
        expected_classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        requires_parent_child_correlation=False,
        build=_mut_scope_escape,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-004",
        family=FAMILY_COMMIT_OR_PUSH_AUTHORIZATION_MISSING,
        description="an APPLY_PATCH authorization is reused as COMMIT authorization",
        threat_scenario_ids=("AUTH-010",),
        enforcement_owner="#301",
        expected_event_type=DENIED_MUTATION_UNAUTHORIZED,
        expected_classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        requires_parent_child_correlation=False,
        build=_mut_commit_reuse,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-005",
        family=FAMILY_COMMIT_OR_PUSH_AUTHORIZATION_MISSING,
        description="a COMMIT authorization is reused as PUSH authorization",
        threat_scenario_ids=("AUTH-011",),
        enforcement_owner="#301",
        expected_event_type=DENIED_MUTATION_UNAUTHORIZED,
        expected_classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        requires_parent_child_correlation=False,
        build=_mut_push_reuse,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-006",
        family=FAMILY_SANDBOX_DENIAL,
        description="outbound HTTP connect attempted inside the validation sandbox",
        threat_scenario_ids=("SBOX-001",),
        enforcement_owner="#302",
        expected_event_type=DENIED_SANDBOX_NETWORK_ACCESS,
        expected_classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        requires_parent_child_correlation=False,
        build=_sandbox_network,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-007",
        family=FAMILY_SANDBOX_DENIAL,
        description="host credential material read attempted inside the validation sandbox",
        threat_scenario_ids=("SBOX-004",),
        enforcement_owner="#302",
        expected_event_type=DENIED_SANDBOX_CREDENTIAL_ACCESS,
        expected_classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        requires_parent_child_correlation=False,
        build=_sandbox_credential,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-008",
        family=FAMILY_SANDBOX_DENIAL,
        description="read outside the bounded work copy attempted inside the validation sandbox",
        threat_scenario_ids=("SBOX-005",),
        enforcement_owner="#302",
        expected_event_type=DENIED_SANDBOX_FILESYSTEM_ACCESS,
        expected_classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        requires_parent_child_correlation=False,
        build=_sandbox_filesystem,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-009",
        family=FAMILY_SANDBOX_UNAVAILABLE,
        description="no supported isolation primitive available on this host",
        threat_scenario_ids=("SBOX-012",),
        enforcement_owner="#302",
        expected_event_type=DENIED_SANDBOX_UNAVAILABLE_PRIMITIVE,
        expected_classification=CLASSIFICATION_EXPECTED_DENIAL,
        requires_parent_child_correlation=False,
        build=_sandbox_unavailable,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-010",
        family=FAMILY_GITHUB_MUTATION_WITHOUT_CAPABILITY,
        description="formal APPROVE attempted while publication mode is not ACTIVE",
        threat_scenario_ids=("AUTH-014",),
        enforcement_owner="existing",
        expected_event_type=DENIED_REVIEW_ACTION_UNAUTHORIZED,
        expected_classification=CLASSIFICATION_EXPECTED_DENIAL,
        requires_parent_child_correlation=False,
        build=_github_unauthorized,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-011",
        family=FAMILY_GITHUB_MUTATION_WITHOUT_CAPABILITY,
        description="formal APPROVE withheld because the reviewer is the PR author",
        threat_scenario_ids=("AUTH-014",),
        enforcement_owner="existing",
        expected_event_type=DENIED_REVIEW_ACTION_SELF_REVIEW,
        expected_classification=CLASSIFICATION_EXPECTED_DENIAL,
        requires_parent_child_correlation=False,
        build=_github_self_review,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-012",
        family=FAMILY_STALE_HEAD_REPLAY_SCOPE_MISMATCH,
        description="PR HEAD advanced past the reviewed HEAD before the formal event was submitted",
        threat_scenario_ids=("AUTH-014",),
        enforcement_owner="existing",
        expected_event_type=DENIED_REVIEW_ACTION_STALE_HEAD,
        expected_classification=CLASSIFICATION_EXPECTED_DENIAL,
        requires_parent_child_correlation=False,
        build=_github_stale_head,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-013",
        family=FAMILY_STALE_HEAD_REPLAY_SCOPE_MISMATCH,
        description="a mutation authorization issued for a different invocation is replayed",
        threat_scenario_ids=("AUTH-012",),
        enforcement_owner="#301",
        expected_event_type=DENIED_MUTATION_AUTHORIZATION_REPLAY,
        expected_classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        requires_parent_child_correlation=False,
        build=_mut_authorization_replay,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-014",
        family=FAMILY_SPAWN_CAPABILITY_ABSENT,
        description="an agent without spawn_agent attempts to create a child",
        threat_scenario_ids=("DELEG-001",),
        enforcement_owner="#303",
        expected_event_type=DENIED_SPAWN_UNAUTHORIZED,
        expected_classification=CLASSIFICATION_EXPECTED_DENIAL,
        requires_parent_child_correlation=True,
        build=_spawn_capability_absent,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-015",
        family=FAMILY_SPAWN_COUNT_OR_DEPTH_EXCEEDED,
        description="max_agents_per_invocation is already reached",
        threat_scenario_ids=("DELEG-002",),
        enforcement_owner="#303",
        expected_event_type=DENIED_SPAWN_BUDGET_EXCEEDED,
        expected_classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        requires_parent_child_correlation=True,
        build=_spawn_budget_exceeded,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-016",
        family=FAMILY_SPAWN_COUNT_OR_DEPTH_EXCEEDED,
        description="a child attempts to spawn beyond max_spawn_depth",
        threat_scenario_ids=("DELEG-003",),
        enforcement_owner="#303",
        expected_event_type=DENIED_SPAWN_DEPTH_EXCEEDED,
        expected_classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        requires_parent_child_correlation=True,
        build=_spawn_depth_exceeded,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-017",
        family=FAMILY_DELEGATED_CAPABILITY_ESCALATION,
        description="a child requests a capability outside its explicitly delegated subset",
        threat_scenario_ids=("DELEG-006",),
        enforcement_owner="#303",
        expected_event_type=DENIED_DELEGATION_AUTHORITY_ESCALATION,
        expected_classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        requires_parent_child_correlation=True,
        build=_delegation_escalation,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-018",
        family=FAMILY_INHERITED_FORWARDED_AUTHORIZATION,
        description="a child inherits and presents its parent's mutation authorization",
        threat_scenario_ids=("AUTH-013",),
        enforcement_owner="#303",
        expected_event_type=DENIED_MUTATION_AUTHORIZATION_REPLAY,
        expected_classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        requires_parent_child_correlation=True,
        build=_mut_inherited_across_agent_boundary,
    ),
    SecurityEventCase(
        case_id="SEC-EVT-019",
        family=FAMILY_INHERITED_FORWARDED_AUTHORIZATION,
        description="a child invokes a capability using its parent's delegation authorization",
        threat_scenario_ids=("DELEG-007",),
        enforcement_owner="#303",
        expected_event_type=DENIED_DELEGATION_REPLAY,
        expected_classification=CLASSIFICATION_BOUNDARY_VIOLATION_ATTEMPT,
        requires_parent_child_correlation=True,
        build=_delegation_replay,
    ),
)
