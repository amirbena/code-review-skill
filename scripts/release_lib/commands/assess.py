"""Handler for release-worthiness assessment.

On a pull request the PR description arrives through an environment
variable (``--pr-body-env``), never as a command-line argument, so
contributor text is not interpolated into a workflow shell step. That text
is written only to the step summary inside a code fence — never to stdout,
where a line could be read as a workflow command, and never to
``$GITHUB_OUTPUT``.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from release_lib import gitgh
from release_lib.assessment import Assessment, assess
from release_lib.commands.shared import emit_output, fenced, resolve_changelog, write_step_summary
from release_lib.release_intent import render_bullet

_INTENT_HINT = (
    "Declare the CHANGELOG entry in the PR description (do not edit CHANGELOG.md):\n"
    "  Release category: <Added|Changed|Deprecated|Fixed|Security|Removed|Breaking>\n"
    "  Release entry: <one line describing the change for users>\n"
    "Editing the description re-runs this check. See docs/RELEASE.md."
)
_CURATED_HINT = (
    "Group every '## Unreleased' entry under a recognized '### <Category>' "
    "heading: Added/Changed/Deprecated -> minor, Fixed/Security -> patch, "
    "Removed/Breaking -> major. See docs/RELEASE.md."
)


def _print_human(assessment: Assessment) -> None:
    classification = assessment.classification
    verdict = "RELEASE-WORTHY" if classification.release_worthy else "not release-worthy"
    print(f"Release worthiness: {verdict}")
    print(f"  reason: {classification.reason}")
    if classification.triggering:
        print("  release-worthy paths:")
        for path, category in classification.triggering:
            print(f"    - {path}  [{category}]")
    intent = assessment.intent
    if intent is not None and intent.ships_entry:
        print(f"  release intent: {intent.category} ({intent.impact})")
    else:
        print(f"  release intent: {assessment.intent_state}")


def _summary(assessment: Assessment, pr_number: int | None) -> list[str]:
    lines = [
        "## Release recommended",
        "",
        "This change affects a Skill or its packaged distribution. It publishes automatically once merged to `main`.",
        "",
        f"- Trigger: {assessment.classification.reason}",
    ]
    intent = assessment.intent
    if intent is not None and intent.ships_entry:
        bullet = render_bullet(intent, pr_number) if pr_number else f"- {intent.entry}"
        lines += [
            f"- Release intent: `{intent.category}` — proposed SemVer impact: **{intent.impact}**",
            "- CHANGELOG entry generated at release (do not edit `CHANGELOG.md`):",
            "",
            *fenced([f"### {intent.category}", "", bullet]),
        ]
    elif assessment.intent_checked:
        lines.append(f"- Release intent: **missing or invalid** — {assessment.missing_intent}")
    else:
        lines.append("- Release intent: not checked (no pull request)")
    return [*lines, "", "See `docs/RELEASE.md`."]


def cmd_assess(args: argparse.Namespace) -> int:
    if args.require_release_intent and not args.pr_body_env:
        print("::error::--require-release-intent needs --pr-body-env; without a PR description there is nothing to enforce")
        return 2
    repo_root = Path(args.repo_root).resolve()
    changelog_path = resolve_changelog(args, repo_root)
    paths = list(args.changed_file) if args.changed_file else gitgh.changed_files(repo_root, args.base_ref)
    changelog_text = changelog_path.read_text(encoding="utf-8") if changelog_path.is_file() else ""
    pr_body = os.environ.get(args.pr_body_env, "") if args.pr_body_env else None
    assessment = assess(paths, changelog_text, pr_body)
    intent = assessment.intent
    ships = intent is not None and intent.ships_entry

    _print_human(assessment)
    emit_output(
        args.github_output,
        release_worthy="true" if assessment.release_worthy else "false",
        release_intent=assessment.intent_state,
        release_category=intent.category if ships else "",
        semver_impact=(intent.impact or "") if ships else "",
        reason=assessment.classification.reason,
    )
    if assessment.release_worthy:
        write_step_summary(args.step_summary, _summary(assessment, args.pr_number))
    elif ships:
        print("::notice::this change is not release-worthy, so its declared release entry will not be generated")

    if not assessment.blocked:
        return 0
    severity = "error" if args.require_release_intent else "warning"
    print()
    if assessment.missing_intent is not None:
        print(f"::{severity}::release-worthy change has no valid release intent: {assessment.missing_intent}")
        print(_INTENT_HINT)
    if assessment.curated_problem is not None:
        print(f"::{severity}::'## Unreleased' in CHANGELOG.md is not classifiable: {assessment.curated_problem}")
        print(_CURATED_HINT)
    return 1 if args.require_release_intent else 0
