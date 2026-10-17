#!/usr/bin/env python3
"""Test-only reference model for the change-aware verification half of
shared/policies/rendered-inspection.md ("Verification plan", "Input, after-only
rendering, and the Playwright runtime", "Evidence kinds and per-check status").

Not runtime logic, not packaged. It models diff-derived planning, viewport
selection, per-check evidence kinds and status, the closed reason set, the
checks slot, and finding routing. No browser is involved.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from tests.reference.review.rendered_inspection import MAX_CAPTURES, MAX_VIEWPORTS


class Kind(Enum):
    DOM = "dom"
    VISUAL = "visual"
    INTERACTION = "interaction"


class ChangeClass(Enum):
    GRID = "grid"
    OVERFLOW = "overflow-and-clipping"
    TYPOGRAPHY = "typography-and-text"
    INTERACTION = "interaction-and-state"
    RESPONSIVE = "responsive-layout"
    POSITIONING = "positioning-and-stacking"
    VISIBILITY = "visibility-and-appearance"


CLASSES = tuple(ChangeClass)  # closed set of seven; no eighth class

# Closed reason set (six tokens).
REASONS = (
    "budget",
    "input unavailable",
    "mutation blocked",
    "target not disposable",
    "timeout",
    "visual evidence insufficient",
)
VISUAL_ONLY_REASON = "visual evidence insufficient"

# Diff tokens that name a class. `decorative-shadow` and `refactor` name none.
TOKEN_CLASS = {
    "grid": ChangeClass.GRID,
    "overflow": ChangeClass.OVERFLOW,
    "scroll-cue": ChangeClass.OVERFLOW,
    "horizontal-overflow-indicator": ChangeClass.OVERFLOW,
    "focus-outline": ChangeClass.OVERFLOW,
    "typography": ChangeClass.TYPOGRAPHY,
    "interaction": ChangeClass.INTERACTION,
    "responsive": ChangeClass.RESPONSIVE,
    "positioning": ChangeClass.POSITIONING,
    "visibility": ChangeClass.VISIBILITY,
}


@dataclass(frozen=True)
class DiffFacts:
    tokens: frozenset[str]
    focusable_children: bool = False
    breakpoints: tuple[int, ...] = ()
    theming_changed: bool = False


@dataclass(frozen=True)
class PlanItem:
    change_class: ChangeClass
    property: str
    kind: Kind


def _items(cls: ChangeClass, prop: str, *kinds: Kind) -> list[PlanItem]:
    return [PlanItem(cls, prop, kind) for kind in kinds]


def build_plan(facts: DiffFacts) -> tuple[PlanItem, ...]:
    """Static, diff-derived, proportional: only touched classes, and inside a
    class only the properties the diff can affect."""
    items: list[PlanItem] = []
    tokens = facts.tokens
    if "grid" in tokens:
        items += _items(ChangeClass.GRID, "track-sizes", Kind.DOM)
        items += _items(ChangeClass.GRID, "alignment-spacing-proportions", Kind.VISUAL)
        if facts.breakpoints:
            items += _items(ChangeClass.GRID, "breakpoint-behavior", Kind.DOM, Kind.VISUAL)
    if "overflow" in tokens:
        items += _items(ChangeClass.OVERFLOW, "clipped-content", Kind.DOM, Kind.VISUAL)
        items += _items(ChangeClass.OVERFLOW, "scrollability", Kind.DOM)
        if facts.focusable_children:
            items += _items(
                ChangeClass.OVERFLOW,
                "focus-outline-clipping",
                Kind.DOM,
                Kind.VISUAL,
                Kind.INTERACTION,
            )
            items += _items(ChangeClass.OVERFLOW, "child-reachability", Kind.INTERACTION)
    if "scroll-cue" in tokens:
        items += _items(ChangeClass.OVERFLOW, "scroll-cue-visibility", Kind.DOM, Kind.VISUAL)
    if "horizontal-overflow-indicator" in tokens:
        items += _items(
            ChangeClass.OVERFLOW, "horizontal-overflow-indicator", Kind.DOM, Kind.VISUAL
        )
    if "focus-outline" in tokens and not any(
        i.property == "focus-outline-clipping" for i in items
    ):
        items += _items(
            ChangeClass.OVERFLOW, "focus-outline-clipping", Kind.DOM, Kind.VISUAL, Kind.INTERACTION
        )
    if "typography" in tokens:
        items += _items(ChangeClass.TYPOGRAPHY, "wrapping-truncation", Kind.DOM, Kind.VISUAL)
    if "interaction" in tokens:
        items += _items(ChangeClass.INTERACTION, "keyboard-navigation", Kind.INTERACTION)
        items += _items(ChangeClass.INTERACTION, "focus-order-visibility", Kind.INTERACTION, Kind.DOM)
    if "responsive" in tokens:
        items += _items(ChangeClass.RESPONSIVE, "reflow", Kind.DOM, Kind.VISUAL)
    if "positioning" in tokens:
        items += _items(ChangeClass.POSITIONING, "overlap-occlusion", Kind.DOM, Kind.VISUAL)
    if "visibility" in tokens:
        items += _items(ChangeClass.VISIBILITY, "hidden-or-revealed-content", Kind.DOM, Kind.VISUAL)
    return tuple(items)


def classes_touched(facts: DiffFacts) -> tuple[ChangeClass, ...]:
    seen: list[ChangeClass] = []
    for token in sorted(facts.tokens):
        cls = TOKEN_CLASS.get(token)
        if cls is not None and cls not in seen:
            seen.append(cls)
    return tuple(seen)


def offer_would_fire(facts: DiffFacts) -> bool:
    """The consent gate offers only when the diff touches a change class, even
    if consent was granted earlier in the session."""
    return bool(build_plan(facts))


DESKTOP = 1440
MOBILE_WIDTHS = (320, 375, 390, 430)


@dataclass(frozen=True)
class ViewportSelection:
    viewports: tuple[int, ...]
    not_checked: tuple[tuple[int, str], ...]


def select_viewports(facts: DiffFacts) -> ViewportSelection:
    """Chosen from the diff inside the unchanged cap of 2 viewports."""
    if not facts.breakpoints:
        return ViewportSelection((DESKTOP,), ())
    primary = facts.breakpoints[0]
    below = max([w for w in (320, 375, 390, 430, 600) if w < primary] or [primary - 1])
    chosen = (below, primary)
    uncovered = tuple(
        (width, "budget")
        for bp in facts.breakpoints[1:]
        for width in (bp - 1, bp)
    )
    return ViewportSelection(chosen[:MAX_VIEWPORTS], uncovered)


def captures_needed(items: Sequence[PlanItem], viewports: Sequence[int]) -> int:
    """Screenshots only to answer a stated visual question; one capture may
    serve several visual checks of the same target and viewport."""
    if not any(i.kind is Kind.VISUAL for i in items):
        return 0
    return min(len(viewports), MAX_CAPTURES)






# --- evidence and per-check status -------------------------------------------------


@dataclass(frozen=True)
class DomRead:
    concern_observed: bool
    detail: str = ""


@dataclass(frozen=True)
class VisualObservation:
    settles_question: bool
    concern_observed: bool
    target: str = ""
    state: str = ""
    observation: str = ""
    capture_readable: bool = True


@dataclass(frozen=True)
class InteractionResult:
    concern_observed: bool


@dataclass(frozen=True)
class Evidence:
    dom: DomRead | None = None
    visual: VisualObservation | None = None
    interaction: InteractionResult | None = None
    # Context that is never evidence of a visual or interaction check:
    playwright_test_passed: bool = False
    ci_status_green: bool = False
    computed_focus_style_present: bool = False
    # Host and plan conditions:
    input_available: bool = True
    needs_write: bool = False
    needs_activation: bool = False
    target_disposable: bool = True
    over_budget: bool = False
    timed_out: bool = False
    capture_possible: bool = True


class Status(Enum):
    CONFIRMED = "confirmed"
    REFUTED = "refuted"
    NOT_CHECKED = "not-checked"


@dataclass(frozen=True)
class CheckResult:
    prop: str
    kind: Kind
    viewport: int
    status: Status
    reason: str | None = None
    dom_support: bool = False

    def slot(self) -> str:
        status = self.status.value
        if self.status is Status.NOT_CHECKED:
            status = f"not-checked({self.reason})"
        return f"{self.prop}:{self.kind.value}@{self.viewport}={status}"


def validate_result(result: CheckResult) -> None:
    """The reason set is closed, and the visual token is for visual checks only."""
    if result.status is Status.NOT_CHECKED:
        if result.reason not in REASONS:
            raise ValueError(f"reason outside the closed set: {result.reason!r}")
        if result.reason == VISUAL_ONLY_REASON and result.kind is not Kind.VISUAL:
            raise ValueError("visual evidence insufficient applies to visual checks only")
    elif result.reason is not None:
        raise ValueError("only a not-checked result carries a reason")


def _not_checked(item: PlanItem, viewport: int, reason: str, *, dom: bool = False) -> CheckResult:
    result = CheckResult(item.property, item.kind, viewport, Status.NOT_CHECKED, reason, dom)
    validate_result(result)
    return result


def evaluate(item: PlanItem, viewport: int, evidence: Evidence) -> CheckResult:
    """Complete a check only with evidence of its own kind."""
    if evidence.over_budget:
        return _not_checked(item, viewport, "budget")
    if evidence.timed_out:
        return _not_checked(item, viewport, "timeout")
    dom_support = evidence.dom is not None
    if item.kind is Kind.DOM:
        if evidence.dom is None:
            return _not_checked(item, viewport, "timeout")
        status = Status.CONFIRMED if evidence.dom.concern_observed else Status.REFUTED
        return CheckResult(item.property, Kind.DOM, viewport, status)
    if item.kind is Kind.VISUAL:
        visual = evidence.visual
        if (
            visual is None
            or not evidence.capture_possible
            or not visual.capture_readable
            or not visual.settles_question
        ):
            return _not_checked(item, viewport, VISUAL_ONLY_REASON, dom=dom_support)
        status = Status.CONFIRMED if visual.concern_observed else Status.REFUTED
        return CheckResult(item.property, Kind.VISUAL, viewport, status, dom_support=dom_support)
    # interaction
    if not evidence.input_available:
        return _not_checked(item, viewport, "input unavailable", dom=dom_support)
    if evidence.needs_write:
        return _not_checked(item, viewport, "mutation blocked")
    if evidence.needs_activation and not evidence.target_disposable:
        return _not_checked(item, viewport, "target not disposable")
    if evidence.interaction is None:
        return _not_checked(item, viewport, "timeout")
    status = Status.CONFIRMED if evidence.interaction.concern_observed else Status.REFUTED
    return CheckResult(item.property, Kind.INTERACTION, viewport, status)


def render_checks_slot(results: Sequence[CheckResult]) -> str:
    return "checks " + "; ".join(r.slot() for r in results)


def human_status(result: CheckResult) -> str:
    """Human text may say "not completed"; the slot always keeps the token."""
    if result.status is Status.NOT_CHECKED:
        return "not completed"
    return result.status.value


def may_say_visually_verified(prop: str, results: Sequence[CheckResult]) -> bool:
    """Only a `visual` check that ran licenses the words for that property."""
    return any(
        r.prop == prop
        and r.kind is Kind.VISUAL
        and r.status in (Status.CONFIRMED, Status.REFUTED)
        for r in results
    )


def record_kinds(results: Sequence[CheckResult]) -> dict[str, set[str]]:
    """Static inference is not a rendered kind; kinds stay separate per property."""
    kinds: dict[str, set[str]] = {}
    for r in results:
        if r.status is not Status.NOT_CHECKED:
            kinds.setdefault(r.prop, set()).add(r.kind.value)
    return kinds




