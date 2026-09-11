"""Containment and resolution checks for Markdown links inside a Skill
package and across tracked repository Markdown. A distributed archive must
be self-contained: no link may point at this repository's own docs, and
every relative link must resolve.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from ._support import MARKDOWN_LINK_RE, require_inside
from .expectations import REPO_ROOT_ONLY_DOC_BASENAMES


@dataclass(frozen=True)
class BrokenMarkdownLink:
    source: Path
    line: int
    target: str


def iter_markdown_links(text: str) -> Iterator[tuple[int, str]]:
    for line_no, line in enumerate(text.splitlines(), start=1):
        for link in MARKDOWN_LINK_RE.findall(line):
            yield line_no, link


def resolve_local_markdown_link(
    md_file: Path, link: str, containment_root: Path
) -> Path | None:
    if link.startswith(("http://", "https://", "mailto:")):
        return None
    target = link.split("#", 1)[0].strip()
    if not target:
        return None
    return require_inside(
        md_file.parent / target, containment_root, f"{md_file} link {link!r}"
    )


def find_broken_markdown_links(
    md_files: Iterable[Path],
    containment_root: Path,
    *,
    require_file: bool = False,
) -> list[BrokenMarkdownLink]:
    broken: list[BrokenMarkdownLink] = []
    root = containment_root.resolve()
    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        for line_no, link in iter_markdown_links(text):
            resolved = resolve_local_markdown_link(md_file, link, root)
            if resolved is None:
                continue
            missing = not resolved.is_file() if require_file else not resolved.exists()
            if missing:
                broken.append(BrokenMarkdownLink(md_file, line_no, link))
    return broken


def tracked_markdown_files(repo_root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        capture_output=True,
        check=True,
    )
    paths = [path for path in result.stdout.decode().split("\0") if path.endswith(".md")]
    return sorted(repo_root / path for path in paths)


def check_repository_markdown_links(
    repo_root: Path, md_files: Iterable[Path] | None = None
) -> None:
    root = repo_root.resolve()
    files = list(md_files) if md_files is not None else tracked_markdown_files(root)
    broken = find_broken_markdown_links(files, root)
    if not broken:
        return
    for item in broken:
        try:
            rel = item.source.relative_to(root)
        except ValueError:
            rel = item.source
        print(
            f"error: {rel}:{item.line}: broken link {item.target!r}",
            file=sys.stderr,
        )
    raise SystemExit(1)


def check_no_repo_root_doc_links(skill_root: Path) -> None:
    """Reject packaged links to this repository's own root-level docs, at
    any relative depth — a distributed archive never contains them."""
    for md_file in sorted(skill_root.rglob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        for _line_no, link in iter_markdown_links(text):
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
    broken = find_broken_markdown_links(
        sorted(skill_root.rglob("*.md")), containment_root, require_file=True
    )
    if not broken:
        return
    item = broken[0]
    resolved = resolve_local_markdown_link(item.source, item.target, containment_root)
    raise SystemExit(
        f"error: {item.source} links to a missing file: {item.target!r} -> {resolved}"
    )
