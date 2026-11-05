"""What a v3 Skill's frontmatter may declare and which repository documents a
Skill must never link to."""

from __future__ import annotations

# A v3 Skill declares only these fields. `version` is absent on `release/v3`
# until the release run stamps it (ADR 11), so it is allowed, never required.
PORTABLE_FRONTMATTER_FIELDS = {"name", "version", "description"}

# A Skill never depends on this repo's own dev docs or its
# repository-development policies/. Any link to one of these basenames, at
# any depth, is a boundary violation.
REPO_ROOT_ONLY_DOC_BASENAMES = {
    "AGENTS.md",
    "ARCHITECTURE.md",
    "README.md",
    "repository-workflow.md",
    "git-pr-merge-policy.md",
    "validation-and-clean-exit.md",
    "documentation-policy.md",
    "skill-development-policy.md",
    "review-orchestration-policy.md",
    "python_scripts_coding_policy.md",
}
