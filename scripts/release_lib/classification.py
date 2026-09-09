"""Classify changed paths and decide whether a change set is release-worthy.

Only shipped Skill content and the files that build the archives justify a
release; everything else (docs, tests, repo policy, CI, maintenance
scripts) does not. The category tables below are the single source of
truth — extend classification by adding a prefix or an exact name here,
never by adding branching logic at a call site. Mapping rationale and the
"what counts as release-worthy" contract: docs/RELEASE.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

# --- Classification rule -------------------------------------------------
#
# Ordered categories. classify_path() returns the first category whose
# matcher accepts the path; the change set is release-worthy when any path
# lands in a RELEASE_WORTHY_CATEGORIES bucket.

# Docs/onboarding that live *inside* an otherwise shipped tree but are not
# themselves packaged into an archive (the packaging allowlists exclude
# every README.md).
NON_SHIPPED_INSIDE_SHIPPED_TREES = ("README.md",)

# Shipped Skill content: everything under skills/ except the carve-out above.
SKILL_CONTENT_ROOT = "skills/"

# Shared review rules packaged into both Skill archives.
SHARED_RUNTIME_ROOT = "shared/"

# Packaging / distribution files that determine what the shipped archives
# contain or whether they build at all.
PACKAGING_FILES = frozenset(
    {
        "scripts/package-skills.sh",
        "scripts/package-skills.ps1",
        "scripts/validate-skill-metadata.py",
    }
)

# Directories whose every file is packaging/distribution machinery (the
# Skill-metadata validator package behind scripts/validate-skill-metadata.py).
PACKAGING_PREFIXES = ("scripts/skill_metadata/",)

# Trees that never, on their own, require a release.
NON_RELEASE_TREES = {
    "tests/": "tests",
    "docs/": "docs",
    "policies/": "repo-policy",
    ".github/": "ci",
    "scripts/": "repo-maintenance",  # non-packaging scripts only; PACKAGING_FILES win first
}

# Root files that are repository maintenance / documentation.
NON_RELEASE_ROOT_FILES = {
    "CHANGELOG.md": "changelog",
    "README.md": "docs",
    "AGENTS.md": "repo-policy",
    "CLAUDE.md": "repo-policy",
    "CONTRIBUTING.md": "docs",
    "SECURITY.md": "docs",
    "LICENSE": "repo-maintenance",
    ".gitignore": "repo-maintenance",
    "requirements-dev.txt": "repo-maintenance",
}

RELEASE_WORTHY_CATEGORIES = frozenset({"skill-content", "shared-runtime", "packaging"})


def _normalize(path: str) -> str:
    p = path.strip().replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def classify_path(path: str) -> str:
    """Return the classification category for one repository-relative path."""
    p = _normalize(path)
    if not p:
        return "empty"

    name = p.rsplit("/", 1)[-1]

    # Packaging files win before the generic scripts/ maintenance bucket.
    if p in PACKAGING_FILES or p.startswith(PACKAGING_PREFIXES):
        return "packaging"

    if p.startswith(SKILL_CONTENT_ROOT):
        if name in NON_SHIPPED_INSIDE_SHIPPED_TREES:
            return "docs"
        return "skill-content"

    if p.startswith(SHARED_RUNTIME_ROOT):
        if name in NON_SHIPPED_INSIDE_SHIPPED_TREES:
            return "docs"
        return "shared-runtime"

    for prefix, category in NON_RELEASE_TREES.items():
        if p.startswith(prefix):
            return category

    if p in NON_RELEASE_ROOT_FILES:
        return NON_RELEASE_ROOT_FILES[p]

    return "unknown"


@dataclass(frozen=True)
class Classification:
    """Outcome of classifying a whole change set."""

    triggering: tuple[tuple[str, str], ...]  # (path, category) that require a release
    other: tuple[tuple[str, str], ...]  # (path, category) that do not

    @property
    def release_worthy(self) -> bool:
        return bool(self.triggering)

    @property
    def reason(self) -> str:
        if not self.triggering:
            return "no shipped Skill content or packaging/distribution files changed"
        categories = sorted({category for _, category in self.triggering})
        sample = ", ".join(path for path, _ in self.triggering[:3])
        more = "" if len(self.triggering) <= 3 else f" (+{len(self.triggering) - 3} more)"
        return f"{'/'.join(categories)} changed: {sample}{more}"


def classify_paths(paths: Iterable[str]) -> Classification:
    triggering: list[tuple[str, str]] = []
    other: list[tuple[str, str]] = []
    for raw in paths:
        p = _normalize(raw)
        if not p:
            continue
        category = classify_path(p)
        if category in RELEASE_WORTHY_CATEGORIES:
            triggering.append((p, category))
        else:
            other.append((p, category))
    return Classification(tuple(triggering), tuple(other))
