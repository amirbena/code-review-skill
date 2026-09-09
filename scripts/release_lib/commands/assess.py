"""Handler for release-worthiness assessment."""

from __future__ import annotations

import argparse
from pathlib import Path

from release_lib import gitgh
from release_lib.assessment import Assessment, assess
from release_lib.commands.shared import emit_output, resolve_changelog


def _print_human(assessment: Assessment) -> None:
    classification = assessment.classification
    verdict = "RELEASE-WORTHY" if classification.release_worthy else "not release-worthy"
    print(f"Release worthiness: {verdict}")
    print(f"  reason: {classification.reason}")
    if classification.triggering:
        print("  release-worthy paths:")
        for path, category in classification.triggering:
            print(f"    - {path}  [{category}]")
    if classification.release_worthy:
        state = "present" if assessment.changelog_covered else "MISSING"
        print(f"  CHANGELOG 'Unreleased' coverage: {state}")


def cmd_assess(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve()
    changelog_path = resolve_changelog(args, repo_root)
    paths = list(args.changed_file) if args.changed_file else gitgh.changed_files(repo_root, args.base_ref)
    changelog_text = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
    assessment = assess(paths, changelog_text)

    _print_human(assessment)
    emit_output(
        args.github_output,
        release_worthy="true" if assessment.release_worthy else "false",
        changelog_covered="true" if assessment.changelog_covered else "false",
        reason=assessment.classification.reason,
    )

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
