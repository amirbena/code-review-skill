#!/usr/bin/env python3
"""Measure and enforce the useful-content length of a pull-request body, and
validate that its structure still matches the canonical PR template.

Required structure (headings, template-declared optionality, and the labeled
fields that must not be left blank) is derived from
``.github/PULL_REQUEST_TEMPLATE.md`` rather than duplicated here, so the two
stay synchronized; see ``tests/policy/governance/test_pr_description_enforcement.py``
for the drift coverage. ``Release category:``/``Release entry:`` are excluded
from the derived blank-field check: their conditional contract (an entry is
only required when the category is not ``none``) is already owned by
``scripts/release/release_lib/release_intent.py`` (docs/RELEASE.md) and is not
duplicated here.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

PR_BODY_HARD_LIMIT = 6_000

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_PATH = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"

# Labeled "## What" fields whose required-ness is governed elsewhere and must
# not be re-validated here (see module docstring).
_FIELDS_OWNED_ELSEWHERE = frozenset({"release category", "release entry"})

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING_RE = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)
_OPTIONAL_HINT_RE = re.compile(r"\boptional\b", re.IGNORECASE)
_LABELED_FIELD_RE = re.compile(r"^-\s+\*\*(?P<label>[^*]+?):\*\*[ \t]*(?P<value>.*)$", re.MULTILINE)
_FIXES_LINE_RE = re.compile(r"^Fixes #(?P<number>\d*)[ \t]*$", re.MULTILINE | re.IGNORECASE)
_CHECKBOX_RE = re.compile(r"^-\s*\[(?P<mark>[ xX])\]\s*(?P<note>.*)$")
# A guidance stub reads as a phrase ("<short reason>"), unlike a type name
# or HTML tag ("<Item>", "<br>") which has no internal whitespace.
_PLACEHOLDER_TOKEN_RE = re.compile(r"<[A-Za-z][^<>\n]*\s[^<>\n]*>")


def useful_content(body: str | None) -> str:
    """Return normalized Markdown content after removing HTML comments."""
    normalized = (body or "").replace("\r\n", "\n").replace("\r", "\n")
    return _HTML_COMMENT_RE.sub("", normalized).strip()


def measure_body(body: str | None) -> int:
    """Count Unicode code points in normalized useful content."""
    return len(useful_content(body))


@dataclass(frozen=True)
class ValidationResult:
    measured: int
    limit: int

    @property
    def over_by(self) -> int:
        return max(0, self.measured - self.limit)

    @property
    def passes(self) -> bool:
        return self.over_by == 0


def validate_body(body: str | None, limit: int = PR_BODY_HARD_LIMIT) -> ValidationResult:
    return ValidationResult(measured=measure_body(body), limit=limit)


def _split_sections(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Split `text` on '## ' headings into (preamble, [(heading, body), ...])."""
    headings = list(_HEADING_RE.finditer(text))
    preamble = text[: headings[0].start()] if headings else text
    sections = []
    for index, match in enumerate(headings):
        start = match.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
        sections.append((match.group(1).strip(), text[start:end]))
    return preamble, sections


def _labeled_fields(section_body: str) -> dict[str, str]:
    return {
        match.group("label").strip(): match.group("value").strip()
        for match in _LABELED_FIELD_RE.finditer(section_body)
    }


@dataclass(frozen=True)
class TemplateContract:
    """Structure required of a PR body, derived from the canonical template."""

    required_headings: tuple[str, ...]
    optional_headings: tuple[str, ...]
    required_blank_fields: tuple[tuple[str, str], ...]  # (heading, label) pairs


def load_template_contract(template_text: str | None = None) -> TemplateContract:
    """Derive the required structure from `.github/PULL_REQUEST_TEMPLATE.md`."""
    text = template_text if template_text is not None else TEMPLATE_PATH.read_text(encoding="utf-8")
    _, sections = _split_sections(text)

    required_headings = []
    optional_headings = []
    required_blank_fields = []
    for heading, body in sections:
        comment_match = _HTML_COMMENT_RE.search(body)
        hint = comment_match.group(0) if comment_match else ""
        if _OPTIONAL_HINT_RE.search(hint):
            optional_headings.append(heading)
        else:
            required_headings.append(heading)

        for label, default_value in _labeled_fields(body).items():
            if label.lower() in _FIELDS_OWNED_ELSEWHERE:
                continue
            if not default_value:
                required_blank_fields.append((heading, label))

    return TemplateContract(
        required_headings=tuple(required_headings),
        optional_headings=tuple(optional_headings),
        required_blank_fields=tuple(required_blank_fields),
    )


