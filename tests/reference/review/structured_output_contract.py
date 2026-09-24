#!/usr/bin/env python3
"""Test-only cross-Skill contract checks for the structured review result (Issue #71).

Contract: docs/review-result/review-result-model.md section 8. Splits one
Skill output into its human report and its structured result, checks the
result against the versioned schema (fail closed), checks each Skill's
surface-specific population, and compares the result with the human report
without re-deriving the decision. Not runtime logic, not packaged.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from tests.reference.review import review_result as rr
from tests.reference.review import review_result_version as rv
from tests.reference.review.verdict_consistency import RenderedSignal

LOCAL = "local-code-review"
GITHUB = "github-pr-review"
SKILLS = (LOCAL, GITHUB)

# Only these top-level fields are populated per surface; every other field is shared.
SURFACE_SPECIFIC_FIELDS = ("skill", "reviewed_state")

STRUCTURED_HEADING = "### Structured Review Result"
NOT_EMITTED_PREFIX = "Structured review result not emitted:"

# review-result-model.md section 4: rendered decision label -> machine outcome.
_SIGNAL_OUTCOME = {
    RenderedSignal.REVIEW_CLEAN: "clean",
    RenderedSignal.APPROVE: "clean",
    RenderedSignal.CHANGES_REQUIRED: "blocking",
    RenderedSignal.REQUEST_CHANGES: "blocking",
    RenderedSignal.REVIEW_INCOMPLETE: "incomplete",
}
# A GitHub self-review renders the local-style labels (external-review-summary.md).
_SKILL_SIGNALS = {
    LOCAL: (RenderedSignal.REVIEW_CLEAN, RenderedSignal.CHANGES_REQUIRED, RenderedSignal.REVIEW_INCOMPLETE),
    GITHUB: tuple(RenderedSignal),
}
RENDERED_OUTCOME: dict[str, dict[str, str]] = {
    skill: {signal.value.upper(): _SIGNAL_OUTCOME[signal] for signal in signals}
    for skill, signals in _SKILL_SIGNALS.items()
}

_JSON_FENCE = re.compile(r"^```json[ \t]*\n(.*?)\n```[ \t]*$", re.M | re.S)
_DECISION = re.compile(r"^### Decision[ \t]*\n+\*\*([^*\n]+)\*\*", re.M)
_SEVERITY = r"(P[012])(?: \([^)\n]*\))?"
_FULL_FINDING = re.compile(rf"^#### (F\d+) (?:\[{_SEVERITY}\]|{_SEVERITY}:) (.+?)[ \t]*$", re.M)
_POINTER_FINDING = re.compile(rf"^- \*\*{_SEVERITY} — (.+?)\*\*", re.M)
_SECTION_END = re.compile(r"^#{2,4} ", re.M)
_AFFECTED = re.compile(r"^- \*\*Affected locations:\*\*[ \t]*\n((?:[ \t]+- .*\n?)+)", re.M)
_AFFECTED_ENTRY = re.compile(r"^[ \t]+- `([^`]+)` — (.+?)[ \t]*$", re.M)
_LOCAL_COUNTS = re.compile(r"^- P0: (\d+), P1: (\d+), P2: (\d+)[ \t]*$", re.M)
_GITHUB_COUNT = re.compile(r"^- (P[012]): (\d+)[ \t]*$", re.M)
_COVERAGE = {
    LOCAL: re.compile(r"^- Coverage: (complete|incomplete)\b", re.M),
    GITHUB: re.compile(r"^- coverage: `(complete|incomplete)\b", re.M),
}
_HEAD = {
    LOCAL: re.compile(r"^- Local HEAD: `([0-9a-f]{40})`", re.M),
    GITHUB: re.compile(r"^- reviewed_head: `([0-9a-f]{40})`", re.M),
}


class ContractError(ValueError):
    """The output cannot be consumed: missing, ambiguous, or malformed result."""


@dataclass(frozen=True)
class SplitOutput:
    human: str
    result: Optional[dict]
    not_emitted_reason: Optional[str] = None


@dataclass(frozen=True)
class RenderedFinding:
    id: Optional[str]
    severity: str
    title: str
    # None when the finding was not rendered in full (a GitHub pointer line).
    affected_locations: Optional[tuple[tuple[str, str], ...]] = None


@dataclass(frozen=True)
class HumanReport:
    decision_label: Optional[str]
    counts: Optional[dict[str, int]]
    coverage: Optional[str]
    head: Optional[str]
    findings: tuple[RenderedFinding, ...]


def split_output(text: str, skill: str) -> SplitOutput:
    """The human part precedes the single fenced `json` result; the result is last."""
    fences = list(_JSON_FENCE.finditer(text))
    if not fences:
        for line in text.splitlines():
            if line.startswith(NOT_EMITTED_PREFIX):
                return SplitOutput(text, None, line[len(NOT_EMITTED_PREFIX):].strip())
        raise ContractError("no structured result block and no not-emitted statement")
    if len(fences) > 1:
        raise ContractError(f"expected exactly one json block, found {len(fences)}")
    fence = fences[0]
    if text[fence.end():].strip():
        raise ContractError("the structured result must be the last part of the output")
    human = text[: fence.start()]
    if skill == LOCAL:
        stripped = human.rstrip()
        if not stripped.endswith(STRUCTURED_HEADING) or human.count(STRUCTURED_HEADING) != 1:
            raise ContractError(f"local result must directly follow one {STRUCTURED_HEADING!r} heading")
        human = stripped[: -len(STRUCTURED_HEADING)]
    try:
        result = json.loads(fence.group(1))
    except json.JSONDecodeError as exc:
        raise ContractError(f"structured result is not valid JSON: {exc}") from exc
    return SplitOutput(human, result)


def producer_errors(result: Any) -> tuple[str, ...]:
    """Fail closed per schema-versioning.md section 3, then schema + owner consistency."""
    if not isinstance(result, dict):
        return ("$: structured result is not a JSON object",)
    major, minor, _patch = rv.parse_version(rr.SCHEMA_VERSION)
    decision = rv.consumer_decision(result.get("schema_version"), major, minor)
    if decision is rv.VersionDecision.REJECT_INVALID:
        return ("$.schema_version: missing or not MAJOR.MINOR.PATCH",)
    if decision is rv.VersionDecision.REJECT_UNSUPPORTED_MAJOR:
        return (f"$.schema_version: unsupported major in {result['schema_version']!r}",)
    if decision is rv.VersionDecision.ACCEPT_KNOWN_FIELDS_ONLY:
        return (f"$.schema_version: {result['schema_version']!r} is newer than the published schema",)
    return rr.validate_review_result(result)


def surface_errors(
    result: Mapping, skill: str, known_head: Optional[str], target_committed: bool = True
) -> tuple[str, ...]:
    """Each Skill's structured-output policy for the surface-specific fields."""
    errors: list[str] = []
    state = result["reviewed_state"]
    if result["skill"] != skill:
        errors.append(f"$.skill: {result['skill']!r}, produced by {skill!r}")
    head = state["reviewed_head_sha"]
    if skill == LOCAL:
        expected = known_head if target_committed else None
        if head != expected:
            errors.append(f"$.reviewed_state.reviewed_head_sha: {head!r}, workspace gives {expected!r}")
        if state["completeness"] != "full":
            errors.append("$.reviewed_state.completeness: a local review is always 'full'")
        if state["prior_reviewed_sha"] is not None:
            errors.append("$.reviewed_state.prior_reviewed_sha: a stateless local review has none")
    elif head is None:
        if result["coverage"] != "incomplete":
            errors.append("$.reviewed_state.reviewed_head_sha: null only when the review is incomplete")
    elif head != known_head:
        errors.append(f"$.reviewed_state.reviewed_head_sha: {head!r}, PR head is {known_head!r}")
    return tuple(errors)


