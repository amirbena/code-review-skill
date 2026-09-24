"""Canonical distribution build output (issue #507): `package-skills.sh all`
leaves deterministic, validated, self-contained Skill trees at
`dist/skills/<name>/`, a content manifest beside them, and zips that equal
those trees byte for byte."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import unittest
import zipfile

import tests.unit.package_domain._shared  # noqa: F401 - sys.path wiring

from package_domain.tree import tree_files, tree_hash
from package_domain.version import frontmatter_version, newest_release_version
from tests.integration.packaging._shared import DIST_DIR, PACKAGE_SCRIPT, _package_manifest
from tests.support.paths import REPO_ROOT

try:
    import skills_ref
except ImportError:  # pragma: no cover - CI installs the pinned skills-ref
    skills_ref = None


@unittest.skipUnless(shutil.which("bash") and shutil.which("python3"), "needs bash and python3")
class SkillTreeOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.skills = [(s["name"], s["archive"]) for s in _package_manifest()["skills"].values()]
        cls.hashes: list[str] = []
        for _ in range(2):
            result = subprocess.run(
                [str(PACKAGE_SCRIPT), "all"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                raise AssertionError(f"package-skills.sh all failed:\n{result.stdout}\n{result.stderr}")
            manifest = json.loads((DIST_DIR / "skills-manifest.json").read_text(encoding="utf-8"))
            cls.hashes.append(json.dumps(manifest, sort_keys=True))
        cls.manifest = manifest

    def test_each_skill_has_a_tree_and_the_manifest_lists_only_those(self) -> None:
        for name, _archive in self.skills:
            self.assertTrue((DIST_DIR / "skills" / name / "SKILL.md").is_file())
        self.assertEqual(sorted(self.manifest["skills"]), sorted(n for n, _ in self.skills))

    def test_rebuilding_the_same_commit_reproduces_the_manifest(self) -> None:
        self.assertEqual(self.hashes[0], self.hashes[1])

    def test_manifest_matches_the_trees_on_disk(self) -> None:
        for name, _archive in self.skills:
            files = tree_files(DIST_DIR / "skills" / name)
            self.assertEqual(self.manifest["skills"][name]["files"], files)
            self.assertEqual(self.manifest["skills"][name]["tree_hash"], tree_hash(files))
            self.assertFalse((DIST_DIR / "skills" / name / "skills-manifest.json").exists())

    def test_zip_extracts_to_exactly_the_tree(self) -> None:
        for name, archive in self.skills:
            tree = DIST_DIR / "skills" / name
            with zipfile.ZipFile(DIST_DIR / archive) as zf:
                found = {i.filename: zf.read(i) for i in zf.infolist() if not i.is_dir()}
            expected = {p.relative_to(tree).as_posix(): p.read_bytes() for p in tree.rglob("*") if p.is_file()}
            self.assertEqual(found, expected)

    def test_trees_carry_the_spec_conformant_version_form(self) -> None:
        newest = newest_release_version((REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
        for name, _archive in self.skills:
            text = (DIST_DIR / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"(?m)^version:", text))
            self.assertIn(f'metadata:\n  version: "{newest}"\n', text)
            self.assertEqual(frontmatter_version(text), newest)

    def test_trees_are_self_contained_lf_and_bom_free(self) -> None:
        for name, _archive in self.skills:
            for path in (DIST_DIR / "skills" / name).rglob("*"):
                if not path.is_file():
                    continue
                data = path.read_bytes()
                self.assertFalse(data.startswith(b"\xef\xbb\xbf"), path)
                self.assertNotIn(b"\r\n", data, path)
                if path.suffix == ".md":
                    self.assertNotIn("../../shared", data.decode("utf-8"), path)

    @unittest.skipIf(skills_ref is None, "skills-ref is not installed (CI installs the pinned version)")
    def test_trees_pass_the_reference_agent_skills_validator(self) -> None:
        for name, _archive in self.skills:
            self.assertEqual(skills_ref.validate(DIST_DIR / "skills" / name), [])


if __name__ == "__main__":
    unittest.main()
