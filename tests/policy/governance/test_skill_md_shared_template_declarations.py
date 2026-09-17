"""Reconciliation guard: each Skill's `SKILL.md` §2 "Required Policy
Loading" section must name (as a Markdown link) every shared *template*
declared in that Skill's own `metadata/skill.yaml` `shared: templates:`
list (issue #406).

`metadata/skill.yaml`'s `shared:` block is a generated projection of
`capabilities/*/capability.yaml` (see
`scripts/packaging/generate_skill_metadata.py`,
`test_generated_skill_metadata.py`). Shared *policies* are legitimately
dispatched only through `shared/policies/review-scope.md`'s own routing
without being re-listed flatly in `SKILL.md` — restating all of them
here would duplicate the router
(`docs/capability-architecture/capability-architecture-model.md` §C.3's
"router becomes the next monolith" risk). Shared *templates* are
different: they define this Skill's own output contract, so `SKILL.md`
§2 names each one explicitly. This is the concrete, narrow check that
would have caught `shared/templates/finding-rendering.md` shipping with
both Skills while being named in neither `SKILL.md`.
"""

from __future__ import annotations

import re
import unittest

import yaml

from tests.support.paths import REPO_ROOT

_SKILLS = {
    "local-code-review": REPO_ROOT / "skills" / "local-code-review",
    "github-pr-review": REPO_ROOT / "skills" / "github-pr-review",
}

_SECTION_HEADING = "## 2. Required Policy Loading"
_NEXT_HEADING_RE = re.compile(r"^## \d", re.MULTILINE)


def _required_policy_loading_section(skill_md_text: str) -> str:
    start = skill_md_text.index(_SECTION_HEADING)
    rest = skill_md_text[start + len(_SECTION_HEADING) :]
    match = _NEXT_HEADING_RE.search(rest)
    return rest[: match.start()] if match else rest


class SkillMdSharedTemplateDeclarationTests(unittest.TestCase):
    def test_every_declared_shared_template_is_named_in_skill_md_section_2(self) -> None:
        for skill_name, skill_root in _SKILLS.items():
            metadata = yaml.safe_load(
                (skill_root / "metadata" / "skill.yaml").read_text(encoding="utf-8")
            )
            templates = metadata.get("shared", {}).get("templates", [])
            self.assertTrue(
                templates, f"{skill_name}'s metadata declares no shared templates"
            )
            skill_md_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
            section = _required_policy_loading_section(skill_md_text)
            for declared in templates:
                basename = declared.rsplit("/", 1)[-1]
                self.assertIn(
                    basename,
                    section,
                    f"{skill_name}/SKILL.md section 2 does not name shared "
                    f"template {basename!r}, declared in metadata/skill.yaml",
                )


if __name__ == "__main__":
    unittest.main()
