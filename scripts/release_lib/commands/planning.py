"""Handlers for SemVer classification and automatic release planning."""

from __future__ import annotations

import argparse
from pathlib import Path

from release_lib import gitgh
from release_lib.changelog import _unreleased_body, has_version_section, unreleased_has_coverage
from release_lib.changelog_generation import ChangelogGenerationError, generate_changelog
from release_lib.classification import classify_paths
from release_lib.commands.changelog import INTENT_FIX_HINT
from release_lib.commands.shared import emit_output, fenced, resolve_changelog, write_step_summary
from release_lib.semver_policy import (
    AmbiguousReleaseImpact,
    classify_semver_impact,
    migration_forced_impact,
)
from release_lib.semver_version import derive_next_version

_SEMVER_FIX_HINT = (
    "Group every '## Unreleased' entry under a recognized '### <Category>' "
    "heading: Added/Changed/Deprecated -> minor, Fixed/Security -> patch, "
    "Removed/Breaking -> major. See docs/RELEASE.md."
)


def cmd_classify_semver(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = resolve_changelog(args, repo_root)
    text = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
    try:
        impact = classify_semver_impact(text)
    except AmbiguousReleaseImpact as exc:
        print(f"::{'error' if args.strict else 'warning'}::ambiguous SemVer classification: {exc}")
        print(_SEMVER_FIX_HINT)
        emit_output(args.github_output, semver_impact="ambiguous")
        return 1 if args.strict else 0
    print(f"Proposed SemVer impact: {impact}")
    emit_output(args.github_output, semver_impact=impact)
    return 0


def _ambiguous(args: argparse.Namespace, exc: AmbiguousReleaseImpact, baseline: str) -> int:
    print(f"::error::ambiguous SemVer classification: {exc}")
    print(_SEMVER_FIX_HINT)
    emit_output(args.github_output, should_release="false", ambiguous="true", reason=str(exc), baseline=baseline)
    return 1


def _no_release(args: argparse.Namespace, reason: str, **pairs: str) -> int:
    print(f"No release: {reason}")
    emit_output(args.github_output, should_release="false", reason=reason, **pairs)
    return 0


def cmd_auto_release_plan(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = resolve_changelog(args, repo_root)

    baseline = gitgh.latest_release_tag(repo_root)
    if not baseline:
        print("::error::no valid vX.Y.Z release tag to use as the version baseline")
        emit_output(args.github_output, should_release="false", reason="no release tag baseline")
        return 1

    classification = classify_paths(gitgh.changed_files(repo_root, baseline))
    if not classification.release_worthy:
        return _no_release(args, f"no release-worthy changes since {baseline}", baseline=baseline)

    on_disk = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
    try:
        changelog_text = generate_changelog(repo_root, baseline, on_disk)
    except ChangelogGenerationError as exc:
        for problem in exc.problems:
            print(f"::error::{problem}")
        print(INTENT_FIX_HINT)
        emit_output(
            args.github_output,
            should_release="false",
            reason="a merged pull request has missing or invalid release intent",
            baseline=baseline,
        )
        return 1
    except AmbiguousReleaseImpact as exc:
        return _ambiguous(args, exc, baseline)

    if not unreleased_has_coverage(changelog_text):
        return _no_release(
            args, "'## Unreleased' has no entries; the accumulated set is already released", baseline=baseline
        )

    impact = migration_forced_impact(baseline)
    impact_source = "one-time pre-policy migration"
    if impact is None:
        try:
            impact = classify_semver_impact(changelog_text)
        except AmbiguousReleaseImpact as exc:
            return _ambiguous(args, exc, baseline)
        impact_source = "release-intent categories"

    version = derive_next_version(baseline, impact)
    done = {"baseline": baseline, "version": version, "impact": impact}
    if gitgh.tag_exists(repo_root, f"v{version}"):
        return _no_release(args, f"v{version} already exists; the accumulated set is already released", **done)
    if has_version_section(on_disk, version):
        return _no_release(
            args, f"CHANGELOG.md already has v{version}; finish the partially published release by hand", **done
        )

    print(f"Release planned: {baseline} -> v{version} ({impact}, {impact_source}); {classification.reason}")
    emit_output(
        args.github_output,
        should_release="true",
        version=version,
        impact=impact,
        baseline=baseline,
        reason=classification.reason,
    )
    notes = _trim(_unreleased_body(changelog_text) or [])
    write_step_summary(args.step_summary, [f"## Release notes for v{version}", "", *fenced(notes)])
    return 0


def _trim(lines: list[str]) -> list[str]:
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]
