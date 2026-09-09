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


def check_markers(text: str, markers: tuple[str, ...], label: str) -> None:
    normalized = normalize_prose(text)
    for marker in markers:
        if normalize_prose(marker) not in normalized:
            raise SystemExit(f"error: {label} missing marker: {marker!r}")


def check_order(text: str, headers: tuple[str, ...], label: str) -> None:
    """Assert each header in `headers` appears, strictly in that order."""
    positions = [text.find(h) for h in headers]
    if any(p < 0 for p in positions) or positions != sorted(positions):
        raise SystemExit(
            f"error: {label} must present {list(headers)} in that exact order"
        )


def check_absent(text: str, phrases: tuple[str, ...], label: str) -> None:
    for phrase in phrases:
        if phrase in text:
            raise SystemExit(
                f"error: {label} must not restate owned section {phrase!r} — "
                "reference the canonical sub-policy file instead of duplicating it"
            )


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


def iter_paths(value: object, field: str):
    if isinstance(value, str):
        yield field, value
    elif isinstance(value, list):
        for item in value:
            yield from iter_paths(item, field)
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from iter_paths(item, f"{field}.{key}")
    elif value is not None:
        raise SystemExit(f"error: metadata resource field {field} must contain paths")


def require_inside(path: Path, root: Path, label: str) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise SystemExit(f"error: {label} escapes root {root}: {path}") from exc
    return resolved
