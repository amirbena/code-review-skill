"""Parse CHANGELOG.md, roll ``## Unreleased`` at release time, and pull a
single version's notes for the GitHub Release body.

``## Unreleased`` is the accumulated coverage for *every* change since the
last ``v*`` tag — not one entry per pull request — so "has coverage" means
the whole pending release set is described, and the roll moves that whole
block under one version heading. A missing heading counts as no coverage
(fail closed) rather than an error, so the assess check can report it
with an actionable message. See docs/RELEASE.md.
"""

from __future__ import annotations

import re

from release_lib.semver_version import validate_semver

_BULLET_RE = re.compile(r"^\s*[-*]\s+\S")
_UNRELEASED_HEADING_RE = re.compile(r"^##\s+Unreleased\s*$", re.IGNORECASE)
_VERSION_HEADING_RE = re.compile(r"^##\s+\S")


def _unreleased_body(changelog_text: str) -> list[str] | None:
    """Lines under the `## Unreleased` heading, or None if the heading is absent."""
    lines = changelog_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if _UNRELEASED_HEADING_RE.match(line):
            start = i + 1
            break
    if start is None:
        return None
    body: list[str] = []
    for line in lines[start:]:
        if _VERSION_HEADING_RE.match(line):
            break
        body.append(line)
    return body


def unreleased_has_coverage(changelog_text: str) -> bool:
    """True when the `## Unreleased` section lists at least one real entry.

    A bullet line counts; the italic placeholder does not. A missing
    `## Unreleased` heading counts as no coverage (fail closed).
    """
    body = _unreleased_body(changelog_text)
    if body is None:
        return False
    return any(_BULLET_RE.match(line) for line in body)


def roll_unreleased(changelog_text: str, version: str, today: str) -> str:
    """Move the `## Unreleased` entries under a `## v<version> — <today>`
    heading and leave a fresh empty `Unreleased` placeholder above it."""
    validate_semver(version)
    body = _unreleased_body(changelog_text)
    if body is None:
        raise ValueError("CHANGELOG.md has no '## Unreleased' section")
    if not any(_BULLET_RE.match(line) for line in body):
        raise ValueError("'## Unreleased' has no entries to roll into a release")

    lines = changelog_text.splitlines()
    heading_idx = next(i for i, line in enumerate(lines) if _UNRELEASED_HEADING_RE.match(line))
    body_end = heading_idx + 1 + len(body)

    # Keep the section's internal shape (### subsections, spacing); only
    # drop blank lines that top-and-tail it.
    trimmed = list(body)
    while trimmed and not trimmed[0].strip():
        trimmed.pop(0)
    while trimmed and not trimmed[-1].strip():
        trimmed.pop()

    placeholder = [
        "## Unreleased",
        "",
        "_Nothing yet. New entries land here and move under a version heading at",
        "release time._",
        "",
    ]
    released = [f"## v{version} — {today}", "", *trimmed, ""]
    new_lines = lines[:heading_idx] + placeholder + released + lines[body_end:]
    text = "\n".join(new_lines)
    if changelog_text.endswith("\n") and not text.endswith("\n"):
        text += "\n"
    return text


def has_version_section(changelog_text: str, version: str) -> bool:
    """True when CHANGELOG.md already has a `## v<version>` heading."""
    heading = re.compile(rf"^##\s+v{re.escape(version)}(\s|$)")
    return any(heading.match(line) for line in changelog_text.splitlines())


def extract_version_section(changelog_text: str, version: str) -> str:
    """Return the notes under `## v<version> — …`, up to the next `## ` heading.

    Used to keep the GitHub Release body consistent with CHANGELOG.md.
    """
    heading = re.compile(rf"^##\s+v{re.escape(version)}(\s|$|\s+—)")
    lines = changelog_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if heading.match(line):
            start = i + 1
            break
    if start is None:
        raise ValueError(f"CHANGELOG.md has no '## v{version}' section")
    out: list[str] = []
    for line in lines[start:]:
        if _VERSION_HEADING_RE.match(line):
            break
        out.append(line)
    return "\n".join(out).strip() + "\n"
