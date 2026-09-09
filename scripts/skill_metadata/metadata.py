"""SKILL.md frontmatter portability, the optional OpenAI UI adapter, and
every path a Skill's ``metadata/skill.yaml`` declares — entrypoint plus
the ``shared`` / ``resources`` / ``config`` resource fields.
"""

from __future__ import annotations

from pathlib import Path

from ._support import iter_paths, load_frontmatter, load_yaml, require_inside
from .expectations import (
    OPENAI_INTERFACE_FIELDS,
    PORTABLE_FRONTMATTER_FIELDS,
    RESOURCE_FIELDS,
)


def check_skill_metadata(skill_root: Path, containment_root: Path) -> dict:
    """Validate SKILL.md frontmatter, adapters and declared paths.

    Returns the parsed ``metadata/skill.yaml`` mapping so the orchestrator
    can dispatch the Skill-family-specific checks.
    """
    skill_md = skill_root / "SKILL.md"
    metadata_path = skill_root / "metadata" / "skill.yaml"
    frontmatter = load_frontmatter(skill_md)
    metadata = load_yaml(metadata_path)

    unexpected_frontmatter = set(frontmatter) - PORTABLE_FRONTMATTER_FIELDS
    if unexpected_frontmatter:
        unexpected = ", ".join(sorted(unexpected_frontmatter))
        raise SystemExit(
            f"error: {skill_md} has non-portable frontmatter field(s): {unexpected}"
        )

    for field in ("name", "description"):
        if not frontmatter.get(field):
            raise SystemExit(f"error: {skill_md} frontmatter missing {field!r}")
        if metadata.get(field) != frontmatter[field]:
            raise SystemExit(
                f"error: {metadata_path} {field} does not exactly match SKILL.md frontmatter"
            )

    adapter_path = skill_root / "agents" / "openai.yaml"
    if adapter_path.exists():
        adapter = load_yaml(adapter_path)
        if set(adapter) != {"interface"}:
            raise SystemExit(
                f"error: {adapter_path} must contain only optional UI interface metadata"
            )
        interface = adapter.get("interface")
        if not isinstance(interface, dict) or set(interface) != OPENAI_INTERFACE_FIELDS:
            raise SystemExit(
                f"error: {adapter_path} interface must contain exactly "
                "display_name, short_description, and default_prompt"
            )
        for field in OPENAI_INTERFACE_FIELDS:
            if not isinstance(interface[field], str) or not interface[field]:
                raise SystemExit(
                    f"error: {adapter_path} interface.{field} must be a string"
                )
        short_description = interface["short_description"]
        if not 25 <= len(short_description) <= 64:
            raise SystemExit(
                f"error: {adapter_path} interface.short_description must be 25-64 characters"
            )
        if f"${frontmatter['name']}" not in interface["default_prompt"]:
            raise SystemExit(
                f"error: {adapter_path} interface.default_prompt must mention "
                f"${frontmatter['name']}"
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

    return metadata
