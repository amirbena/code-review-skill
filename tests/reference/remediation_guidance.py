#!/usr/bin/env python3
"""Test-only output model for remediation guidance; not runtime logic, not packaged."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class Finding:
    id: str
    severity: str
    title: str
    recommended_direction: str
    implementation_prompt: Optional[str] = None


@dataclass(frozen=True)
class Review:
    findings: tuple[Finding, ...]
    decision: str
    rendered: str


def _decision(findings: Sequence[Finding]) -> str:
    return (
        "CHANGES REQUIRED"
        if any(finding.severity in {"P0", "P1"} for finding in findings)
        else "REVIEW CLEAN"
    )


def render_local(
    findings: Sequence[Finding], *, include_fix_prompt: bool = False
) -> Review:
    """The opt-in changes rendering only, never findings or decision."""
    sections = []
    for finding in findings:
        body = (
            f"{finding.id} [{finding.severity}] {finding.title}\n"
            f"Recommended direction: {finding.recommended_direction}"
        )
        if include_fix_prompt and finding.implementation_prompt:
            body += f"\nImplementation prompt: {finding.implementation_prompt}"
        sections.append(body)
    return Review(tuple(findings), _decision(findings), "\n\n".join(sections))


def render_github(findings: Sequence[Finding]) -> Review:
    """GitHub renders concise reviewer guidance without local fix prompts."""
    rendered = "\n\n".join(
        f"{finding.id} [{finding.severity}] {finding.title}\n"
        f"Recommended direction: {finding.recommended_direction}"
        for finding in findings
    )
    decision = (
        "REQUEST CHANGES" if _decision(findings) == "CHANGES REQUIRED" else "APPROVE"
    )
    return Review(tuple(findings), decision, rendered)
