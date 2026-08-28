#!/usr/bin/env python3
"""Test-only reference for the canonical finding contract (Issue #37).

Mirrors shared/templates/finding.md: the compact, field-oriented finding
shape shared by both review Skills, its mandatory core, the controlled
longer-explanation exception, and the surface-specific optional fields.
Not runtime logic, not packaged — the packaged Skills are Markdown only.

The contract is the *fields*; a rendering is one projection of them. This
module models the fields and the three canonical projections (full,
inline, summary-pointer) so a test can assert the externally visible
shape does not silently drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence


class Severity(Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


class Surface(Enum):
    """A delivery surface a finding is projected onto."""

    LOCAL_REPORT = "local_report"
    GITHUB_BODY = "github_body"
    GITHUB_INLINE = "github_inline"


# A GitHub inline comment supplies its own file/line anchor and comment
# identity, so `id` and `location` are not repeated as fields there.
SURFACES_WITHOUT_ID_AND_LOCATION: frozenset[Surface] = frozenset({Surface.GITHUB_INLINE})

# The mandatory core of a normal actionable finding, in canonical order.
# "Where" (location) is still mandatory as information; on a surface in
# SURFACES_WITHOUT_ID_AND_LOCATION it is carried by the surface itself.
MANDATORY_CORE: tuple[str, ...] = (
    "id",
    "severity",
    "title",
    "location",
    "evidence",
    "impact",
    "fix",
)

# The only finding categories permitted a longer `details` explanation,
# per finding.md, "When a longer explanation is justified".
LONG_FORM_CATEGORIES: frozenset[str] = frozenset(
    {
        "cross_file_behavior",
        "concurrency_or_ordering",
        "security_implication",
        "complex_invariant_violation",
        "evidence_needs_context",
    }
)


@dataclass(frozen=True)
class Finding:
    id: str
    severity: Severity
    title: str
    location: str
    evidence: str
    impact: str
    fix: str
    # Optional, surface- or case-specific fields. Rendered only when set.
    details: Optional[str] = None
    long_form_category: Optional[str] = None
    location_source_annotation: Optional[str] = None  # local-only, e.g. "staged"
    implementation_prompt: Optional[str] = None  # local-only, opt-in


def missing_mandatory_fields(finding: Finding, *, surface: Surface) -> tuple[str, ...]:
    """Mandatory-core fields that are absent/empty for this surface.

    A publishable finding returns () — the mandatory core is never reduced
    to hit a length target.
    """
    skip = (
        {"id", "location"} if surface in SURFACES_WITHOUT_ID_AND_LOCATION else set()
    )
    missing = []
    for name in MANDATORY_CORE:
        if name in skip:
            continue
        value = getattr(finding, name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(name)
    return tuple(missing)


def has_justified_long_form(finding: Finding) -> bool:
    """A `details` field is justified only for a listed long-form category.

    Drift guard: a finding that carries a longer explanation without being
    one of the controlled-exception categories is *not* justified — agents
    must not default back to verbose prose.
    """
    if finding.details is None:
        return True  # no longer explanation -> nothing to justify
    return finding.long_form_category in LONG_FORM_CATEGORIES


def _location_line(finding: Finding) -> str:
    value = f"`{finding.location}`"
    if finding.location_source_annotation:
        value += f" _({finding.location_source_annotation})_"
    return f"- **Location:** {value}"


def render_full(
    finding: Finding, *, surface: Surface = Surface.LOCAL_REPORT, include_fix_prompt: bool = False
) -> str:
    """The compact full rendering (finding.md, "Canonical full rendering").

    Order is fixed: heading, Location, Evidence, [Details], Impact, Fix,
    [Implementation prompt]. Optional fields are emitted only when populated
    — never as an empty placeholder line.
    """
    if surface is Surface.GITHUB_INLINE:
        raise ValueError("use render_inline for the GitHub inline surface")
    lines = [f"### {finding.id} [{finding.severity.value}] {finding.title}", ""]
    lines.append(_location_line(finding))
    lines.append(f"- **Evidence:** {finding.evidence}")
    if finding.details is not None:
        lines.append(f"- **Details:** {finding.details}")
    lines.append(f"- **Impact:** {finding.impact}")
    lines.append(f"- **Fix:** {finding.fix}")
    if (
        surface is Surface.LOCAL_REPORT
        and include_fix_prompt
        and finding.implementation_prompt
    ):
        lines.append(f"- **Implementation prompt:** {finding.implementation_prompt}")
    return "\n".join(lines)


def render_inline(finding: Finding) -> str:
    """The GitHub inline-comment rendering (finding.md, "Canonical inline
    rendering"): severity first, no `id`, no `Location`."""
    lines = [f"[{finding.severity.value}] {finding.title}", "", f"Evidence: {finding.evidence}"]
    if finding.details is not None:
        lines += ["", f"Details: {finding.details}"]
    lines += ["", f"Impact: {finding.impact}", "", f"Fix: {finding.fix}"]
    return "\n".join(lines)


def render_summary_pointer(finding: Finding) -> str:
    """The pointer form used when the full finding lives elsewhere."""
    return f"- **{finding.severity.value} — {finding.title}**\n  `{finding.location}`"


NO_FINDINGS_LINE = "No P0, P1, or P2 findings."


def render_findings_section(findings: Sequence[Finding]) -> str:
    """The review-summary "Findings" section body for a set of findings."""
    if not findings:
        return NO_FINDINGS_LINE
    return "\n\n".join(render_full(f) for f in findings)
