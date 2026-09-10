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
    location: str  # the canonical fix/action location (finding semantics)
    evidence: str
    impact: str
    fix: str
    # Optional, surface- or case-specific fields. Rendered only when set.
    details: Optional[str] = None
    long_form_category: Optional[str] = None
    location_source_annotation: Optional[str] = None  # local-only, e.g. "staged"
    implementation_prompt: Optional[str] = None  # local-only, opt-in
    # Where evidence was observed, when it differs from the resolved
    # fix/action location. Never rendered when it equals `location` or when
    # the fix/action location is unresolved.
    evidence_location: Optional[str] = None
    # False => an actionable fix/action location could not be resolved; the
    # `location` value carries the best-known coordinate and the Location
    # line gets the explicit unresolved annotation. `location` is never a
    # promoted evidence location.
    fix_location_resolved: bool = True
    # Issue #118: optional provenance — the contextual-evidence entries that
    # informed the finding (each a short "source: clause" string). Rendered
    # only when it materially explains the problem; folds into `evidence`
    # prose on the GitHub inline surface. Never carries or changes severity.
    context_evidence: tuple[str, ...] = ()
    # Issue #178: the finding's one machine-readable evidence-state value —
    # one of "confirmed", "credible", "runtime-validation-unavailable",
    # "external-contract-unvalidated", "insufficient-context". Defaults to
    # "credible" (the floor every reported finding has already met); rendered
    # only when it is not that default; folds into `evidence` prose on the
    # GitHub inline surface. Never lowers the evidence bar and never carries
    # or changes severity, identity, or the decision. See
    # tests/reference/finding_confidence.py for the value set and derivation.
    confidence: str = "credible"


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
    # Strict trailing addition; source-state annotation first, then this.
    if not finding.fix_location_resolved:
        value += " _(evidence location; fix/action location unresolved)_"
    return f"- **Location:** {value}"


def renders_evidence_location(finding: Finding) -> bool:
    """A distinct `Evidence location` line renders only when the fix/action
    location is resolved and a different evidence location is set."""
    return bool(
        finding.fix_location_resolved
        and finding.evidence_location
        and finding.evidence_location != finding.location
    )


def renders_context_evidence(finding: Finding) -> bool:
    """The optional `Contextual evidence` provenance line renders only when
    at least one contextual-evidence entry informed the finding (Issue
    #118). It is independent of severity and of the location fields."""
    return bool(finding.context_evidence)


def renders_confidence(finding: Finding) -> bool:
    """The optional `Confidence` line (Issue #178) renders only when the
    value is not the `credible` default — the same "only when it adds
    information" rule every other optional field follows. It never lowers
    the evidence bar and is independent of severity.

    This reference does not model the `Runtime validation` line (Issue #128
    added its own reference module), so the further human-surface
    suppression — dropping a `confidence` that merely restates a shown
    `Runtime validation` line — lives in
    ``tests/reference/finding_confidence.py``
    (``renders_human_confidence``)."""
    return finding.confidence != "credible"


def render_full(
    finding: Finding,
    *,
    surface: Surface = Surface.LOCAL_REPORT,
    include_fix_prompt: bool = False,
    include_finding_details: Optional[bool] = None,
    finding_detail_override: Optional[bool] = None,
) -> str:
    """The compact full rendering (finding.md, "Canonical full rendering").

    Order is fixed: heading, Location, Evidence, Impact, Fix,
    [Implementation prompt], [Details]. Optional fields are emitted only when selected
    — never as an empty placeholder line.
    """
    if surface is Surface.GITHUB_INLINE:
        raise ValueError("use render_inline for the GitHub inline surface")
    lines = [f"### {finding.id} [{finding.severity.value}] {finding.title}", ""]
    lines.append(_location_line(finding))
    if renders_evidence_location(finding):
        lines.append(f"- **Evidence location:** {finding.evidence_location}")
    lines.append(f"- **Evidence:** {finding.evidence}")
    if renders_context_evidence(finding):
        lines.append(
            f"- **Contextual evidence:** {'; '.join(finding.context_evidence)}"
        )
    if renders_confidence(finding):
        lines.append(f"- **Confidence:** {finding.confidence}")
    lines.append(f"- **Impact:** {finding.impact}")
    lines.append(f"- **Fix:** {finding.fix}")
    if (
        surface is Surface.LOCAL_REPORT
        and include_fix_prompt
        and finding.implementation_prompt
    ):
        lines.append(f"- **Implementation prompt:** {finding.implementation_prompt}")
    default = surface is Surface.LOCAL_REPORT
    show_details = (
        finding_detail_override
        if finding_detail_override is not None
        else include_finding_details
        if include_finding_details is not None
        else default
    )
    if finding.details is not None and show_details:
        lines.append(f"- **Details:** {finding.details}")
    return "\n".join(lines)


