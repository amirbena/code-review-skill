#!/usr/bin/env python3
"""Test-only reference model for shared/policies/rendered-inspection-environment.md.

Not runtime logic, not packaged. It models the deterministic parts of the
contract: detection order, the four-gate acquisition question, the trusted-source
rules for the opt-out and the install authorization, and the install-command
surface. Nothing here installs or probes anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

PINNED_VERSION = "1.63.0"
BROWSER = "chromium"


class Source(Enum):
    RUNTIME = "runtime-supplied"
    PROJECT = "project-playwright"
    USER_LEVEL = "user-level-playwright"
    NONE = "none"


@dataclass(frozen=True)
class Candidate:
    present: bool
    meets_capability: bool = True
    browser_binary_present: bool = True
    shares_user_profile: bool = False

    @property
    def usable(self) -> bool:
        return (
            self.present
            and self.meets_capability
            and self.browser_binary_present
            and not self.shares_user_profile
        )


ABSENT = Candidate(present=False)


def detect(runtime: Candidate, project: Candidate, user_level: Candidate) -> Source:
    """Read-only detection order; the first usable source wins."""
    if runtime.usable:
        return Source.RUNTIME
    if project.usable:
        return Source.PROJECT
    if user_level.usable:
        return Source.USER_LEVEL
    return Source.NONE


class Channel(Enum):
    TRUSTED_RUNTIME = "trusted-runtime"
    REPOSITORY_FILE = "repository-file"
    PR_TEXT = "pr-text"
    PRIOR_REVIEW = "prior-review"
    CONVERSATION = "conversation"
    SPAWNED_CHILD = "spawned-child"
    PAGE_OR_TOOL_OUTPUT = "page-or-tool-output"


@dataclass(frozen=True)
class Signal:
    value: bool
    channel: Channel
    ambiguous: bool = False


def effective_signal(signal: Signal | None) -> bool:
    """A boolean signal counts only from the trusted runtime channel and when
    unambiguous; anything else is `false`."""
    if signal is None or signal.ambiguous:
        return False
    return signal.value and signal.channel is Channel.TRUSTED_RUNTIME


def install_authorized(signal: Signal | None) -> bool:
    return effective_signal(signal)


def opt_out_present(signal: Signal | None) -> bool:
    return effective_signal(signal)


@dataclass(frozen=True)
class Gates:
    materially_ui_impacting: bool
    meaningful_added_evidence: bool
    usable_capability: bool
    durable_opt_out: bool


def should_ask(gates: Gates) -> bool:
    """The question is emitted only when all four gates hold."""
    return (
        gates.materially_ui_impacting
        and gates.meaningful_added_evidence
        and not gates.usable_capability
        and not gates.durable_opt_out
    )


class Surface(Enum):
    REVIEWER_BRIEF = "reviewer-brief-open-questions"
    LOCAL_FINAL_REPORT = "local-final-report-note"


def surface_for(skill: str) -> Surface:
    return Surface.REVIEWER_BRIEF if skill == "github-pr-review" else Surface.LOCAL_FINAL_REPORT


def install_command(tools_dir: str) -> tuple[str, ...]:
    """The exact command emitted for an operator or supplying runtime. The
    Skill never executes it; it excludes global, sudo, and system packages."""
    return (
        f"mkdir -p {tools_dir} && npm install --prefix {tools_dir} --save-exact "
        f"--ignore-scripts playwright@{PINNED_VERSION}",
        f"{tools_dir}/node_modules/.bin/playwright install {BROWSER}",
    )


@dataclass(frozen=True)
class Action:
    asked: bool
    emit_authorized_install_request: bool
    performed_install: bool
    review_completes: bool


def decide(
    gates: Gates, authorization: Signal | None, opt_out: Signal | None
) -> Action:
    """Never performs an install; the review always completes."""
    effective = Gates(
        gates.materially_ui_impacting,
        gates.meaningful_added_evidence,
        gates.usable_capability,
        gates.durable_opt_out or opt_out_present(opt_out),
    )
    asked = should_ask(effective)
    return Action(
        asked=asked,
        emit_authorized_install_request=asked and install_authorized(authorization),
        performed_install=False,
        review_completes=True,
    )
