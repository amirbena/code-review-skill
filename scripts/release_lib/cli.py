"""Argument parsing and the thin command handlers for release_worthiness.py.

Each ``_cmd_*`` handler is deliberately small: it reads inputs, calls the
focused modules (classification / changelog / semver_policy /
semver_version / remote_state / gitgh), and writes the exact stdout,
``$GITHUB_OUTPUT`` keys, and exit codes the workflow consumes. The
read-only planning boundary is ``auto-release-plan``: it decides *whether*
and *at which version* to release but never mutates anything — the Git and
GitHub mutations are the workflow's ``publish`` job. See docs/RELEASE.md.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from release_lib import gitgh
from release_lib.changelog import (
    extract_version_section,
    roll_unreleased,
    unreleased_has_coverage,
)
from release_lib.classification import Classification, classify_paths
from release_lib.remote_state import (
    _FULL_SHA_RE,
    parse_ref_lines,
    release_assets_present,
    resolved_tag_commit,
)
from release_lib.semver_policy import (
    AmbiguousReleaseImpact,
    classify_semver_impact,
    migration_forced_impact,
)
from release_lib.semver_version import derive_next_version, validate_semver

# Canonical text for the top-level ``--help`` description, rendered verbatim
# by argparse. Kept here (not read from a module docstring) so the CLI's
# user-facing wording has one owner.
_DESCRIPTION = """Classify a change set as release-worthy, enforce CHANGELOG coverage, and
drive the deterministic parts of the direct-to-main release flow.

Classification, CHANGELOG parsing, and the release-state comparisons are
pure and side-effect-free so they can be unit tested; the workflow
(.github/workflows/release-worthiness.yml) supplies the changed-file list
or a base ref, and performs the Git/GitHub mutations itself.

Release worthiness is always evaluated over *all* changes since the
previous ``v*`` tag. ``## Unreleased`` is the coverage for that whole
release set, never one entry per pull request. See docs/RELEASE.md.
"""


# --- assess ---------------------------------------------------------------


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
        paths = gitgh.changed_files(repo_root, args.base_ref)

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


# --- prepare-changelog / changelog-section -------------------------------


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


# --- classify-semver ----------------------------------------------------

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


# --- auto-release-plan -------------------------------------------------------


def _cmd_auto_release_plan(args: argparse.Namespace) -> int:
    """Decide, from trusted `main`, whether to publish and at which version.

    Exit 0 whether or not a release is due (``should_release`` says which);
    exit 1 only on a hard fault — no baseline tag, or a release-worthy,
    covered set whose SemVer impact is ambiguous (fail closed).
    """
    repo_root = Path(args.repo_root).resolve()
    changelog_path = _resolve_changelog(args, repo_root)

    baseline = gitgh.latest_release_tag(repo_root)
    if not baseline:
        print("::error::no valid vX.Y.Z release tag to use as the version baseline")
        _emit_output(args.github_output, should_release="false", reason="no release tag baseline")
        return 1

    classification = classify_paths(gitgh.changed_files(repo_root, baseline))
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
    if gitgh.tag_exists(repo_root, f"v{version}"):
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


# --- release-preflight -----------------------------------------------------


def _cmd_release_preflight(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = _resolve_changelog(args, repo_root)

    try:
        validate_semver(args.version)
    except ValueError as exc:
        print(f"::error::{exc}")
        return 1
    tag = f"v{args.version}"

    if gitgh.tag_exists(repo_root, tag):
        print(f"::error::tag {tag} already exists (locally or on origin); choose a new version")
        return 1

    paths = gitgh.changed_files(repo_root, args.base_ref)
    classification = classify_paths(paths)
    if not classification.release_worthy:
        print(
            "::error::no release-worthy changes since the previous tag "
            f"({gitgh.previous_release_tag(repo_root) or 'none'}); nothing to release"
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


# --- release-verify -------------------------------------------------------


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
        local_commit = gitgh._git(["rev-parse", f"{tag}^{{commit}}"], repo_root).strip()
    except subprocess.CalledProcessError:
        local_commit = None
    if local_commit != expected:
        failures.append(f"local tag {tag} resolves to {local_commit or 'nothing'}, expected {expected}")

    remote_tags = gitgh._git(
        ["ls-remote", "--tags", "origin", f"refs/tags/{tag}", f"refs/tags/{tag}^{{}}"], repo_root
    )
    remote_commit = resolved_tag_commit(remote_tags, args.version)
    if remote_commit != expected:
        failures.append(f"origin tag {tag} resolves to {remote_commit or 'nothing'}, expected {expected}")

    main_refs = parse_ref_lines(gitgh._git(["ls-remote", "origin", "refs/heads/main"], repo_root))
    main_commit = main_refs.get("refs/heads/main")
    if main_commit != expected:
        failures.append(f"origin/main is at {main_commit or 'nothing'}, expected {expected}")

    try:
        release_json = json.loads(
            gitgh._gh(["release", "view", tag, "--json", "tagName,targetCommitish,assets"], repo_root)
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
    parser = argparse.ArgumentParser(description=_DESCRIPTION)
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