def render_inline(
    finding: Finding,
    *,
    include_finding_details: Optional[bool] = None,
    finding_detail_override: Optional[bool] = None,
) -> str:
    """The GitHub inline-comment rendering (finding.md, "Canonical inline
    rendering"): severity first, no `id`, no `Location`."""
    evidence = finding.evidence
    if renders_context_evidence(finding):
        # folds into evidence prose on this surface — no separate line
        evidence = f"{evidence} (contextual evidence: {'; '.join(finding.context_evidence)})"
    if renders_confidence(finding):
        # folds into evidence prose on this surface — no separate line
        evidence = f"{evidence} (confidence: {finding.confidence})"
    lines = [f"[{finding.severity.value}] {finding.title}", "", f"Evidence: {evidence}"]
    lines += ["", f"Impact: {finding.impact}", "", f"Fix: {finding.fix}"]
    show_details = (
        finding_detail_override
        if finding_detail_override is not None
        else include_finding_details
        if include_finding_details is not None
        else False
    )
    if finding.details is not None and show_details:
        lines += ["", f"Details: {finding.details}"]
    return "\n".join(lines)


def render_human_inline(
    finding: Finding,
    *,
    include_finding_details: Optional[bool] = None,
    finding_detail_override: Optional[bool] = None,
) -> str:
    """The opt-in concise "human inline" rendering (finding.md, "Canonical
    human inline rendering"), selected by `human_inline_findings`.

    A re-voicing of the *same fields* onto the GitHub inline surface: a
    heading that keeps the severity (``P2: …``, never ``[P2] …``) and
    names the finding, then prose that still carries evidence, impact, and
    fix — with no ``Evidence:`` / ``Impact:`` / ``Fix:`` labels. `id` and
    `Location` are supplied by the surface, exactly as for
    :func:`render_inline`. This model preserves the *structural*
    invariants a test can check; the real prose is generated, not
    templated.
    """
    heading = f"{finding.severity.value}: {finding.title}"
    # Evidence -> impact -> fix, woven into prose rather than labelled.
    parts = [finding.evidence, finding.impact, finding.fix]
    show_details = (
        finding_detail_override
        if finding_detail_override is not None
        else include_finding_details
        if include_finding_details is not None
        else False
    )
    if finding.details is not None and show_details:
        parts.append(finding.details)
    prose = " ".join(p.strip() for p in parts if p and p.strip())
    return f"{heading}\n\n{prose}"


def human_inline_preserves_semantics(finding: Finding) -> bool:
    """The structured and human inline renderings are two projections of
    one semantic finding: same severity, identity, and canonical location,
    same mandatory core, and no labelled ``Evidence:`` / ``Impact:`` /
    ``Fix:`` block in the human form."""
    human = render_human_inline(finding)
    if not human.startswith(f"{finding.severity.value}: "):
        return False
    if f"[{finding.severity.value}]" in human:
        return False
    if any(label in human for label in ("Evidence:", "Impact:", "Fix:")):
        return False
    # the mandatory core is still fully present for the inline surface
    if missing_mandatory_fields(finding, surface=Surface.GITHUB_INLINE):
        return False
    # every semantic field's substance still reaches the reader
    return all(
        value.strip() in human
        for value in (finding.evidence, finding.impact, finding.fix)
    )


def render_summary_pointer(finding: Finding) -> str:
    """The pointer form used when the full finding lives elsewhere."""
    return f"- **{finding.severity.value} — {finding.title}**\n  `{finding.location}`"


def render_findings_section(findings: Sequence[Finding]) -> str:
    """The review-summary "Findings" section body for a set of findings."""
    if not findings:
        return ""
    return "\n\n".join(render_full(f) for f in findings)
