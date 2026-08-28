#!/usr/bin/env python3
"""Structural coverage for the repository instruction architecture:
AGENTS.md is a routing entrypoint, each routed policy file exists and is
canonical, moved rules are not duplicated back into AGENTS.md, and no
repository-development policy leaks into a packaged Skill.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

AGENTS = REPO_ROOT / "AGENTS.md"
CLAUDE = REPO_ROOT / "CLAUDE.md"
POLICIES_DIR = REPO_ROOT / "policies"
PACKAGE_SCRIPTS = (
    REPO_ROOT / "scripts" / "package-skills.sh",
    REPO_ROOT / "scripts" / "package-skills.ps1",
)
SKILL_DIRS = (
    REPO_ROOT / "skills" / "local-code-review",
    REPO_ROOT / "skills" / "github-pr-review",
)
LINK_RE = re.compile(r"\]\(([^)]+)\)")

# Every policy AGENTS.md routes to, and a phrase each one canonically owns
# that must therefore NOT be inlined in AGENTS.md anymore.
ROUTED_POLICIES = {
    "repository-workflow.md": "Preserving local changes when switching (stash discipline)",
    "git-pr-merge-policy.md": "Squash Cleanup Safety",
    "validation-and-clean-exit.md": "Python cache/bytecode cleanup around commits",
    "documentation-policy.md": "User journey first.",
    "skill-development-policy.md": "Portable Core, Optional Runtime Adapters",
    "review-orchestration-policy.md": "One review scope → one Code Review Agent owner",
    "python_scripts_coding_policy.md": "Remove or shorten a comment that mainly explains",
}


def _norm(path: Path) -> str:
    raw = path.read_text(encoding="utf-8").replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", raw)


class RoutingTableTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agents_raw = AGENTS.read_text(encoding="utf-8")
        self.agents_norm = _norm(AGENTS)

    def test_every_routed_policy_file_exists(self) -> None:
        for name in ROUTED_POLICIES:
            self.assertTrue((POLICIES_DIR / name).is_file(), f"missing policy: {name}")

    def test_agents_links_to_every_routed_policy(self) -> None:
        for name in ROUTED_POLICIES:
            self.assertIn(f"](policies/{name})", self.agents_raw, f"AGENTS.md does not route to {name}")

    def test_agents_keeps_entrypoint_scaffolding(self) -> None:
        for header in (
            "## Global invariants",
            "## Instruction precedence",
            "## Task routing",
            "## Maintainability and extension",
        ):
            self.assertIn(header, self.agents_raw)

    def test_agents_does_not_inline_moved_detail(self) -> None:
        for name, owned_phrase in ROUTED_POLICIES.items():
            self.assertIn(owned_phrase, _norm(POLICIES_DIR / name), f"{name} lost its owned rule")
            self.assertNotIn(
                owned_phrase,
                self.agents_norm,
                f"AGENTS.md still inlines a rule owned by {name}",
            )

    def test_every_policy_dir_file_is_routed(self) -> None:
        # README.md is the directory's navigation aid, not a routed policy.
        on_disk = {p.name for p in POLICIES_DIR.glob("*.md")} - {"README.md"}
        self.assertEqual(on_disk, set(ROUTED_POLICIES), "policies/ and the routing table disagree")


class CanonicalOwnershipTests(unittest.TestCase):
    def test_new_policies_declare_they_are_not_packaged(self) -> None:
        for name in ROUTED_POLICIES:
            if name == "python_scripts_coding_policy.md":
                continue
            self.assertIn(
                "not packaged into either Skill archive",
                _norm(POLICIES_DIR / name),
                f"{name} must state it is repository-development only",
            )

    def test_claude_md_still_defers_to_agents_md(self) -> None:
        t = _norm(CLAUDE)
        self.assertIn("AGENTS.md", t)
        self.assertIn("canonical", t)
        self.assertIn("Read and follow AGENTS.md first", t)

    def test_new_policy_relative_links_resolve(self) -> None:
        broken = []
        for name in ROUTED_POLICIES:
            md = POLICIES_DIR / name
            for target in LINK_RE.findall(md.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                rel = target.split("#", 1)[0].strip()
                if rel and not (md.parent / rel).exists():
                    broken.append(f"{name} -> {target}")
        self.assertEqual(broken, [], f"broken links in policies/: {broken}")


class PoliciesReadmeTests(unittest.TestCase):
    README = POLICIES_DIR / "README.md"

    def test_readme_exists_and_maps_every_routed_policy(self) -> None:
        self.assertTrue(self.README.is_file())
        raw = self.README.read_text(encoding="utf-8")
        for name in ROUTED_POLICIES:
            self.assertIn(f"]({name})", raw, f"policies/README.md does not list {name}")

    def test_readme_states_the_runtime_boundary(self) -> None:
        t = _norm(self.README)
        self.assertIn("never shipped", t)
        self.assertIn("no packaged Skill resource may depend on them", t)
        self.assertIn("shared/", t)
        self.assertIn("skills/", t)

    def test_readme_is_navigational_only(self) -> None:
        # A directory map, not another normative policy: no imperative
        # rule-defining modal verbs of the kind the policy files use.
        t = _norm(self.README)
        self.assertNotIn("MUST NOT", t)
        self.assertNotIn("MUST ", t)


class PackagingBoundaryTests(unittest.TestCase):
    # Repository-development files that must never enter a packaged archive.
    UNPACKAGED = set(ROUTED_POLICIES) | {"README.md"}

    def test_no_package_script_lists_a_repository_development_policy(self) -> None:
        for script in PACKAGE_SCRIPTS:
            text = script.read_text(encoding="utf-8")
            for name in self.UNPACKAGED:
                self.assertNotIn(
                    f'"policies/{name}"',
                    text,
                    f"{script.name} packages repository-development file {name}",
                )

    def test_no_packaged_skill_markdown_links_to_a_repository_development_policy(self) -> None:
        offenders = []
        for skill_dir in SKILL_DIRS:
            for md in skill_dir.rglob("*.md"):
                for target in LINK_RE.findall(md.read_text(encoding="utf-8")):
                    rel = target.split("#", 1)[0].strip()
                    if not rel or rel.startswith(("http://", "https://", "mailto:")):
                        continue
                    # Only a link that actually points into repo-root policies/
                    # is a violation — a Skill's own policies/<name>.md is fine.
                    resolved = (md.parent / rel).resolve()
                    if resolved.parent == POLICIES_DIR.resolve():
                        offenders.append(f"{md.relative_to(REPO_ROOT)} -> {target}")
        self.assertEqual(offenders, [], f"packaged links into repo-root policies/: {offenders}")

    def test_archives_exclude_repository_development_files(self) -> None:
        import zipfile

        dist = REPO_ROOT / "dist"
        archives = [
            dist / "local-code-review-skill.zip",
            dist / "github-pr-review-skill.zip",
        ]
        if not all(a.is_file() for a in archives):
            self.skipTest("archives not built; run scripts/package-skills.sh all")
        banned = {f"policies/{n}" for n in self.UNPACKAGED} | {"AGENTS.md", "CLAUDE.md"}
        for archive in archives:
            with zipfile.ZipFile(archive) as zf:
                names = set(zf.namelist())
            self.assertEqual(
                names & banned, set(), f"{archive.name} ships repository-development files"
            )


if __name__ == "__main__":
    unittest.main()
