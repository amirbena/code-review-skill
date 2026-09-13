"""``X.Y.Z`` form validation and the patch/minor/major bump arithmetic.

Kept apart from ``semver_policy`` (which maps CHANGELOG categories to a
bump) so the string-shape rules have no dependency on changelog parsing.
Versions are always bare ``X.Y.Z``; the ``v`` prefix belongs only on Git
tags. Pre-release / build metadata is rejected on purpose — this flow
publishes plain releases only.
"""

from __future__ import annotations

import re

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")

_IMPACT_RANK = {"patch": 1, "minor": 2, "major": 3}


def validate_semver(version: str) -> None:
    """Accept only `X.Y.Z` with no leading `v` and no pre-release/build parts."""
    if not _VERSION_RE.match(version):
        raise ValueError(f"version must be X.Y.Z with no leading 'v', got {version!r}")


def derive_next_version(latest_tag: str | None, impact: str) -> str:
    """Next `X.Y.Z` from the latest `vX.Y.Z` tag and a patch/minor/major bump."""
    if impact not in _IMPACT_RANK:
        raise ValueError(f"impact must be patch/minor/major, got {impact!r}")
    if not latest_tag:
        raise ValueError("no vX.Y.Z release tag to derive the next version from")
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", latest_tag.strip())
    if not match:
        raise ValueError(f"latest tag {latest_tag!r} is not a vX.Y.Z release tag")
    major, minor, patch = (int(part) for part in match.groups())
    if impact == "major":
        return f"{major + 1}.0.0"
    if impact == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"
