#!/usr/bin/env python3
"""Classify a change set as release-worthy, enforce CHANGELOG coverage, and
drive the deterministic parts of the direct-to-main release flow.

Classification, CHANGELOG parsing, and the release-state comparisons are
pure and side-effect-free so they can be unit tested; the workflow
(.github/workflows/release-worthiness.yml) supplies the changed-file list
or a base ref, and performs the Git/GitHub mutations itself.

Release worthiness is always evaluated over *all* changes since the
previous ``v*`` tag. ``## Unreleased`` is the coverage for that whole
release set, never one entry per pull request. See docs/RELEASE.md.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
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
_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


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


# --- CHANGELOG parsing -----------------------------------------------------


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


# --- Deterministic SemVer classification --------------------------------
#
# The release's bump is decided by the Keep a Changelog `### <Category>`
# headings under `## Unreleased`, never by free judgement. Mapping and the
# highest-impact-wins rule are documented in docs/RELEASE.md.

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

_IMPACT_RANK = {"patch": 1, "minor": 2, "major": 3}

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


# --- Release-state comparisons (pure) ------------------------------------


def validate_semver(version: str) -> None:
    """Accept only `X.Y.Z` with no leading `v` and no pre-release/build parts."""
    if not _VERSION_RE.match(version):
        raise ValueError(f"version must be X.Y.Z with no leading 'v', got {version!r}")


def parse_ref_lines(text: str) -> dict[str, str]:
    """Parse `git ls-remote` output into {ref: sha}. Keeps peeled `^{}` refs."""
    refs: dict[str, str] = {}
    for line in text.splitlines():
        if "\t" not in line:
            continue
        sha, ref = line.split("\t", 1)
        refs[ref.strip()] = sha.strip()
    return refs


def resolved_tag_commit(ls_remote_text: str, version: str) -> str | None:
    """The commit a `v<version>` tag points at, dereferencing an annotated tag.

    Prefers the peeled `refs/tags/v<version>^{}` entry (annotated tag → commit);
    falls back to the bare ref (lightweight tag → commit).
    """
    refs = parse_ref_lines(ls_remote_text)
    return refs.get(f"refs/tags/v{version}^{{}}") or refs.get(f"refs/tags/v{version}")


def release_assets_present(release_json: dict, expected: Sequence[str]) -> bool:
    """True when every expected asset filename is attached to the release."""
    names = {asset.get("name") for asset in release_json.get("assets", [])}
    return set(expected).issubset(names)


# --- Git / GitHub plumbing ---------------------------------------------------


def _git(args: Sequence[str], repo_root: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=True
    )
    return result.stdout


def _gh(args: Sequence[str], repo_root: Path) -> str:
    result = subprocess.run(
        ["gh", *args], cwd=repo_root, capture_output=True, text=True, check=True
    )
    return result.stdout


def previous_release_tag(repo_root: Path) -> str | None:
    try:
        out = _git(["describe", "--tags", "--abbrev=0", "--match", "v[0-9]*"], repo_root)
    except subprocess.CalledProcessError:
        return None
    tag = out.strip()
    return tag or None


def latest_release_tag(repo_root: Path) -> str | None:
    """Highest `vMAJOR.MINOR.PATCH` tag by version order, not commit topology.

    This is the version baseline for automatic releases: the accumulated
    release set is everything since this tag, and the next version is
    derived from it.
    """
    try:
        out = _git(
            ["tag", "--list", "--sort=-v:refname", "v[0-9]*.[0-9]*.[0-9]*"], repo_root
        )
    except subprocess.CalledProcessError:
        return None
    for line in out.splitlines():
        tag = line.strip()
        if tag.startswith("v") and _VERSION_RE.match(tag[1:]):
            return tag
    return None


def changed_files(repo_root: Path, base_ref: str | None) -> list[str]:
    """Repository-relative paths changed between `base_ref` (default: previous
    `v*` tag) and HEAD."""
    ref = base_ref or previous_release_tag(repo_root)
    if not ref:
        # No prior release to diff against: treat the whole tree as in scope.
        out = _git(["ls-files"], repo_root)
    else:
        out = _git(["diff", "--name-only", f"{ref}...HEAD"], repo_root)
    return [line for line in out.splitlines() if line.strip()]


def tag_exists(repo_root: Path, tag: str) -> bool:
    """True when `tag` exists locally or on `origin`."""
    local = {line.strip() for line in _git(["tag", "--list", tag], repo_root).splitlines() if line.strip()}
    if tag in local:
        return True
    try:
        remote = _git(["ls-remote", "--tags", "origin", f"refs/tags/{tag}"], repo_root)
    except subprocess.CalledProcessError:
        remote = ""
    return bool(remote.strip())


# --- CLI: assess -------------------------------------------------------------


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


def _resolve_changelog(args: argparse.Namespace, repo_root: Path) -> Path:
    return Path(args.changelog) if args.changelog else repo_root / "CHANGELOG.md"


def _cmd_assess(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = _resolve_changelog(args, repo_root)

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


# --- CLI: prepare-changelog / changelog-section ----------------------------


def _cmd_prepare_changelog(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = _resolve_changelog(args, repo_root)
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


def _cmd_changelog_section(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = _resolve_changelog(args, repo_root)
    try:
        validate_semver(args.version)
        section = extract_version_section(changelog_path.read_text(encoding="utf-8"), args.version)
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    sys.stdout.write(section)
    return 0


# --- CLI: classify-semver -----------------------------------------------

_SEMVER_FIX_HINT = (
    "Group every '## Unreleased' entry under a recognized '### <Category>' "
    "heading: Added/Changed/Deprecated -> minor, Fixed/Security -> patch, "
    "Removed/Breaking -> major. See docs/RELEASE.md."
)


def _emit_output(path: str | None, **pairs: str) -> None:
    target = path or os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        for key, value in pairs.items():
            handle.write(f"{key}={value}\n")


def _cmd_classify_semver(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = _resolve_changelog(args, repo_root)
    text = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
    try:
        impact = classify_semver_impact(text)
    except AmbiguousReleaseImpact as exc:
        print(f"::{'error' if args.strict else 'warning'}::ambiguous SemVer classification: {exc}")
        print(_SEMVER_FIX_HINT)
        _emit_output(args.github_output, semver_impact="ambiguous")
        return 1 if args.strict else 0
    print(f"Proposed SemVer impact: {impact}")
    _emit_output(args.github_output, semver_impact=impact)
    return 0


# --- CLI: auto-release-plan -------------------------------------------------


def _cmd_auto_release_plan(args: argparse.Namespace) -> int:
    """Decide, from trusted `main`, whether to publish and at which version.

    Exit 0 whether or not a release is due (``should_release`` says which);
    exit 1 only on a hard fault — no baseline tag, or a release-worthy,
    covered set whose SemVer impact is ambiguous (fail closed).
    """
    repo_root = Path(args.repo_root).resolve()
    changelog_path = _resolve_changelog(args, repo_root)

    baseline = latest_release_tag(repo_root)
    if not baseline:
        print("::error::no valid vX.Y.Z release tag to use as the version baseline")
        _emit_output(args.github_output, should_release="false", reason="no release tag baseline")
        return 1

    classification = classify_paths(changed_files(repo_root, baseline))
    if not classification.release_worthy:
        reason = f"no release-worthy changes since {baseline}"
        print(f"No release: {reason}")
        _emit_output(args.github_output, should_release="false", reason=reason, baseline=baseline)
        return 0

    changelog_text = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
    if not unreleased_has_coverage(changelog_text):
        reason = "'## Unreleased' has no entries; the accumulated set is already released"
        print(f"No release: {reason}")
        _emit_output(args.github_output, should_release="false", reason=reason, baseline=baseline)
        return 0

    impact = migration_forced_impact(baseline)
    impact_source = "one-time pre-policy migration"
    if impact is None:
        try:
            impact = classify_semver_impact(changelog_text)
        except AmbiguousReleaseImpact as exc:
            print(f"::error::ambiguous SemVer classification: {exc}")
            print(_SEMVER_FIX_HINT)
            _emit_output(
                args.github_output, should_release="false", ambiguous="true",
                reason=str(exc), baseline=baseline,
            )
            return 1
        impact_source = "CHANGELOG '## Unreleased' categories"

    version = derive_next_version(baseline, impact)
    if tag_exists(repo_root, f"v{version}"):
        reason = f"v{version} already exists; the accumulated set is already released"
        print(f"No release: {reason}")
        _emit_output(
            args.github_output, should_release="false", reason=reason,
            baseline=baseline, version=version, impact=impact,
        )
        return 0

    print(f"Release planned: {baseline} -> v{version} ({impact}, {impact_source}); {classification.reason}")
    _emit_output(
        args.github_output, should_release="true", version=version, impact=impact,
        baseline=baseline, reason=classification.reason,
    )
    return 0


# --- CLI: release-preflight -----------------------------------------------


def _cmd_release_preflight(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = _resolve_changelog(args, repo_root)

    try:
        validate_semver(args.version)
    except ValueError as exc:
        print(f"::error::{exc}")
        return 1
    tag = f"v{args.version}"

    if tag_exists(repo_root, tag):
        print(f"::error::tag {tag} already exists (locally or on origin); choose a new version")
        return 1

    paths = changed_files(repo_root, args.base_ref)
    classification = classify_paths(paths)
    if not classification.release_worthy:
        print(
            "::error::no release-worthy changes since the previous tag "
            f"({previous_release_tag(repo_root) or 'none'}); nothing to release"
        )
        return 1

    changelog_text = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
    if not unreleased_has_coverage(changelog_text):
        print("::error::'## Unreleased' has no release notes; add them before releasing")
        return 1

    print(
        f"Preflight OK: {tag} is new; {classification.reason}; '## Unreleased' has notes"
    )
    return 0


# --- CLI: release-verify -------------------------------------------------


def _cmd_release_verify(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    tag = f"v{args.version}"
    expected = args.expected_sha.strip()
    failures: list[str] = []

    try:
        validate_semver(args.version)
    except ValueError as exc:
        print(f"::error::{exc}")
        return 1
    if not _FULL_SHA_RE.match(expected):
        print(f"::error::--expected-sha must be a full 40-hex commit SHA, got {expected!r}")
        return 1

    try:
        local_commit = _git(["rev-parse", f"{tag}^{{commit}}"], repo_root).strip()
    except subprocess.CalledProcessError:
        local_commit = None
    if local_commit != expected:
        failures.append(f"local tag {tag} resolves to {local_commit or 'nothing'}, expected {expected}")

    remote_tags = _git(
        ["ls-remote", "--tags", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"], repo_root
    )
    remote_commit = resolved_tag_commit(remote_tags, args.version)
    if remote_commit != expected:
        failures.append(f"origin tag {tag} resolves to {remote_commit or 'nothing'}, expected {expected}")

    main_refs = parse_ref_lines(_git(["ls-remote", "origin", "refs/heads/main"], repo_root))
    main_commit = main_refs.get("refs/heads/main")
    if main_commit != expected:
        failures.append(f"origin/main is at {main_commit or 'nothing'}, expected {expected}")

    try:
        release_json = json.loads(
            _gh(["release", "view", tag, "--json", "tagName,targetCommitish,assets"], repo_root)
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        failures.append(f"could not read GitHub Release {tag}: {exc}")
        release_json = None

    if release_json is not None:
        if release_json.get("tagName") != tag:
            failures.append(f"GitHub Release tagName is {release_json.get('tagName')!r}, expected {tag}")
        target = str(release_json.get("targetCommitish", ""))
        if _FULL_SHA_RE.match(target) and target != expected:
            failures.append(f"GitHub Release target is {target}, expected {expected}")
        if not release_assets_present(release_json, args.asset):
            have = sorted(a.get("name") for a in release_json.get("assets", []))
            failures.append(f"GitHub Release assets {have} are missing one of {list(args.asset)}")

    if failures:
        for failure in failures:
            print(f"::error::{failure}")
        return 1
    print(
        f"Verified: {tag} → {expected}; origin/main → {expected}; "
        f"GitHub Release published with assets {list(args.asset)}"
    )
    return 0


# --- parser ------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="repository root (default: cwd)")
    parser.add_argument("--changelog", default=None, help="path to CHANGELOG.md")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("assess", help="classify the change set and check CHANGELOG coverage")
    a.add_argument("--base-ref", default=None, help="diff HEAD against this ref (default: previous v* tag)")
    a.add_argument(
        "--changed-file", action="append", default=[], metavar="PATH",
        help="explicit changed path (repeatable); skips Git when given",
    )
    a.add_argument("--require-changelog", action="store_true", help="exit 1 when release-worthy and coverage is missing")
    a.add_argument("--github-output", default=None, help="path for release_worthy/reason outputs")
    a.set_defaults(func=_cmd_assess)

    p = sub.add_parser("prepare-changelog", help="roll '## Unreleased' entries into a versioned heading")
    p.add_argument("--version", required=True, help="target version X.Y.Z")
    p.add_argument("--date", default=None, help="release date YYYY-MM-DD (default: today)")
    p.add_argument("--check", action="store_true", help="print result to stdout, do not write")
    p.set_defaults(func=_cmd_prepare_changelog)

    s = sub.add_parser("changelog-section", help="print the notes for one version (for GitHub Release body)")
    s.add_argument("--version", required=True, help="version X.Y.Z whose section to print")
    s.set_defaults(func=_cmd_changelog_section)

    cs = sub.add_parser(
        "classify-semver",
        help="print the SemVer impact (patch/minor/major) of the current '## Unreleased'",
    )
    cs.add_argument("--strict", action="store_true", help="exit 1 when the impact is ambiguous")
    cs.add_argument("--github-output", default=None, help="path for the semver_impact output")
    cs.set_defaults(func=_cmd_classify_semver)

    ar = sub.add_parser(
        "auto-release-plan",
        help="from trusted main, decide whether to publish and derive the next version",
    )
    ar.add_argument("--github-output", default=None, help="path for should_release/version/impact outputs")
    ar.set_defaults(func=_cmd_auto_release_plan)

    f = sub.add_parser(
        "release-preflight",
        help="fail closed unless there are release-worthy changes since the previous tag, "
        "'## Unreleased' has notes, and v<version> is a new, valid tag",
    )
    f.add_argument("--version", required=True, help="requested semantic version X.Y.Z")
    f.add_argument("--base-ref", default=None, help="override the since-tag base (default: previous v* tag)")
    f.set_defaults(func=_cmd_release_preflight)

    v = sub.add_parser(
        "release-verify",
        help="verify the live tag, origin/main, and the published GitHub Release all match the release commit",
    )
    v.add_argument("--version", required=True, help="released version X.Y.Z")
    v.add_argument("--expected-sha", required=True, help="the pushed main commit the release must point at")
    v.add_argument("--asset", action="append", default=[], metavar="NAME", help="required release asset filename (repeatable)")
    v.set_defaults(func=_cmd_release_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