@dataclass(frozen=True)
class StructureIssue:
    section: str
    message: str

    def __str__(self) -> str:
        return f"[{self.section}] {self.message}"


@dataclass(frozen=True)
class StructureResult:
    issues: tuple[StructureIssue, ...] = field(default_factory=tuple)

    @property
    def passes(self) -> bool:
        return not self.issues


def _validation_section_has_content(section_body: str) -> bool:
    for raw_line in section_body.splitlines():
        line = raw_line.strip()
        if not line or line == "-":
            continue
        checkbox = _CHECKBOX_RE.match(line)
        if checkbox:
            if checkbox.group("mark").lower() == "x":
                return True
            continue
        return True
    return False


def validate_structure(body: str | None, contract: TemplateContract | None = None) -> StructureResult:
    """Validate `body` against the canonical PR-template contract.

    Checks required headings are present, required-but-optional headings
    (like "Review") are never falsely demanded, labeled fields the template
    leaves blank are actually filled in, "Fixes #" references a real Issue,
    the "Validation" section carries real content, and no bracketed
    placeholder/guidance stub survives outside an HTML comment.
    """
    contract = contract or load_template_contract()
    visible = useful_content(body)
    issues: list[StructureIssue] = []

    _, sections = _split_sections(visible)
    sections_by_heading = dict(sections)

    for heading in contract.required_headings:
        if heading not in sections_by_heading:
            issues.append(StructureIssue(heading, f"required section '## {heading}' is missing"))

    fixes_match = _FIXES_LINE_RE.search(visible)
    if fixes_match is None:
        issues.append(StructureIssue("Fixes", "a 'Fixes #<issue-number>' line is required"))
    elif not fixes_match.group("number"):
        issues.append(StructureIssue("Fixes", "'Fixes #' must reference a real Issue number"))

    for heading, label in contract.required_blank_fields:
        section_body = sections_by_heading.get(heading)
        if section_body is None:
            continue  # already reported as a missing section
        fields = _labeled_fields(section_body)
        if label not in fields:
            issues.append(StructureIssue(heading, f"required field '{label}:' is missing"))
        elif not fields[label] or _PLACEHOLDER_TOKEN_RE.fullmatch(fields[label]):
            issues.append(StructureIssue(heading, f"required field '{label}:' must not be left blank"))

    if "Validation" in sections_by_heading and "Validation" in contract.required_headings:
        if not _validation_section_has_content(sections_by_heading["Validation"]):
            issues.append(
                StructureIssue("Validation", "must summarize evidence, or state why validation could not run")
            )

    for heading, body_text in sections:
        for match in _PLACEHOLDER_TOKEN_RE.finditer(body_text):
            issues.append(StructureIssue(heading, f"unresolved placeholder left in place: {match.group(0)!r}"))

    return StructureResult(issues=tuple(issues))


def body_from_event(path: Path) -> str | None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    pull_request = payload.get("pull_request")
    if not isinstance(pull_request, dict) or "body" not in pull_request:
        raise ValueError("event payload does not contain pull_request.body")
    body = pull_request["body"]
    if body is not None and not isinstance(body, str):
        raise ValueError("pull_request.body must be a string or null")
    return body


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Enforce the PR body useful-content hard limit and the canonical "
            "PR-template structure from a GitHub event payload."
        )
    )
    parser.add_argument("--event-path", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        body = body_from_event(args.event_path)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"::error title=Cannot validate PR description::{error}")
        return 2

    ok = True

    length_result = validate_body(body)
    if length_result.passes:
        print(
            "PR description useful-content length is "
            f"{length_result.measured:,} code points; hard limit is {length_result.limit:,}."
        )
    else:
        ok = False
        print(
            "::error title=PR description exceeds hard limit::"
            f"Measured {length_result.measured:,} useful-content code points; "
            f"hard limit is {length_result.limit:,}; {length_result.over_by:,} over. "
            "Summarize the change and link to canonical Issues, docs, policies, or "
            "runbooks instead of duplicating detailed requirements or semantics."
        )

    structure_result = validate_structure(body)
    if structure_result.passes:
        print("PR description matches the required .github/PULL_REQUEST_TEMPLATE.md structure.")
    else:
        ok = False
        for issue in structure_result.issues:
            print(f"::error title=PR description does not match the PR template::{issue}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
