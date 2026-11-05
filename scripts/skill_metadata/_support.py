"""Generic assertion helpers and loaders shared by the focused checkers.

These carry no Skill-specific knowledge: the concrete markers, orders and
field names live in ``expectations``; the callers live in the sibling
checker modules.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment prerequisite
    raise SystemExit("error: PyYAML is required for Skill metadata validation") from exc

MARKDOWN_LINK_RE = re.compile(r"\]\(([^)]+)\)")
WHITESPACE_RE = re.compile(r"\s+")


def normalize_prose(text: str) -> str:
    """Collapse whitespace so marker checks survive Markdown reflow."""
    return WHITESPACE_RE.sub(" ", text).strip()





def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise SystemExit(f"error: cannot parse YAML {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"error: expected a YAML mapping in {path}")
    return data


def load_frontmatter(skill_md: Path) -> dict:
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise SystemExit(f"error: {skill_md} must start with YAML frontmatter")
    try:
        closing = lines.index("---", 1)
    except ValueError as exc:
        raise SystemExit(f"error: {skill_md} has no closing frontmatter delimiter") from exc
    try:
        data = yaml.safe_load("\n".join(lines[1:closing])) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f"error: cannot parse frontmatter in {skill_md}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"error: expected a frontmatter mapping in {skill_md}")
    return data


def require_single_line_scalar(skill_md: Path, field: str) -> None:
    """Assert `field:` in `skill_md`'s frontmatter is a plain scalar written
    on exactly one physical YAML line — no block/folded scalar (`>`/`|`
    indicator) and no continuation line.
    """
    lines = skill_md.read_text(encoding="utf-8").splitlines()
    closing = lines.index("---", 1)
    body_lines = lines[1:closing]
    field_idx = next(
        (i for i, line in enumerate(body_lines) if line.startswith(f"{field}:")),
        None,
    )
    if field_idx is None:
        raise SystemExit(f"error: {skill_md} frontmatter missing {field!r}")
    value = body_lines[field_idx][len(field) + 1 :].strip()
    if not value or value[0] in ("|", ">"):
        raise SystemExit(
            f"error: {skill_md} {field!r} must be a plain scalar on one "
            "physical YAML line, not a block/folded scalar"
        )
    following = body_lines[field_idx + 1] if field_idx + 1 < len(body_lines) else ""
    if following[:1].isspace():
        raise SystemExit(
            f"error: {skill_md} {field!r} must be a single physical line "
            "with no continuation line"
        )



def require_inside(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise SystemExit(f"error: {label} escapes root {root}: {path}") from exc
    return resolved
