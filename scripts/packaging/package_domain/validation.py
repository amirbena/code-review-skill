"""SKILL.md frontmatter structural validation for a staged package.

Guards against a regression stripping/corrupting the Agent Skills YAML
frontmatter of a packaged root ``SKILL.md``. This is a narrow structural
check (line 1 is the opening delimiter, a closing delimiter exists, and
the required ``name``/``description`` fields are present with the
expected ``name``) — not a full YAML validator, and it does not replace
``scripts/validation/validate-skill-metadata.py`` / ``scripts/skill_metadata/``,
which own Skill metadata semantics broadly.

Prefers a real YAML parse when PyYAML is available; otherwise falls back
to the same structural check via regex, matching the previous
Bash/PowerShell fallback behavior.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only without PyYAML installed
    yaml = None  # type: ignore[assignment]


class SkillFrontmatterError(ValueError):
    """Raised when a staged root SKILL.md fails structural frontmatter validation."""


def validate_skill_frontmatter(skill_md_path: Path, expected_name: str) -> None:
    skill_md_path = Path(skill_md_path)
    lines = skill_md_path.read_text(encoding="utf-8").split("\n")

    if not lines or lines[0] != "---":
        raise SkillFrontmatterError(
            f"{skill_md_path} does not start with '---' frontmatter delimiter on line 1"
        )

    try:
        closing_offset = lines[1:].index("---")
    except ValueError:
        raise SkillFrontmatterError(
            f"{skill_md_path} frontmatter has no closing '---' delimiter"
        ) from None

    body_lines = lines[1 : closing_offset + 1]
    fm_body = "\n".join(body_lines)

    if yaml is not None:
        data = yaml.safe_load(fm_body) or {}
        name = data.get("name")
        description = data.get("description")
        if not name:
            raise SkillFrontmatterError(f"{skill_md_path} frontmatter missing required 'name'")
        if not description:
            raise SkillFrontmatterError(
                f"{skill_md_path} frontmatter missing required 'description'"
            )
        if name != expected_name:
            raise SkillFrontmatterError(
                f"{skill_md_path} frontmatter name '{name}' does not match expected "
                f"'{expected_name}'"
            )
        return

    if not re.search(rf"^name:[ \t]*{re.escape(expected_name)}[ \t]*$", fm_body, re.MULTILINE):
        raise SkillFrontmatterError(f"{skill_md_path} frontmatter missing 'name: {expected_name}'")
    if not re.search(r"^description:", fm_body, re.MULTILINE):
        raise SkillFrontmatterError(
            f"{skill_md_path} frontmatter missing required 'description'"
        )
    print(
        f"note: python3 yaml module unavailable — used structural fallback "
        f"validation for {skill_md_path}",
        file=sys.stderr,
    )
