"""Containment and resolution checks for Markdown links inside a Skill
package. A distributed archive must be self-contained: no link may point
at this repository's own docs, and every relative link must resolve.
"""

from __future__ import annotations

from pathlib import Path

from ._support import MARKDOWN_LINK_RE, require_inside
from .expectations import REPO_ROOT_ONLY_DOC_BASENAMES


def check_no_repo_root_doc_links(skill_root: Path) -> None:
    """Reject packaged links to this repository's own root-level docs, at
    any relative depth — a distributed archive never contains them."""
    for md_file in sorted(skill_root.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        for link in MARKDOWN_LINK_RE.findall(text):
            if link.startswith(("http://", "https://")):
                continue
            target = link.split("#", 1)[0].strip()
            if not target:
                continue
            basename = Path(target).name
            if basename in REPO_ROOT_ONLY_DOC_BASENAMES:
                raise SystemExit(
                    f"error: {md_file} contains a packaged link to "
                    f"repository-root {basename!r} ({link!r}); a distributed "
                    "Skill must be self-contained and must not depend on "
                    "source-repository documentation"
                )


def check_markdown_links_resolve(skill_root: Path, containment_root: Path) -> None:
    """Every local relative Markdown link must resolve to a real file.

    Catches stale references left behind by a rename/move (e.g. a policy
    split) that marker checks alone would not detect.
    """
    for md_file in sorted(skill_root.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        for link in MARKDOWN_LINK_RE.findall(text):
            if link.startswith(("http://", "https://", "mailto:")):
                continue
            target = link.split("#", 1)[0].strip()
            if not target:
                continue
            resolved = require_inside(
                md_file.parent / target, containment_root, f"{md_file} link {link!r}"
            )
            if not resolved.is_file():
                raise SystemExit(
                    f"error: {md_file} links to a missing file: {link!r} -> {resolved}"
                )
