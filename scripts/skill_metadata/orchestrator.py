"""``validate()`` — run every focused check against one Skill package, in
the order the checks depend on: link containment first, then declared
metadata, then the shared runtime, then the Skill-family-specific layout.
"""

from __future__ import annotations

from pathlib import Path

from .github_family import validate_github_policy_family
from .links import check_markdown_links_resolve, check_no_repo_root_doc_links
from .local_family import validate_local_policy_family
from .metadata import check_skill_metadata
from .shared_resources import check_shared_resources


def validate(skill_root: Path, containment_root: Path) -> None:
    check_no_repo_root_doc_links(skill_root)
    check_markdown_links_resolve(skill_root, containment_root)

    metadata = check_skill_metadata(skill_root, containment_root)
    check_shared_resources(skill_root, containment_root)

    if metadata.get("name") == "github-pr-review":
        validate_github_policy_family(skill_root)
    if metadata.get("name") == "local-code-review":
        validate_local_policy_family(skill_root)
