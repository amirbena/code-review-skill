#!/usr/bin/env python3
"""Structural coverage for the repository instruction architecture:
AGENTS.md is a routing entrypoint, each routed policy file exists and is
canonical, moved rules are not duplicated back into AGENTS.md, no
repository-development policy leaks into a packaged Skill, and every
user-facing policy/guidance directory has a navigational README.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.support.paths import REPO_ROOT

AGENTS = REPO_ROOT / "AGENTS.md"
CLAUDE = REPO_ROOT / "CLAUDE.md"
POLICIES_DIR = REPO_ROOT / "policies"
SHARED_POLICIES_DIR = REPO_ROOT / "shared" / "policies"
DOCUMENTATION_POLICY = POLICIES_DIR / "documentation-policy.md"
# Directories a person/agent is expected to browse directly per
# documentation-policy.md, "Navigational README for user-facing
# policy/guidance directories."
USER_FACING_GUIDANCE_DIRS = (
    POLICIES_DIR,
    SHARED_POLICIES_DIR,
    REPO_ROOT / "tests",
    REPO_ROOT / "docs" / "features",
)
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
    "github-issue-pr-authoring.md": "Agent-complete internally, human-scannable externally",
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


class SharedPoliciesReadmeTests(unittest.TestCase):
    README = SHARED_POLICIES_DIR / "README.md"

    def test_readme_exists(self) -> None:
        self.assertTrue(self.README.is_file())

    def test_readme_maps_exactly_the_existing_shared_policies(self) -> None:
        raw = self.README.read_text(encoding="utf-8")
        listed = {
            m for m in LINK_RE.findall(raw)
            if m.endswith(".md") and "/" not in m
        }
        on_disk = {p.name for p in SHARED_POLICIES_DIR.glob("*.md")} - {"README.md"}
        # Every shared policy is mapped, and nothing invented.
        self.assertEqual(listed, on_disk, "shared/policies/README.md map is out of sync")

    def test_readme_is_navigational_only(self) -> None:
        t = _norm(self.README)
        self.assertNotIn("MUST NOT", t)
        self.assertNotIn("MUST ", t)
        self.assertIn("the policy wins", t)

    def test_readme_states_packaging_status(self) -> None:
        t = _norm(self.README)
        self.assertIn("except this README", t)
        self.assertIn("packaged runtime resource", t)

    def test_readme_relative_links_resolve(self) -> None:
        broken = [
            target
            for target in LINK_RE.findall(self.README.read_text(encoding="utf-8"))
            if not target.startswith(("http://", "https://", "mailto:"))
            and (rel := target.split("#", 1)[0].strip())
            and not (self.README.parent / rel).exists()
        ]
        self.assertEqual(broken, [], f"broken links in shared/policies/README.md: {broken}")


class NavigationalReadmeConventionTests(unittest.TestCase):
    def test_convention_is_owned_by_documentation_policy(self) -> None:
        raw = DOCUMENTATION_POLICY.read_text(encoding="utf-8")
        self.assertIn(
            "## Navigational README for user-facing policy/guidance directories", raw
        )
        t = _norm(DOCUMENTATION_POLICY)
        self.assertIn("If a README and a policy conflict, the policy wins", t)
        self.assertIn("not a rule that", t)  # explicitly not "every directory has a README"

    def test_agents_routes_the_convention_without_inlining_it(self) -> None:
        raw = AGENTS.read_text(encoding="utf-8")
        self.assertIn("](policies/documentation-policy.md)", raw)
        self.assertIn("navigational README", _norm(AGENTS))

    def test_user_facing_guidance_directories_have_an_entrypoint(self) -> None:
        missing = [
            str(d.relative_to(REPO_ROOT))
            for d in USER_FACING_GUIDANCE_DIRS
            if not (d / "README.md").is_file()
        ]
        self.assertEqual(missing, [], f"user-facing guidance dirs without a README: {missing}")


FEATURES_DIR = REPO_ROOT / "docs" / "features"


class FeatureCatalogTests(unittest.TestCase):
    """docs/features/README.md is the capability catalog: every feature
    guide is a real, linked page, and its links resolve."""

    def setUp(self) -> None:
        self.readme = FEATURES_DIR / "README.md"
        self.assertTrue(self.readme.is_file())
        self.raw = self.readme.read_text(encoding="utf-8")

    def test_catalog_links_every_feature_guide(self) -> None:
        on_disk = {p.name for p in FEATURES_DIR.glob("*.md")} - {"README.md"}
        self.assertTrue(on_disk, "no feature guides found under docs/features/")
        for name in sorted(on_disk):
            self.assertIn(
                f"]({name})", self.raw, f"docs/features/README.md does not list {name}"
            )

    def test_catalog_names_the_supporting_skill_and_activation(self) -> None:
        t = _norm(self.readme)
        # It is a catalog, not just a link list: it states support + activation.
        self.assertIn("which Skill supports it", t)
        self.assertIn("Default / conditional / requested", t)
        # And it draws the boundary of what is NOT a feature guide.
        self.assertIn("Not a feature guide", t)

    def test_catalog_relative_links_resolve(self) -> None:
        broken = [
            target
            for target in LINK_RE.findall(self.raw)
            if not target.startswith(("http://", "https://", "mailto:"))
            and not (self.readme.parent / target.split("#", 1)[0]).exists()
        ]
        self.assertEqual(broken, [], f"broken links in docs/features/README.md: {broken}")

    def test_feature_guides_are_never_packaged(self) -> None:
        # docs/ is repository-development documentation; no package script
        # may stage a docs/features/ path.
        for script in PACKAGE_SCRIPTS:
            text = script.read_text(encoding="utf-8")
            self.assertNotIn("docs/features", text, f"{script.name} references docs/features/")


class ThinReadmeDisciplineTests(unittest.TestCase):
    """The README-layering rule survives beyond one issue: it is a stated
    AGENTS.md invariant routed to its canonical policy."""

    def test_agents_states_the_thin_layered_documentation_invariant(self) -> None:
        t = _norm(AGENTS)
        self.assertIn("Thin, layered documentation.", t)
        self.assertIn("capability catalog", t)
        self.assertIn("](docs/features/README.md)", AGENTS.read_text(encoding="utf-8"))

    def test_documentation_policy_owns_the_layering_and_duplication_rule(self) -> None:
        # Concept checks, not verbatim sentences: harmless copy edits that
        # keep the meaning must not break this test.
        t = _norm(DOCUMENTATION_POLICY).lower()
        self.assertIn("thin readme discipline", t)  # the stable lead-in anchor
        self.assertIn("smallest", t)  # the smallest-layer principle
        # A canonical policy/runbook outranks explanatory docs on conflict.
        self.assertTrue(
            "canonical" in t and "wins" in t and "conflict" in t,
            "documentation-policy.md must state that the canonical doc wins a conflict",
        )

    def test_agents_routes_the_documentation_impact_check(self) -> None:
        t = _norm(AGENTS)
        self.assertIn("documentation-impact check", t)
        # An implementation-only change must not force a README edit.
        self.assertIn("no user-visible effect", _norm(AGENTS).lower())
        # It stays a summary that routes, not the full matrix.
        self.assertIn("](policies/documentation-policy.md)", AGENTS.read_text(encoding="utf-8"))
        self.assertNotIn("docs/features/<name>.md", t)  # matrix lives in the policy

    def test_documentation_policy_owns_the_capability_impact_rule(self) -> None:
        raw = DOCUMENTATION_POLICY.read_text(encoding="utf-8")
        heading = "### Documentation impact for capability changes"
        self.assertIn(heading, raw)  # stable structural anchor
        # Scope the concept checks to that section.
        section = _norm(DOCUMENTATION_POLICY).lower().split(heading.lower(), 1)[1]
        section = section.split("## navigational readme", 1)[0]
        self.assertIn("documentation-impact check", section)
        self.assertIn("smallest", section)  # route to the smallest affected layer
        # Implementation-only changes do not require a README/doc edit.
        self.assertTrue(
            "implementation" in section
            and ("no readme" in section or "needs no" in section or "no user-visible" in section),
            "the section must say an implementation-only change needs no README edit",
        )
        # A known-affected surface left stale means the change is incomplete.
        self.assertTrue(
            "incomplete" in section and "stale" in section,
            "the section must treat a stale known-affected surface as incomplete work",
        )
        # It is documentation governance, not a mechanical source-diff mapping.
        self.assertIn("not a mechanical", section)


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
        banned = (
            {f"policies/{n}" for n in self.UNPACKAGED}
            | {"AGENTS.md", "CLAUDE.md", "shared/policies/README.md"}
        )
        for archive in archives:
            with zipfile.ZipFile(archive) as zf:
                names = set(zf.namelist())
            self.assertEqual(
                names & banned, set(), f"{archive.name} ships repository-development files"
            )
            # Repository-level documentation under docs/ (the architecture
            # map, the feature guides, release notes, …) is never packaged.
            # Guard the built artifact directly, not just the package script.
            docs_entries = sorted(
                n for n in names if n == "docs" or n.startswith("docs/")
            )
            self.assertEqual(
                docs_entries,
                [],
                f"{archive.name} ships repository documentation: {docs_entries}",
            )


if __name__ == "__main__":
    unittest.main()
