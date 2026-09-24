"""Consumer-side check of the distribution tree (issue #511): the exact file
set #509 publishes is discoverable and installable through the `skills` CLI,
and each installed copy is self-contained.

The offline tests always run. The `npx skills` tests are opt-in via
`DISTRIBUTION_INSTALL_CHECK=1` (CI sets it with a pinned CLI) so a plain local
test run never depends on the npm registry.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import tests.unit.package_domain._shared  # noqa: F401 - sys.path wiring
import tests.unit.release._shared  # noqa: F401 - scripts/release sys.path wiring

from package_domain.version import newest_release_version
from release_lib import distribution
from tests.integration.packaging._shared import DIST_DIR, PACKAGE_SCRIPT, _package_manifest
from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from skill_metadata.links import find_broken_markdown_links  # noqa: E402

SKILLS_CLI = os.environ.get("SKILLS_CLI_SPEC", "skills@1.7.0")
RUN_CLI = os.environ.get("DISTRIBUTION_INSTALL_CHECK", "").lower() in {"1", "true", "yes"}
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


@unittest.skipUnless(shutil.which("bash") and shutil.which("python3"), "needs bash and python3")
class DistributionConsumerInstallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.names = sorted(s["name"] for s in _package_manifest()["skills"].values())
        result = subprocess.run(
            [str(PACKAGE_SCRIPT), "all"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise AssertionError(f"package-skills.sh all failed:\n{result.stdout}\n{result.stderr}")
        version = newest_release_version((REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
        cls.build = distribution.build_distribution(
            REPO_ROOT, DIST_DIR, version, "amirbena/code-review-skill", "a" * 40
        )
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.tmp = Path(tmp.name)
        cls.repo = cls.tmp / "distribution"
        for path, data in cls.build.files.items():
            target = cls.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

    def _skills(self, *args: str, cwd: Path) -> str:
        env = dict(os.environ, HOME=str(self.tmp), npm_config_update_notifier="false", CI="1")
        result = subprocess.run(
            ["npx", "--yes", SKILLS_CLI, *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=300
        )
        out = ANSI.sub("", result.stdout + result.stderr)
        if result.returncode != 0:
            self.fail(f"npx {SKILLS_CLI} {' '.join(args)} failed:\n{out}")
        return out

    def test_published_root_holds_exactly_the_skills_and_plugin_files(self) -> None:
        self.assertEqual(sorted(p.name for p in (self.repo / "skills").iterdir()), self.names)
        for name in self.names:
            self.assertTrue((self.repo / "skills" / name / "SKILL.md").is_file())
        for path in ("plugin.json", ".claude-plugin/marketplace.json", "DISTRIBUTION.json", "LICENSE"):
            self.assertTrue((self.repo / path).is_file(), path)

    @unittest.skipUnless(RUN_CLI, "set DISTRIBUTION_INSTALL_CHECK=1 to run the npx skills checks")
    def test_skills_cli_lists_exactly_both_skills(self) -> None:
        out = self._skills("add", str(self.repo), "--list", cwd=self.tmp)
        self.assertIn(f"Found {len(self.names)} skills", out)
        for name in self.names:
            self.assertRegex(out, rf"(?m)^\W*{re.escape(name)}\s*$")

    @unittest.skipUnless(RUN_CLI, "set DISTRIBUTION_INSTALL_CHECK=1 to run the npx skills checks")
    def test_installed_copies_equal_the_trees_and_resolve_every_link(self) -> None:
        project = self.tmp / "project"
        project.mkdir()
        self._skills("add", str(self.repo), "-s", "*", "-a", "claude-code", "--copy", "-y", cwd=project)
        for name in self.names:
            installed = project / ".claude" / "skills" / name
            prefix = f"skills/{name}/"
            expected = {p[len(prefix):]: b for p, b in self.build.files.items() if p.startswith(prefix)}
            found = {
                p.relative_to(installed).as_posix(): p.read_bytes() for p in installed.rglob("*") if p.is_file()
            }
            self.assertEqual(found, expected, f"installed {name} differs from the published tree")
            broken = find_broken_markdown_links(
                sorted(installed.rglob("*.md")), installed, require_file=True
            )
            self.assertEqual([(str(b.source), b.target) for b in broken], [], f"broken links in {name}")


if __name__ == "__main__":
    unittest.main()
