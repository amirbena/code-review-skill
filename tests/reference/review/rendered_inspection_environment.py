#!/usr/bin/env python3
"""Test-only reference model for shared/policies/rendered-inspection-environment.md.

Not runtime logic, not packaged. It models the deterministic parts of the
contract: the render-consent gate (closed authorization sources, session
boundary, decline/revoke/unavailable states), the read-only existing-Playwright
check, project configuration read as data, and the rule that nothing is ever
installed, downloaded, or repaired. Nothing here launches a browser or touches
the host.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

OFFER_SENTENCES = (
    "This review includes frontend changes that may benefit from browser-rendered "
    "verification. Would you like me to run Playwright?"
)

AFFIRMATIVE = (
    "yes",
    "yes please",
    "yes, run playwright",
    "run playwright",
    "go ahead",
    "approved",
    "allow rendered inspection",
    "approve rendered verification",
    "allow_rendered_inspection=true",
)
NEGATIVE = (
    "no",
    "no thanks",
    "don't run playwright",
    "do not run playwright",
    "skip rendered verification",
)
REVOCATION = (
    "stop rendering",
    "stop running playwright",
    "revoke rendered inspection",
    "don't render anything else",
    "do not run playwright anymore",
    "allow_rendered_inspection=false",
)

# Signals of the removed browser-install flow: ignored if supplied.
REMOVED_SIGNALS = ("allow_browser_tooling_install", "rendered_inspection_opt_out")
CONSENT_SIGNAL = "allow_rendered_inspection"


class Reply(Enum):
    AFFIRMATIVE = "affirmative"
    NEGATIVE = "negative"
    REVOCATION = "revocation"
    AMBIGUOUS = "ambiguous"


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower()).rstrip(".!")


def classify_reply(text: str) -> Reply:
    """Closed phrase sets, matched case-insensitively and whitespace-flexibly."""
    plain = _norm(text)
    if plain in REVOCATION:
        return Reply.REVOCATION
    if plain in NEGATIVE:
        return Reply.NEGATIVE
    if plain in AFFIRMATIVE:
        return Reply.AFFIRMATIVE
    return Reply.AMBIGUOUS


class Author(Enum):
    USER = "user"
    REVIEWER = "reviewer"
    REPOSITORY = "repository-file"
    PR_TEXT = "pr-issue-commit-text"
    TOOL_OUTPUT = "tool-output"
    PAGE = "page-or-console"
    SPAWNED_CHILD = "spawned-child"
    PRIOR_SESSION = "prior-session"


@dataclass(frozen=True)
class Turn:
    author: Author
    text: str
    is_offer: bool = False


class Channel(Enum):
    TRUSTED_RUNTIME = "trusted-runtime"
    REPOSITORY_FILE = "repository-file"
    PR_TEXT = "pr-text"
    WORKFLOW_FILE = "workflow-file"


@dataclass(frozen=True)
class Structured:
    value: bool
    channel: Channel = Channel.TRUSTED_RUNTIME
    ambiguous: bool = False


class Consent(Enum):
    GRANTED = "granted"
    DECLINED = "declined"
    REVOKED = "revoked"
    UNAVAILABLE = "unavailable"
    NEEDS_OFFER = "needs-offer"


class Basis(Enum):
    SESSION = "session"
    INVOCATION = "invocation"
    DECLINED = "declined"
    REVOKED = "revoked"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ConsentState:
    state: Consent
    basis: Basis | None


def resolve_consent(
    *,
    structured: Structured | None = None,
    visible_turns: Sequence[Turn] = (),
    interactive: bool = False,
) -> ConsentState:
    """Resolve the consent state from the closed source list.

    Structured trusted value first (explicit `false` always wins), then the
    last decisive user turn still visible in the reviewer's context.
    """
    if structured is not None and not structured.ambiguous:
        if structured.channel is Channel.TRUSTED_RUNTIME:
            if not structured.value:
                return ConsentState(Consent.DECLINED, Basis.DECLINED)
            return ConsentState(Consent.GRANTED, Basis.INVOCATION)

    offered = False
    revoked_seen = False
    decision: ConsentState | None = None
    for turn in visible_turns:
        if turn.is_offer and turn.author is Author.REVIEWER:
            offered = True
            continue
        if turn.author is not Author.USER:
            continue  # only text attributable to the user's own turn counts
        reply = classify_reply(turn.text)
        if reply is Reply.REVOCATION:
            # Revocation voids every earlier approval; only a new offer re-opens it.
            decision = ConsentState(Consent.REVOKED, Basis.REVOKED)
            offered = False
            revoked_seen = True
        elif reply is Reply.NEGATIVE and offered:
            decision = ConsentState(Consent.DECLINED, Basis.DECLINED)
        elif reply is Reply.AFFIRMATIVE and (
            offered or ("=" in _norm(turn.text) and not revoked_seen)
        ):
            decision = ConsentState(Consent.GRANTED, Basis.SESSION)
    if decision is not None:
        return decision
    if interactive:
        return ConsentState(Consent.NEEDS_OFFER, None)
    return ConsentState(Consent.UNAVAILABLE, Basis.UNAVAILABLE)


class GateAction(Enum):
    SILENT = "silent"
    OFFER = "offer"
    PROCEED = "proceed"
    SKIP = "skip"


@dataclass(frozen=True)
class GateResult:
    action: GateAction
    reason: str | None = None
    basis: Basis | None = None
    waits: bool = False
    renders: bool = False
    record: bool = False
    blocks_review: bool = False


def gate(
    *,
    trigger_fires: bool,
    change_classes: Sequence[str],
    consent: ConsentState,
    offered_this_review: bool = False,
) -> GateResult:
    """The consent gate: silent unless the trigger fired and the diff touches a
    change class; never waits unless an offer is actually made."""
    if not trigger_fires or not change_classes:
        return GateResult(GateAction.SILENT)
    if consent.state is Consent.GRANTED:
        return GateResult(GateAction.PROCEED, basis=consent.basis, renders=True)
    if consent.state is Consent.REVOKED:
        return GateResult(GateAction.SKIP, "consent-revoked", consent.basis, record=True)
    if consent.state is Consent.DECLINED:
        return GateResult(GateAction.SKIP, "consent-declined", consent.basis, record=True)
    if consent.state is Consent.NEEDS_OFFER:
        if offered_this_review:
            return GateResult(GateAction.SKIP, "consent-declined", Basis.DECLINED, record=True)
        return GateResult(GateAction.OFFER, waits=True)
    return GateResult(GateAction.SKIP, "consent-unavailable", Basis.UNAVAILABLE, record=True)


def answer_offer(answer: str | None) -> ConsentState:
    """No answer, an ended host turn, or a negative all end as `declined`."""
    if answer is None:
        return ConsentState(Consent.DECLINED, Basis.DECLINED)
    reply = classify_reply(answer)
    if reply is Reply.AFFIRMATIVE:
        return ConsentState(Consent.GRANTED, Basis.SESSION)
    return ConsentState(Consent.DECLINED, Basis.DECLINED)


def effective_supplied_signals(supplied: dict[str, tuple[bool, Channel]]) -> dict[str, bool]:
    """Only the trusted `allow_rendered_inspection` counts; the removed install
    and opt-out signals are ignored."""
    result: dict[str, bool] = {}
    value = supplied.get(CONSENT_SIGNAL)
    if value is not None and value[1] is Channel.TRUSTED_RUNTIME:
        result[CONSENT_SIGNAL] = value[0]
    return result


class Source(Enum):
    PROJECT = "project-playwright"
    USER_LEVEL = "user-level-playwright"
    NONE = "none"


@dataclass(frozen=True)
class Candidate:
    package_present: bool
    browser_binary_present: bool = True
    shares_user_profile: bool = False

    @property
    def usable(self) -> bool:
        return (
            self.package_present
            and self.browser_binary_present
            and not self.shares_user_profile
        )


ABSENT = Candidate(package_present=False)


@dataclass(frozen=True)
class Availability:
    source: Source
    outcome: str | None
    reason: str | None
    statement: str | None
    runs_repository_code: bool = False


NOT_PERFORMED = "rendered verification was unavailable and was not performed"


def check_playwright(
    project: Candidate,
    user_level: Candidate,
    *,
    isolation_boundary: bool = False,
    trusted_host: bool = False,
) -> Availability:
    """Read-only, first usable source wins. The project's installation runs
    repository-controlled code and so needs the boundary or trusted-host
    authorization; otherwise the check continues to the user-level install."""
    project_gated = False
    if project.usable:
        if isolation_boundary or trusted_host:
            return Availability(Source.PROJECT, None, None, None, runs_repository_code=True)
        project_gated = True
    if user_level.usable:
        return Availability(Source.USER_LEVEL, None, None, None)
    if project_gated:
        return Availability(
            Source.NONE, "skipped", "project-playwright-gated", NOT_PERFORMED
        )
    return Availability(Source.NONE, "unavailable", "playwright-missing", NOT_PERFORMED)


FORBIDDEN_CONFIG_KEYS = ("globalSetup", "globalTeardown", "webServer", "fixtures", "reporter")
