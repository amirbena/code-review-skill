"""Derive the release bump deterministically from the ``## Unreleased``
``### <Category>`` headings — never from free judgement.

Every pending entry must sit under a recognized Keep a Changelog category;
the highest impact across categories wins. Anything unrecognized or
uncategorized raises :class:`AmbiguousReleaseImpact` so the caller stops
before mutating a tag or release (fail closed) and a maintainer fixes the
section. The category -> bump table and the one-time pre-policy migration
are documented in docs/RELEASE.md and policies/release-changelog-policy.md.
"""

from __future__ import annotations

import re

from release_lib.changelog import _BULLET_RE, _unreleased_body
from release_lib.semver_version import _IMPACT_RANK

SUBSECTION_IMPACT = {
    "added": "minor",
    "changed": "minor",
    "deprecated": "minor",
    "fixed": "patch",
    "security": "patch",
    "removed": "major",
    "breaking": "major",
    "breaking changes": "major",
}

# One-time migration (Issue #113): entries accumulated under `## Unreleased`
# before this contract existed ship as a single PATCH release, whatever
# their categories say. It applies only while the latest release is still
# this baseline; the next release retires it automatically.
PRE_POLICY_BASELINE_TAG = "v1.0.2"

_SUBSECTION_RE = re.compile(r"^###\s+(.+?)\s*$")


class AmbiguousReleaseImpact(ValueError):
    """The `## Unreleased` entries cannot be mapped to a single bump."""


def classify_semver_impact(changelog_text: str) -> str:
    """Return `patch` / `minor` / `major` for the current `## Unreleased`.

    Every entry must sit under a recognized `### <Category>` heading. The
    highest impact across categories wins. Anything unrecognized or
    uncategorized raises AmbiguousReleaseImpact so the caller fails closed.
    """
    body = _unreleased_body(changelog_text)
    if body is None:
        raise AmbiguousReleaseImpact("CHANGELOG.md has no '## Unreleased' section")

    impacts: set[str] = set()
    current: str | None = None
    saw_entry = False
    for line in body:
        heading = _SUBSECTION_RE.match(line)
        if heading:
            current = heading.group(1).strip().lower()
            if current not in SUBSECTION_IMPACT:
                raise AmbiguousReleaseImpact(
                    f"unrecognized '## Unreleased' category '### {heading.group(1).strip()}'"
                )
            continue
        if _BULLET_RE.match(line):
            saw_entry = True
            if current is None:
                raise AmbiguousReleaseImpact(
                    "'## Unreleased' has an entry outside any '### <Category>' heading"
                )
            impacts.add(SUBSECTION_IMPACT[current])
    if not saw_entry:
        raise AmbiguousReleaseImpact("'## Unreleased' has no entries to classify")
    return max(impacts, key=_IMPACT_RANK.__getitem__)


def migration_forced_impact(latest_tag: str | None) -> str | None:
    """`"patch"` while the one-time pre-policy migration applies, else None."""
    return "patch" if latest_tag == PRE_POLICY_BASELINE_TAG else None
