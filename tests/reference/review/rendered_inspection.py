#!/usr/bin/env python3
"""Test-only reference model for shared/policies/rendered-inspection.md.

Not runtime logic, not packaged. It models the deterministic parts of the
contract: the UI-impact trigger, budget enforcement, outcome mapping, the
objective/subjective routing, the single shared observation cap, and the
evidence record. No browser is involved.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

MAX_TARGETS = 3
MAX_VIEWPORTS = 2
MAX_CAPTURES = 6
MAX_OBSERVATIONS = 3
WALL_CLOCK_SECONDS = 120


class Outcome(Enum):
    INSPECTED = "inspected"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"
    ATTEMPTED_INCONCLUSIVE = "attempted-inconclusive"


class Mode(Enum):
    ANALYTICAL = "analytical"
    DESIGN_REFERENCE = "design-reference"


@dataclass(frozen=True)
class ChangeFacts:
    user_facing_dimension_implicated: bool
    rendered_output_materially_changes: bool
    render_could_add_evidence: bool


def trigger_fires(facts: ChangeFacts) -> bool:
    """The UI-impact trigger: all three conditions, otherwise inert."""
    return (
        facts.user_facing_dimension_implicated
        and facts.rendered_output_materially_changes
        and facts.render_could_add_evidence
    )


@dataclass(frozen=True)
class Target:
    target_id: str
    viewports: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    targets: tuple[Target, ...]
    captures: int


def bound_plan(targets: Sequence[Target]) -> Plan:
    """Apply the default budget: at most 3 targets, 2 viewports each, 6
    captures in total, one attempt per target and viewport."""
    kept: list[Target] = []
    captures = 0
    for target in targets[:MAX_TARGETS]:
        viewports = target.viewports[:MAX_VIEWPORTS]
        room = MAX_CAPTURES - captures
        if room <= 0:
            break
        viewports = viewports[:room]
        if not viewports:
            break
        kept.append(Target(target.target_id, viewports))
        captures += len(viewports)
    return Plan(tuple(kept), captures)


@dataclass(frozen=True)
class Attempt:
    target_ready: bool
    capability_present: bool
    sha_matches: bool
    completed_within_budget: bool
    pages_rendered: int


def map_outcome(attempt: Attempt) -> Outcome:
    """No page rendered is never `inspected`."""
    if not attempt.capability_present or not attempt.target_ready:
        return Outcome.UNAVAILABLE
    if not attempt.sha_matches:
        return Outcome.ATTEMPTED_INCONCLUSIVE
    if attempt.pages_rendered <= 0 or not attempt.completed_within_budget:
        return Outcome.ATTEMPTED_INCONCLUSIVE
    return Outcome.INSPECTED


def may_emit_visual_output(outcome: Outcome) -> bool:
    """No-fabrication: findings/observations only from an inspected render."""
    return outcome is Outcome.INSPECTED


@dataclass(frozen=True)
class Coverage:
    coverage: str
    decision_changed: bool


def coverage_effect(outcome: Outcome, base_coverage: str) -> Coverage:
    """No outcome ever alters coverage or the Decision derivation."""
    return Coverage(coverage=base_coverage, decision_changed=False)


@dataclass(frozen=True)
class Concern:
    description: str
    user_blocked_misled_or_excluded: bool = False
    requirement_unmet: bool = False
    measurable_engineering_cost: bool = False
    caused_by_change: bool = True
    rendered_target_id: str | None = None
    state: str | None = None


class Route(Enum):
    FINDING = "finding"
    OBSERVATION = "observation"
    NOT_REPORTED = "not-reported"


def route_concern(concern: Concern, outcome: Outcome) -> Route:
    """Objective/subjective boundary test plus the no-fabrication rule."""
    if not may_emit_visual_output(outcome):
        return Route.NOT_REPORTED
    objective = (
        concern.user_blocked_misled_or_excluded
        or concern.requirement_unmet
        or concern.measurable_engineering_cost
    )
    if objective:
        # An objective defect needs a causal link to the change.
        return Route.FINDING if concern.caused_by_change else Route.NOT_REPORTED
    if concern.rendered_target_id is None or concern.state is None:
        return Route.NOT_REPORTED
    return Route.OBSERVATION


@dataclass(frozen=True)
class Observation:
    target_id: str
    state: str
    text: str
    views: int = 1


def cap_observations(
    observations: Sequence[Observation], plan_order: Sequence[str]
) -> tuple[Observation, ...]:
    """One cap shared by every observation source: earlier plan target, then
    most-viewed state, then plan order, then lexical target id."""
    rank = {target_id: index for index, target_id in enumerate(plan_order)}
    ordered = sorted(
        observations,
        key=lambda o: (rank.get(o.target_id, len(rank)), -o.views, o.target_id),
    )
    return tuple(ordered[:MAX_OBSERVATIONS])


def render_observations_section(observations: Sequence[Observation]) -> str:
    """Omitted entirely — not rendered empty — when there are none."""
    if not observations:
        return ""
    lines = ["### Rendered observations"]
    for index, obs in enumerate(observations, start=1):
        lines.append(f"{index}. {obs.target_id} · {obs.state}: {obs.text}")
    return "\n".join(lines)


def render_record(
    mode: Mode,
    outcome: Outcome,
    *,
    target_source: str,
    sha: str,
    viewports: Sequence[str],
    states: Sequence[str],
    observed: str,
    design_reference: str | None = None,
) -> str:
    """The compact `Validation` entry. The design-reference line exists only
    in design-reference mode."""
    entry = (
        f"Rendered inspection: {mode.value} · target source {target_source} · "
        f"SHA {sha} · viewports {', '.join(viewports)} · states {', '.join(states)} · "
        f"outcome {outcome.value} · observed {observed}"
    )
    if mode is Mode.DESIGN_REFERENCE and design_reference:
        entry += f"\nDesign reference: {design_reference}"
    return entry


def output_for(facts: ChangeFacts) -> str | None:
    """Inert on a non-firing trigger: no record, no section, nothing."""
    if not trigger_fires(facts):
        return None
    return "active"


class TargetSource(Enum):
    DECLARED_SERVER = "declared-running-server"
    TRUSTED_PREVIEW = "sha-matched-trusted-preview"
    START_COMMAND = "declared-start-command"
    NONE = "none"


@dataclass(frozen=True)
class Candidate:
    source: TargetSource
    from_trusted_channel: bool = True
    bound_sha: str | None = None
    introduced_by_content: bool = False


@dataclass(frozen=True)
class Selection:
    source: TargetSource
    outcome: Outcome | None
    reason: str


def can_start_command(*, sandbox_established: bool, trusted_host_authorized: bool) -> bool:
    """Source 3 needs the verified boundary or explicit trusted-host
    authorization; absence never falls back to host execution."""
    return sandbox_established or trusted_host_authorized


def select_target(
    candidates: Sequence[Candidate],
    reviewed_sha: str,
    *,
    sandbox_established: bool = False,
    trusted_host_authorized: bool = False,
) -> Selection:
    """First available source in priority order that passes its gate.

    Content-introduced candidates are never considered; a SHA-mismatched one
    is recorded inconclusive and is not evidence; no fallback past a gate.
    """
    order = (TargetSource.DECLARED_SERVER, TargetSource.TRUSTED_PREVIEW, TargetSource.START_COMMAND)
    usable = {c.source: c for c in candidates if not c.introduced_by_content}
    for source in order:
        cand = usable.get(source)
        if cand is None:
            continue
        if source is not TargetSource.START_COMMAND:
            if not cand.from_trusted_channel:
                continue
            if cand.bound_sha != reviewed_sha:
                return Selection(source, Outcome.ATTEMPTED_INCONCLUSIVE, "sha-mismatch")
            return Selection(source, None, "selected")
        if not can_start_command(
            sandbox_established=sandbox_established,
            trusted_host_authorized=trusted_host_authorized,
        ):
            return Selection(source, Outcome.UNAVAILABLE, "no-boundary-or-authorization")
        return Selection(source, None, "selected")
    return Selection(TargetSource.NONE, Outcome.UNAVAILABLE, "no-target")


SERVER_START_TIMEOUT_SECONDS = 30
NAVIGATION_TIMEOUT_SECONDS = 15
MAX_ATTEMPTS = 1


@dataclass(frozen=True)
class StepRun:
    server_start_seconds: float = 0
    navigation_seconds: float = 0
    total_seconds: float = 0
    attempts: int = 1
    needs_credentials: bool = False
    tree_changed: bool = False
    process_torn_down: bool = True


def map_step(run: StepRun) -> Outcome:
    """Bounds, one attempt, credential need, and post-run tree check."""
    if run.needs_credentials:
        return Outcome.UNAVAILABLE
    if (
        run.attempts > MAX_ATTEMPTS
        or run.server_start_seconds > SERVER_START_TIMEOUT_SECONDS
        or run.navigation_seconds > NAVIGATION_TIMEOUT_SECONDS
        or run.total_seconds > WALL_CLOCK_SECONDS
        or run.tree_changed
        or not run.process_torn_down
    ):
        return Outcome.ATTEMPTED_INCONCLUSIVE
    return Outcome.INSPECTED
