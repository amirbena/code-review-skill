"""Release-worthiness assessment domain model.

A pull request's CHANGELOG coverage is its release intent (the PR
description's ``Release category:`` / ``Release entry:`` lines), never a
hand edit to CHANGELOG.md. Hand-curated ``## Unreleased`` bullets remain
allowed, but must stay classifiable. See docs/RELEASE.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from release_lib.changelog import unreleased_has_coverage
from release_lib.classification import Classification, classify_paths
from release_lib.release_intent import ReleaseIntent, ReleaseIntentError, parse_release_intent
from release_lib.semver_policy import AmbiguousReleaseImpact, classify_semver_impact


@dataclass(frozen=True)
class Assessment:
    classification: Classification
    intent: ReleaseIntent | None = None
    intent_problem: str | None = None
    curated_problem: str | None = None
    intent_checked: bool = False

    @property
    def release_worthy(self) -> bool:
        return self.classification.release_worthy

    @property
    def intent_state(self) -> str:
        if not self.intent_checked:
            return "not-checked"
        if self.intent is None:
            return "invalid"
        return "valid" if self.intent.ships_entry else "none"

    @property
    def missing_intent(self) -> str | None:
        """Why a release-worthy PR is not covered, or None when it is (or need not be)."""
        if not (self.intent_checked and self.release_worthy):
            return None
        if self.intent is None:
            return self.intent_problem
        if not self.intent.ships_entry:
            return "'Release category: none' but this change is release-worthy"
        return None

    @property
    def blocked(self) -> bool:
        return self.intent_checked and (self.missing_intent is not None or self.curated_problem is not None)


def _curated_problem(changelog_text: str) -> str | None:
    if not unreleased_has_coverage(changelog_text):
        return None
    try:
        classify_semver_impact(changelog_text)
    except AmbiguousReleaseImpact as exc:
        return str(exc)
    return None


def assess(paths: Iterable[str], changelog_text: str, pr_body: str | None = None) -> Assessment:
    """Classify `paths`; when `pr_body` is given (a PR), also check its release intent."""
    classification = classify_paths(paths)
    curated = _curated_problem(changelog_text)
    if pr_body is None:
        return Assessment(classification, curated_problem=curated)
    try:
        intent = parse_release_intent(pr_body)
    except ReleaseIntentError as exc:
        return Assessment(classification, None, str(exc), curated, True)
    return Assessment(classification, intent, None, curated, True)
