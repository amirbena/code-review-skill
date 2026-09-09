"""Handlers for SemVer classification and automatic release planning."""

from __future__ import annotations

import argparse
from pathlib import Path

from release_lib import gitgh
from release_lib.changelog import unreleased_has_coverage
from release_lib.classification import classify_paths
from release_lib.commands.shared import emit_output, resolve_changelog
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
        reason = f"no release-worthy changes since {baseline}"
        print(f"No release: {reason}")
        emit_output(args.github_output, should_release="false", reason=reason, baseline=baseline)
        return 0

    changelog_text = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
    if not unreleased_has_coverage(changelog_text):
        reason = "'## Unreleased' has no entries; the accumulated set is already released"
        print(f"No release: {reason}")
        emit_output(args.github_output, should_release="false", reason=reason, baseline=baseline)
        return 0

    impact = migration_forced_impact(baseline)
    impact_source = "one-time pre-policy migration"
    if impact is None:
        try:
            impact = classify_semver_impact(changelog_text)
        except AmbiguousReleaseImpact as exc:
            print(f"::error::ambiguous SemVer classification: {exc}")
            print(_SEMVER_FIX_HINT)
            emit_output(
                args.github_output,
                should_release="false",
                ambiguous="true",
                reason=str(exc),
                baseline=baseline,
            )
            return 1
        impact_source = "CHANGELOG '## Unreleased' categories"

    version = derive_next_version(baseline, impact)
    if gitgh.tag_exists(repo_root, f"v{version}"):
        reason = f"v{version} already exists; the accumulated set is already released"
        print(f"No release: {reason}")
        emit_output(
            args.github_output,
            should_release="false",
            reason=reason,
            baseline=baseline,
            version=version,
            impact=impact,
        )
        return 0

    print(f"Release planned: {baseline} -> v{version} ({impact}, {impact_source}); {classification.reason}")
    emit_output(
        args.github_output,
        should_release="true",
        version=version,
        impact=impact,
        baseline=baseline,
        reason=classification.reason,
    )
    return 0
