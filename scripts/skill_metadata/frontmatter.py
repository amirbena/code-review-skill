"""SKILL.md frontmatter contract for a v3 Skill: `name` (equal to its folder
name) and a one-line `description`; `version` is optional and strict x.y.z."""

from __future__ import annotations

import re
from pathlib import Path

from ._support import load_frontmatter, require_single_line_scalar
from .expectations import PORTABLE_FRONTMATTER_FIELDS

_VERSION_RE = re.compile(r"^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$")


def check_frontmatter(skill_root: Path) -> dict:
    skill_md = skill_root / "SKILL.md"
    if not skill_md.is_file():
        raise SystemExit(f"error: missing SKILL.md in {skill_root}")
    frontmatter = load_frontmatter(skill_md)

    unexpected = set(frontmatter) - PORTABLE_FRONTMATTER_FIELDS
    if unexpected:
        raise SystemExit(
            f"error: {skill_md} has non-portable frontmatter field(s): {', '.join(sorted(unexpected))}"
        )
    for field in ("name", "description"):
        if not frontmatter.get(field):
            raise SystemExit(f"error: {skill_md} frontmatter missing {field!r}")
    if frontmatter["name"] != skill_root.name:
        raise SystemExit(
            f"error: {skill_md} name {frontmatter['name']!r} must equal its folder name {skill_root.name!r}"
        )
    require_single_line_scalar(skill_md, "description")

    version = frontmatter.get("version")
    if version is not None and (not isinstance(version, str) or not _VERSION_RE.match(version)):
        raise SystemExit(
            f"error: {skill_md} frontmatter 'version' must be strict x.y.z "
            f"(no 'v' prefix, no leading zeros): got {version!r}"
        )
    return frontmatter
