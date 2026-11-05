#!/usr/bin/env python3
"""Structural guard for the instruction layering (#849): `CLAUDE.md` defers to
`AGENTS.md`, `AGENTS.md` routes to exactly the policies on disk, and the
directories people browse directly have a README. Prose is not pinned."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

AGENTS = REPO_ROOT / "AGENTS.md"
CLAUDE = REPO_ROOT / "CLAUDE.md"
POLICIES_DIR = REPO_ROOT / "policies"

# Directories people navigate directly to find policies, contracts or guidance
# (policies/documentation-policy.md, "Navigational README ...").
USER_FACING_GUIDANCE_DIRS = (
    POLICIES_DIR,
    REPO_ROOT / "tests",
    REPO_ROOT / "benchmark",
    REPO_ROOT / "runtime_platform" / "benchmark",
)
LINK_RE = re.compile(r"\]\(([^)]+)\)")
ROUTE_RE = re.compile(r"\]\(policies/([A-Za-z0-9_\-]+\.md)\)")


def _routed() -> set[str]:
    # policies/README.md is linked as a map, not routed to as a policy.
    return set(ROUTE_RE.findall(AGENTS.read_text(encoding="utf-8"))) - {"README.md"}


class RoutingTableTests(unittest.TestCase):
    def test_every_routed_policy_exists(self) -> None:
        for name in _routed():
            self.assertTrue((POLICIES_DIR / name).is_file(), f"AGENTS.md routes to missing policy: {name}")

    def test_every_policy_file_is_routed(self) -> None:
        # README.md is the directory's navigation aid, not a routed policy.
        on_disk = {p.name for p in POLICIES_DIR.glob("*.md")} - {"README.md"}
        self.assertEqual(on_disk, _routed(), "policies/ and the AGENTS.md routing disagree")

    def test_agents_keeps_entrypoint_scaffolding(self) -> None:
        text = AGENTS.read_text(encoding="utf-8")
        for header in ("## Global invariants", "## Instruction precedence", "## Task routing"):
            self.assertIn(header, text)

    def test_claude_md_defers_to_agents_md(self) -> None:
        text = " ".join(CLAUDE.read_text(encoding="utf-8").split())
        self.assertIn("Read and follow `AGENTS.md` first", text)

    def test_policy_relative_links_resolve(self) -> None:
        broken = []
        for md in sorted(POLICIES_DIR.glob("*.md")):
            for target in LINK_RE.findall(md.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                rel = target.split("#", 1)[0].strip()
                if rel and not (md.parent / rel).exists():
                    broken.append(f"{md.name} -> {target}")
        self.assertEqual(broken, [])


class GuidanceDirectoryTests(unittest.TestCase):
    def test_user_facing_guidance_directories_have_a_readme(self) -> None:
        missing = [
            str(d.relative_to(REPO_ROOT)) for d in USER_FACING_GUIDANCE_DIRS if not (d / "README.md").is_file()
        ]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