def shared_projection(result: Mapping) -> dict:
    """The result with its surface-specific fields removed."""
    return {key: value for key, value in result.items() if key not in SURFACE_SPECIFIC_FIELDS}


def parse_human_report(text: str, skill: str) -> HumanReport:
    decision = _DECISION.search(text)
    coverage = _COVERAGE[skill].search(text)
    head = _HEAD[skill].search(text)
    return HumanReport(
        decision_label=decision.group(1).strip() if decision else None,
        counts=_counts(text, skill),
        coverage=coverage.group(1) if coverage else None,
        head=head.group(1) if head else None,
        findings=_rendered_findings(text, skill),
    )


def _counts(text: str, skill: str) -> Optional[dict[str, int]]:
    if skill == LOCAL:
        match = _LOCAL_COUNTS.search(text)
        return dict(zip(("p0", "p1", "p2"), map(int, match.groups()))) if match else None
    found = {level.lower(): int(n) for level, n in _GITHUB_COUNT.findall(text)}
    return found if len(found) == 3 else None


def _rendered_findings(text: str, skill: str) -> tuple[RenderedFinding, ...]:
    full = [
        RenderedFinding(m.group(1), m.group(2) or m.group(3), m.group(4), _affected(text, m.end()))
        for m in _FULL_FINDING.finditer(text)
    ]
    if skill == LOCAL:
        return tuple(full)
    # A GitHub pointer line and a body block for the same finding count once.
    pointers = [RenderedFinding(None, m.group(1), m.group(2)) for m in _POINTER_FINDING.finditer(text)]
    in_body = {(f.severity, f.title) for f in full}
    return tuple(full + [p for p in pointers if (p.severity, p.title) not in in_body])


