"""Release-worthiness assessment domain model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from release_lib.changelog import unreleased_has_coverage
from release_lib.classification import Classification, classify_paths


@dataclass(frozen=True)
class Assessment:
    classification: Classification
    changelog_covered: bool

    @property
    def release_worthy(self) -> bool:
        return self.classification.release_worthy

    @property
    def blocked(self) -> bool:
        return self.release_worthy and not self.changelog_covered


def assess(paths: Iterable[str], changelog_text: str) -> Assessment:
    classification = classify_paths(paths)
    return Assessment(classification, unreleased_has_coverage(changelog_text))
