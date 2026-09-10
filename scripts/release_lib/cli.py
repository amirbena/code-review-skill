"""Argument parsing and dispatch for release_worthiness.py."""

from __future__ import annotations

import argparse

from release_lib.commands import (
    cmd_assess,
    cmd_auto_release_plan,
    cmd_changelog_section,
    cmd_classify_semver,
    cmd_prepare_changelog,
    cmd_release_preflight,
    cmd_release_verify,
    cmd_resolve_app_identity,
    cmd_resolve_base_ref,
)

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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=_DESCRIPTION)
    parser.add_argument("--repo-root", default=".", help="repository root (default: cwd)")
    parser.add_argument("--changelog", default=None, help="path to CHANGELOG.md")
    sub = parser.add_subparsers(dest="command", required=True)

    assess = sub.add_parser("assess", help="classify the change set and check CHANGELOG coverage")
    assess.add_argument("--base-ref", default=None, help="diff HEAD against this ref (default: previous v* tag)")
    assess.add_argument(
        "--changed-file", action="append", default=[], metavar="PATH",
        help="explicit changed path (repeatable); skips Git when given",
    )
    assess.add_argument(
        "--require-changelog", action="store_true",
        help="exit 1 when release-worthy and coverage is missing",
    )
    assess.add_argument("--github-output", default=None, help="path for release_worthy/reason outputs")
    assess.set_defaults(func=cmd_assess)

    prepare = sub.add_parser("prepare-changelog", help="roll '## Unreleased' entries into a versioned heading")
    prepare.add_argument("--version", required=True, help="target version X.Y.Z")
    prepare.add_argument("--date", default=None, help="release date YYYY-MM-DD (default: today)")
    prepare.add_argument("--check", action="store_true", help="print result to stdout, do not write")
    prepare.set_defaults(func=cmd_prepare_changelog)

    section = sub.add_parser("changelog-section", help="print the notes for one version (for GitHub Release body)")
    section.add_argument("--version", required=True, help="version X.Y.Z whose section to print")
    section.set_defaults(func=cmd_changelog_section)

    classify = sub.add_parser(
        "classify-semver",
        help="print the SemVer impact (patch/minor/major) of the current '## Unreleased'",
    )
    classify.add_argument("--strict", action="store_true", help="exit 1 when the impact is ambiguous")
    classify.add_argument("--github-output", default=None, help="path for the semver_impact output")
    classify.set_defaults(func=cmd_classify_semver)

    plan = sub.add_parser(
        "auto-release-plan",
        help="from trusted main, decide whether to publish and derive the next version",
    )
    plan.add_argument("--github-output", default=None, help="path for should_release/version/impact outputs")
    plan.set_defaults(func=cmd_auto_release_plan)

    preflight = sub.add_parser(
        "release-preflight",
        help="fail closed unless there are release-worthy changes since the previous tag, "
        "'## Unreleased' has notes, and v<version> is a new, valid tag",
    )
    preflight.add_argument("--version", required=True, help="requested semantic version X.Y.Z")
    preflight.add_argument("--base-ref", default=None, help="override the since-tag base (default: previous v* tag)")
    preflight.set_defaults(func=cmd_release_preflight)

    verify = sub.add_parser(
        "release-verify",
        help="verify the live tag, origin/main, and the published GitHub Release all match the release commit",
    )
    verify.add_argument("--version", required=True, help="released version X.Y.Z")
    verify.add_argument("--expected-sha", required=True, help="the pushed main commit the release must point at")
    verify.add_argument(
        "--asset", action="append", default=[], metavar="NAME",
        help="required release asset filename (repeatable)",
    )
    verify.set_defaults(func=cmd_release_verify)

    base_ref = sub.add_parser(
        "resolve-base-ref",
        help="print the diff base the assess job classifies against "
        "(merge-base with the PR's current base branch, or previous v* tag)",
    )
    base_ref.add_argument("--event-name", required=True, help="the triggering GitHub event (github.event_name)")
    base_ref.add_argument(
        "--pr-base-ref", default="",
        help="pull_request.base.ref branch name; its fetched origin/<ref> tip is the fork point (pull_request only)",
    )
    base_ref.add_argument(
        "--pr-base-sha", default="",
        help="pull_request.base.sha; fallback fork point when origin/<pr-base-ref> is unavailable (pull_request only)",
    )
    base_ref.add_argument("--github-output", default=None, help="path for the ref output")
    base_ref.set_defaults(func=cmd_resolve_base_ref)

    app_identity = sub.add_parser(
        "resolve-app-identity",
        help="resolve the release-commit Git identity from the minted release App's slug; fails closed with no fallback",
    )
    app_identity.add_argument("--app-slug", required=True, help="app-slug from actions/create-github-app-token")
    app_identity.add_argument("--github-output", default=None, help="path for the login/email outputs")
    app_identity.set_defaults(func=cmd_resolve_app_identity)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