def _affected(text: str, start: int) -> tuple[tuple[str, str], ...]:
    end = _SECTION_END.search(text, start)
    block = text[start : end.start() if end else len(text)]
    listing = _AFFECTED.search(block)
    return tuple(_AFFECTED_ENTRY.findall(listing.group(1))) if listing else ()


def agreement_errors(report: HumanReport, result: Mapping, skill: str) -> tuple[str, ...]:
    """Compares rendered facts with the result; never re-derives the decision."""
    errors: list[str] = []
    label = (report.decision_label or "").split(" — ", 1)[0].strip().upper()
    outcome = RENDERED_OUTCOME[skill].get(label)
    if outcome is None:
        errors.append(f"human report: unrecognized decision label {report.decision_label!r}")
    elif outcome != result["decision"]["outcome"]:
        errors.append(f"decision: report renders {label!r}, result says {result['decision']['outcome']!r}")

    if report.counts != dict(result["counts"]):
        errors.append(f"counts: report {report.counts}, result {dict(result['counts'])}")
    if report.coverage != result["coverage"]:
        errors.append(f"coverage: report {report.coverage!r}, result {result['coverage']!r}")
    head = result["reviewed_state"]["reviewed_head_sha"]
    if head is not None and report.head != head:
        errors.append(f"reviewed head: report {report.head!r}, result {head!r}")

    rendered = Counter((f.severity, f.title) for f in report.findings)
    structured = Counter((f["severity"], f["title"]) for f in result["findings"])
    if rendered != structured:
        errors.append(
            f"findings: only in report {sorted((rendered - structured).elements())}, "
            f"only in result {sorted((structured - rendered).elements())}"
        )
    by_key = {(f["severity"], f["title"]): f for f in result["findings"]}
    for finding in report.findings:
        match = by_key.get((finding.severity, finding.title))
        if match is None:
            continue
        if finding.id is not None and match["id"] != finding.id:
            errors.append(f"finding id: report {finding.id!r}, result {match['id']!r} for {finding.title!r}")
        structured_sites = tuple((a["location"], a["note"]) for a in match.get("affected_locations", ()))
        if finding.affected_locations is not None and finding.affected_locations != structured_sites:
            errors.append(f"affected locations: report {finding.affected_locations}, result {structured_sites}")
    if skill == LOCAL and [f.id for f in report.findings] != [f["id"] for f in result["findings"]]:
        errors.append("findings: result order differs from report order")
    return tuple(errors)


def contract_errors(
    text: str, skill: str, known_head: Optional[str], target_committed: bool = True
) -> tuple[str, ...]:
    """Every check for one emitted output; empty means the output honors the contract."""
    try:
        split = split_output(text, skill)
    except ContractError as exc:
        return (str(exc),)
    if split.result is None:
        return ("structured result was not emitted",)
    errors = producer_errors(split.result)
    if errors:
        return errors
    return surface_errors(split.result, skill, known_head, target_committed) + agreement_errors(
        parse_human_report(split.human, skill), split.result, skill
    )
