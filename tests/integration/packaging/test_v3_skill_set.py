"""v3 Skill set packaging (#851): every skills/* folder is a self-contained,
deterministic archive; the two v2 names are thin wrappers over review-core;
no pre-cutover build labels a v3 Skill with a v2.x version."""

from __future__ import annotations

import json
import re
import subprocess
import unittest
import zipfile

from tests.integration.packaging._shared import DIST_DIR, PACKAGE_SCRIPT, _package_manifest
from tests.support.paths import REPO_ROOT

SKILLS = REPO_ROOT / "skills"
WRAPPERS = ("local-code-review", "github-pr-review")
MINI_SKILLS = (
    "review-publish-github",
    "review-requirements",
    "review-deep-investigation",
    "review-suggestions",
    "review-security",
    "review-backend",
    "review-frontend",
    "review-runtime-check",
)
V3_SKILLS = ("review-core", *MINI_SKILLS)


def _skill_md(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def _frontmatter_lines(text: str) -> list[str]:
    return text.split("---", 2)[1].strip().splitlines()


class ManifestCoversEverySkillTests(unittest.TestCase):
    def test_manifest_targets_are_exactly_the_skill_folders(self) -> None:
        folders = {p.name for p in SKILLS.iterdir() if p.is_dir()}
        self.assertEqual(folders, {*V3_SKILLS, *WRAPPERS})
        names = {skill["name"] for skill in _package_manifest()["skills"].values()}
        self.assertEqual(names, folders)

    def test_each_target_packages_its_own_folder_and_only_license_from_outside(self) -> None:
        manifest = _package_manifest()
        self.assertEqual([e["source"] for e in manifest["shared_files"]], ["LICENSE"])
        for skill in manifest["skills"].values():
            folder = {p.relative_to(SKILLS / skill["name"]).as_posix() for p in (SKILLS / skill["name"]).rglob("*") if p.is_file()}
            self.assertEqual({e["destination"] for e in skill["files"]}, folder)
            self.assertTrue(all(e["source"].startswith(f"skills/{skill['name']}/") for e in skill["files"]))

    def test_distribution_plugin_files_describe_the_whole_skill_set(self) -> None:
        for path in ("distribution/claude/marketplace.json", "distribution/portable/plugin.json"):
            text = (REPO_ROOT / path).read_text(encoding="utf-8")
            json.loads(text)
            self.assertIn("{{version}}", text)
            for name in ("review-core", "local-code-review", "github-pr-review"):
                self.assertIn(name, text, path)


class CompatibilityWrapperTests(unittest.TestCase):
    def test_wrappers_keep_the_v2_0_0_name_and_delegate_to_review_core(self) -> None:
        for name in WRAPPERS:
            text = _skill_md(name)
            self.assertIn(f"name: {name}", text)
            self.assertIn("`review-core`", text)
            self.assertLessEqual(len(text.splitlines()), 30, f"{name} must stay one short SKILL.md")
            self.assertEqual([p.name for p in (SKILLS / name).iterdir()], ["SKILL.md"])

    def test_wrappers_restate_no_core_policy_or_v2_machinery(self) -> None:
        for name in WRAPPERS:
            text = _skill_md(name)
            for forbidden in ("P0", "P1", "P2", "shared/", "policies/", "ACTIVE", "PASSIVE", "SEMI", "router", "dispatch"):
                self.assertNotIn(forbidden, text.replace("P0/P1/P2 code-review findings", "").replace("P0/P1/P2 findings", ""), f"{name}: {forbidden}")

    def test_github_wrapper_never_publishes_without_an_explicit_request(self) -> None:
        text = _skill_md("github-pr-review")
        self.assertRegex(text, r"never publishes on its own")
        self.assertRegex(text, r"only when the user explicitly asks")
        self.assertIn("`review-publish-github`", text)
        self.assertNotIn("review-publish-github", _skill_md("local-code-review"))

    def test_review_core_stays_directly_invocable(self) -> None:
        text = _skill_md("review-core")
        self.assertIn("name: review-core", text)
        self.assertNotRegex(text, r"(?i)requires `?(local-code-review|github-pr-review)")
        for name in WRAPPERS:
            self.assertNotIn(f"`{name}`", text)

    def test_every_mini_skill_states_it_requires_review_core(self) -> None:
        for name in MINI_SKILLS:
            self.assertIn("**Requires `review-core`.**", _skill_md(name), name)


class BuildOutputTests(unittest.TestCase):
    """Builds every archive twice with the real script (offline)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.hashes: list[dict[str, bytes]] = []
        for _ in range(2):
            subprocess.run(["bash", str(PACKAGE_SCRIPT), "all"], cwd=REPO_ROOT, check=True, capture_output=True)
            cls.hashes.append({p.name: p.read_bytes() for p in sorted(DIST_DIR.glob("*.zip"))})

    def test_archive_set_matches_the_manifest(self) -> None:
        expected = {skill["archive"] for skill in _package_manifest()["skills"].values()}
        self.assertEqual(set(self.hashes[0]), expected)

    def test_archives_are_byte_identical_across_builds(self) -> None:
        self.assertEqual(self.hashes[0], self.hashes[1])

    def test_archives_are_self_contained(self) -> None:
        for skill in _package_manifest()["skills"].values():
            with zipfile.ZipFile(DIST_DIR / skill["archive"]) as zf:
                names = zf.namelist()
                self.assertIn("SKILL.md", names)
                self.assertIn("LICENSE", names)
                self.assertFalse([n for n in names if n.startswith(("skills/", "shared/"))])
                for name in names:
                    if name.endswith(".md"):
                        self.assertNotRegex(zf.read(name).decode("utf-8"), r"\.\./shared/")

    def test_a_build_never_labels_a_v3_skill_with_a_version_its_source_lacks(self) -> None:
        # Before the cutover a v3 SKILL.md has no `version:` line, so its archive must carry
        # none (not the newest v2.x CHANGELOG heading). After the release run stamps
        # `version: X.Y.Z`, the archive carries exactly that.
        for skill in _package_manifest()["skills"].values():
            source = [l for l in _frontmatter_lines(_skill_md(skill["name"])) if l.startswith("version:")]
            with zipfile.ZipFile(DIST_DIR / skill["archive"]) as zf:
                built = zf.read("SKILL.md").decode("utf-8").split("---", 2)[1]
            built_versions = re.findall(r'(?m)^\s+version:\s*"?([^"\s]+)"?\s*$', built)
            if source:
                self.assertEqual(built_versions, [source[0].split(":", 1)[1].strip()], skill["name"])
            else:
                self.assertEqual(built_versions, [], skill["name"])
                self.assertNotIn("metadata:", built, skill["name"])


if __name__ == "__main__":
    unittest.main()
