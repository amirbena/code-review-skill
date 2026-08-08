#!/usr/bin/env python3
"""Validate Skill discovery metadata and declared package resources."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

try:
    import yaml
except ImportError as exc:  # pragma: no cover - environment prerequisite
    raise SystemExit("error: PyYAML is required for Skill metadata validation") from exc


RESOURCE_FIELDS = ("shared", "resources", "config")


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


def validate(skill_root: Path, containment_root: Path) -> None:
    skill_md = skill_root / "SKILL.md"
    metadata_path = skill_root / "metadata" / "skill.yaml"
    frontmatter = load_frontmatter(skill_md)
    metadata = load_yaml(metadata_path)

    for field in ("name", "description"):
        if not frontmatter.get(field):
            raise SystemExit(f"error: {skill_md} frontmatter missing {field!r}")
        if metadata.get(field) != frontmatter[field]:
            raise SystemExit(
                f"error: {metadata_path} {field} does not exactly match SKILL.md frontmatter"
            )

    entrypoint = metadata.get("entrypoint")
    if not isinstance(entrypoint, str) or not entrypoint:
        raise SystemExit(f"error: {metadata_path} missing string entrypoint")
    entrypoint_path = require_inside(skill_root / entrypoint, containment_root, "entrypoint")
    if not entrypoint_path.is_file():
        raise SystemExit(f"error: metadata entrypoint does not exist: {entrypoint_path}")

    for field in RESOURCE_FIELDS:
        if field not in metadata:
            continue
        for nested_field, declared in iter_paths(metadata[field], field):
            target = require_inside(metadata_path.parent / declared, containment_root, nested_field)
            if not target.exists():
                raise SystemExit(
                    f"error: metadata path {nested_field} does not exist: {declared}"
                )

    if metadata.get("name") == "github-pr-review":
        policy = (skill_root / "policies" / "github-review.md").read_text(encoding="utf-8")
        runbook = (skill_root / "runbooks" / "active-pr-review.md").read_text(encoding="utf-8")
        required_policy = (
            "## Self-review capability",
            "authenticated reviewer is the PR author",
            "Final GitHub approval was not submitted",
            "never fabricate a successful",
        )
        for marker in required_policy:
            if marker not in policy:
                raise SystemExit(f"error: GitHub self-review policy missing marker: {marker!r}")
        author_step = runbook.find("resolve PR author")
        access_step = runbook.find("verify repository/review access")
        capability_step = runbook.find("determine self-review submission capability")
        decision_step = runbook.find("submit permitted Approve/Request Changes")
        if not (0 <= author_step < access_step < capability_step < decision_step):
            raise SystemExit(
                "error: active review flow must check PR-author identity and self-review "
                "capability before a formal review decision"
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_root", type=Path)
    parser.add_argument("--containment-root", type=Path)
    args = parser.parse_args()
    root = args.skill_root.resolve()
    containment = (args.containment_root or root).resolve()
    validate(root, containment)


if __name__ == "__main__":
    main()
