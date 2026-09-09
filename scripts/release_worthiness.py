#!/usr/bin/env python3
"""Classify a change set as release-worthy, enforce CHANGELOG coverage, and
drive the deterministic parts of the direct-to-main release flow.

Thin CLI entrypoint. The flow is split into focused modules under
``release_lib/`` (see ``release_lib/__init__.py`` for the map); this file
only wires ``sys.argv`` to them and re-exports their public names so
existing importers keep working. End-to-end release policy: docs/RELEASE.md.

Release worthiness is always evaluated over *all* changes since the
previous ``v*`` tag. ``## Unreleased`` is the coverage for that whole
release set, never one entry per pull request.
"""

from __future__ import annotations

import sys

from release_lib import gitgh
from release_lib.changelog import (
    extract_version_section,
    roll_unreleased,
    unreleased_has_coverage,
)
from release_lib.classification import (
    Classification,
    classify_path,
    classify_paths,
)
from release_lib.assessment import Assessment, assess
from release_lib.cli import build_parser, main
from release_lib.gitgh import (
    changed_files,
    latest_release_tag,
    previous_release_tag,
    tag_exists,
)
from release_lib.remote_state import (
    parse_ref_lines,
    release_assets_present,
    resolved_tag_commit,
)
from release_lib.semver_policy import (
    PRE_POLICY_BASELINE_TAG,
    SUBSECTION_IMPACT,
    AmbiguousReleaseImpact,
    classify_semver_impact,
    migration_forced_impact,
)
from release_lib.semver_version import derive_next_version, validate_semver

__all__ = [
    "gitgh",
    "Assessment",
    "assess",
    "build_parser",
    "main",
    "Classification",
    "classify_path",
    "classify_paths",
    "extract_version_section",
    "roll_unreleased",
    "unreleased_has_coverage",
    "changed_files",
    "latest_release_tag",
    "previous_release_tag",
    "tag_exists",
    "parse_ref_lines",
    "release_assets_present",
    "resolved_tag_commit",
    "PRE_POLICY_BASELINE_TAG",
    "SUBSECTION_IMPACT",
    "AmbiguousReleaseImpact",
    "classify_semver_impact",
    "migration_forced_impact",
    "derive_next_version",
    "validate_semver",
]


if __name__ == "__main__":
    sys.exit(main())
