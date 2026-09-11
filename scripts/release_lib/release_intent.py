"""Parse a pull request's release-intent lines and render the CHANGELOG
bullet they generate.

A release-worthy PR declares its CHANGELOG entry in its description —
``Release category:`` plus ``Release entry:`` — instead of editing
CHANGELOG.md. Parsing is strict and never guesses at prose; HTML comments
and fenced code are ignored so template guidance and examples never count.
Error messages never echo the contributor's text, so they are safe to pass
through workflow outputs. Contract: docs/RELEASE.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from release_lib.semver_policy import SUBSECTION_IMPACT

NO_RELEASE = "none"

# Accepted category values (matched case-insensitively) -> canonical spelling.
CATEGORY_NAMES = {
    "added": "Added",
    "changed": "Changed",
    "deprecated": "Deprecated",
    "fixed": "Fixed",
    "security": "Security",
    "removed": "Removed",
    "breaking": "Breaking",
    "breaking changes": "Breaking",
    NO_RELEASE: NO_RELEASE,
}

# Order of `### <Category>` sections in a composed `## Unreleased`.
CATEGORY_ORDER = ("Breaking", "Removed", "Added", "Changed", "Deprecated", "Fixed", "Security")

_ALLOWED = "Added, Changed, Deprecated, Fixed, Security, Removed, Breaking, or none"

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[^\n]*$", re.DOTALL | re.MULTILINE)
_FIELD_RE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?\**[ \t]*release[ \t]+(category|entry)\**[ \t]*:[ \t]*\**[ \t]*(.*?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)
_PLACEHOLDER_RE = re.compile(r"<[^>]*>|_No response_|[-–—.…]+|tbd|todo", re.IGNORECASE)
# An entry is one line of prose: it must not open a heading, list, or quote.
_MARKUP_START_RE = re.compile(r"^(?:#|>|[-*+][ \t]|\d+[.)][ \t])")


class ReleaseIntentError(ValueError):
    """The PR description has no usable release intent."""


@dataclass(frozen=True)
class ReleaseIntent:
    category: str  # canonical category, or NO_RELEASE
    entry: str

    @property
    def ships_entry(self) -> bool:
        return self.category != NO_RELEASE

    @property
    def impact(self) -> str | None:
        return SUBSECTION_IMPACT[self.category.lower()] if self.ships_entry else None


def _visible_text(body: str) -> str:
    text = body.replace("\r\n", "\n").replace("\r", "\n")
    return _FENCE_RE.sub("", _HTML_COMMENT_RE.sub("", text))


def parse_release_intent(body: str | None) -> ReleaseIntent:
    """Return the declared intent, or raise ReleaseIntentError (fail closed)."""
    fields: dict[str, str] = {}
    for match in _FIELD_RE.finditer(_visible_text(body or "")):
        key = match.group(1).lower()
        if key in fields:
            raise ReleaseIntentError(f"'Release {key}:' appears more than once in the PR description")
        fields[key] = match.group(2)

    if "category" not in fields:
        raise ReleaseIntentError("the PR description has no 'Release category:' line")
    category = CATEGORY_NAMES.get(fields["category"].strip("`* \t").lower())
    if category is None:
        raise ReleaseIntentError(f"'Release category:' must be one of {_ALLOWED}")
    if category == NO_RELEASE:
        return ReleaseIntent(NO_RELEASE, "")

    entry = fields.get("entry", "").strip()
    if not entry or _PLACEHOLDER_RE.fullmatch(entry):
        raise ReleaseIntentError(f"'Release category: {category}' needs a one-line 'Release entry:'")
    if _MARKUP_START_RE.match(entry):
        raise ReleaseIntentError("'Release entry:' must be one line of prose, not a heading, list item, or quote")
    return ReleaseIntent(category, entry)


def render_bullet(intent: ReleaseIntent, pr_number: int) -> str:
    """The CHANGELOG bullet for `intent`, ending with the PR reference."""
    if not intent.ships_entry:
        raise ValueError("a 'none' release intent renders no CHANGELOG bullet")
    ref = f"(#{pr_number})"
    if ref in intent.entry:
        return f"- {intent.entry}"
    return f"- {intent.entry.rstrip().rstrip('.')} {ref}."
