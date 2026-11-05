"""``validate()`` -- run every check against one Skill folder: link
containment first, then the frontmatter contract."""

from __future__ import annotations

from pathlib import Path

from .frontmatter import check_frontmatter
from .links import check_markdown_links_resolve, check_no_repo_root_doc_links


def validate(skill_root: Path, containment_root: Path) -> None:
    check_no_repo_root_doc_links(skill_root)
    check_markdown_links_resolve(skill_root, containment_root)
    check_frontmatter(skill_root)
