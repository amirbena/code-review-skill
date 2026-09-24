"""Standard `skills` CLI discovery and install from the built tree (issue #511).

Assembles the exact file set the distribution repository would publish
(#509) as a local source, then runs `npx skills add <path>` against it: the
CLI must discover exactly both Skills, and the installed copies must be
self-contained (every link resolves inside the installed copy, none escaping it). The live check against the published repository is manual
and recorded in docs/distribution.md.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.integration.packaging._shared import DIST_DIR, PACKAGE_SCRIPT, _package_manifest
from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "release"))

from release_lib.distribution import DISTRIBUTION_JSON, build_distribution  # noqa: E402
from skill_metadata.links import find_broken_markdown_links  # noqa: E402

# Pinned so a CLI release cannot change discovery behavior under CI unnoticed.
SKILLS_CLI = "skills@1.7.0"
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


@unittest.skipUnless(
    shutil.which("npx") and shutil.which("bash") and shutil.which("python3"),
    "needs npx, bash, and python3",
)
class SkillsCliInstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        result = subprocess.run(
            [str(PACKAGE_SCRIPT), "all"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise AssertionError(f"package-skills.sh all failed:\n{result.stdout}\n{result.stderr}")
        cls.names = sorted(s["name"] for s in _package_manifest()["skills"].values())
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.tmp = Path(tmp.name)
        cls.source = cls.tmp / "distribution"
        build = build_distribution(REPO_ROOT, DIST_DIR, "0.0.0", "example/source", "0" * 40)
        for path, data in build.files.items():
            target = cls.source / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        cls.env = {
            **os.environ,
            "HOME": str(cls.tmp / "home"),
            "DISABLE_TELEMETRY": "1",
            "DO_NOT_TRACK": "1",
            "CI": "1",
        }

    def _skills(self, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["npx", "--yes", SKILLS_CLI, *args],
            cwd=cwd, env=self.env, capture_output=True, text=True, timeout=300,
        )

    def test_list_discovers_exactly_both_skills(self) -> None:
        cwd = self.tmp / "list"
        cwd.mkdir()
        result = self._skills("add", str(self.source), "--list", cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        plain = ANSI.sub("", result.stdout)
        self.assertRegex(plain, rf"Found {len(self.names)} skills")
        for name in self.names:
            self.assertRegex(plain, rf"(?m)^│\s+{name}$")

    def test_installed_copies_are_self_contained(self) -> None:
        project = self.tmp / "project"
        project.mkdir()
        args = ["add", str(self.source), "-a", "claude-code", "-y", "--copy"]
        for name in self.names:
            args += ["--skill", name]
        result = self._skills(*args, cwd=project)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        installed = project / ".claude" / "skills"
        self.assertEqual(sorted(p.name for p in installed.iterdir()), self.names)
        for name in self.names:
            root = installed / name
            self.assertTrue((root / "SKILL.md").is_file())
            broken = find_broken_markdown_links(sorted(root.rglob("*.md")), root, require_file=True)
            self.assertEqual([], [f"{b.source}: {b.target}" for b in broken])

    def test_distribution_manifest_names_the_built_content(self) -> None:
        data = json.loads((self.source / DISTRIBUTION_JSON).read_text(encoding="utf-8"))
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(len(data["content_manifest_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
