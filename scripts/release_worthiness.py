#!/usr/bin/env python3
"""Classify a change set as release-worthy and enforce CHANGELOG coverage.

Classification and CHANGELOG parsing are pure and Git-free so they can be
unit tested; the workflow (.github/workflows/release-worthiness.yml) supplies
the changed-file list (or a base ref to diff against) and acts on the result.

The rule this file encodes is deterministic and intentionally narrow: a
change is release-worthy only when it touches shipped Skill content or the
packaging/distribution path that builds the Skill archives. See
docs/RELEASE.md for the human-facing convention.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

# --- Classification rule -------------------------------------------------
#
# Ordered categories. classify_path() returns the first category whose
# matcher accepts the path; the change set is release-worthy when any path
# lands in a RELEASE_WORTHY_CATEGORIES bucket. Extend by adding a prefix
# or an exact name below — not by adding branching logic elsewhere.

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

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
_BULLET_RE = re.compile(r"^\s*[-*]\s+\S")
_UNRELEASED_HEADING_RE = re.compile(r"^##\s+Unreleased\s*$", re.IGNORECASE)
_VERSION_HEADING_RE = re.compile(r"^##\s+\S")


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
    if p in PACKAGING_FILES:
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


# --- CHANGELOG coverage ------------------------------------------------------


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
    if not _VERSION_RE.match(version):
        raise ValueError(f"version must be X.Y.Z, got {version!r}")
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


# --- Git plumbing ----------------------------------------------------------


def _git(args: Sequence[str], repo_root: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def previous_release_tag(repo_root: Path) -> str | None:
    try:
        out = _git(["describe", "--tags", "--abbrev=0", "--match", "v[0-9]*"], repo_root)
    except subprocess.CalledProcessError:
        return None
    tag = out.strip()
    return tag or None


def changed_files(repo_root: Path, base_ref: str | None) -> list[str]:
    ref = base_ref or previous_release_tag(repo_root)
    if not ref:
        # No prior release to diff against: treat the whole tree as in scope.
        out = _git(["ls-files"], repo_root)
    else:
        out = _git(["diff", "--name-only", f"{ref}...HEAD"], repo_root)
    return [line for line in out.splitlines() if line.strip()]


# --- CLI -----------------------------------------------------------------


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


def _print_human(assessment: Assessment) -> None:
    c = assessment.classification
    verdict = "RELEASE-WORTHY" if c.release_worthy else "not release-worthy"
    print(f"Release worthiness: {verdict}")
    print(f"  reason: {c.reason}")
    if c.triggering:
        print("  release-worthy paths:")
        for path, category in c.triggering:
            print(f"    - {path}  [{category}]")
    if c.release_worthy:
        state = "present" if assessment.changelog_covered else "MISSING"
        print(f"  CHANGELOG 'Unreleased' coverage: {state}")


def _emit_github_output(assessment: Assessment, path: str) -> None:
    c = assessment.classification
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"release_worthy={'true' if c.release_worthy else 'false'}\n")
        handle.write(f"changelog_covered={'true' if assessment.changelog_covered else 'false'}\n")
        handle.write(f"reason={c.reason}\n")


def _cmd_assess(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = Path(args.changelog or repo_root / "CHANGELOG.md")

    if args.changed_file:
        paths: list[str] = list(args.changed_file)
    else:
        paths = changed_files(repo_root, args.base_ref)

    changelog_text = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
    assessment = assess(paths, changelog_text)

    _print_human(assessment)

    github_output = args.github_output or os.environ.get("GITHUB_OUTPUT")
    if github_output:
        _emit_github_output(assessment, github_output)

    if assessment.blocked:
        print()
        severity = "error" if args.require_changelog else "warning"
        print(f"::{severity}::release-worthy change is missing CHANGELOG coverage")
        print(
            "Add an entry under '## Unreleased' in CHANGELOG.md (a concise bullet, "
            "e.g. the PR title with its number). See docs/RELEASE.md."
        )
        if args.require_changelog:
            return 1
    return 0


def _cmd_prepare_changelog(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = Path(args.changelog or repo_root / "CHANGELOG.md")
    today = args.date or _dt.date.today().isoformat()
    text = changelog_path.read_text(encoding="utf-8")
    try:
        updated = roll_unreleased(text, args.version, today)
    except ValueError as exc:
        print(f"::error::{exc}")
        return 1
    if args.check:
        print(updated)
        return 0
    changelog_path.write_text(updated, encoding="utf-8")
    print(f"Rolled '## Unreleased' into '## v{args.version} — {today}' in {changelog_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="repository root (default: cwd)")
    parser.add_argument("--changelog", default=None, help="path to CHANGELOG.md")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("assess", help="classify the change set and check CHANGELOG coverage")
    a.add_argument(
        "--base-ref",
        default=None,
        help="diff HEAD against this ref (default: previous v* tag)",
    )
    a.add_argument(
        "--changed-file",
        action="append",
        default=[],
        metavar="PATH",
        help="explicit changed path (repeatable); skips Git when given",
    )
    a.add_argument(
        "--require-changelog",
        action="store_true",
        help="exit 1 when release-worthy and CHANGELOG coverage is missing",
    )
    a.add_argument("--github-output", default=None, help="path for release_worthy/reason outputs")
    a.set_defaults(func=_cmd_assess)

    p = sub.add_parser(
        "prepare-changelog",
        help="roll '## Unreleased' entries into a versioned heading",
    )
    p.add_argument("--version", required=True, help="target version X.Y.Z")
    p.add_argument("--date", default=None, help="release date YYYY-MM-DD (default: today)")
    p.add_argument("--check", action="store_true", help="print result to stdout, do not write")
    p.set_defaults(func=_cmd_prepare_changelog)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
