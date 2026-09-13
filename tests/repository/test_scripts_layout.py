#!/usr/bin/env python3
"""`scripts/` stays subsystem-owned: no loose top-level scripts (Issue #292).

Every script belongs to a subsystem directory (benchmark/, governance/,
packaging/, release/, skill_metadata/, validation/); nothing is added
directly under `scripts/` again. Narrower than an allowlist: it needs no
update when a legitimate new subsystem directory is added, only flags a
regression to the old flat layout.
"""

from __future__ import annotations

import unittest

from tests.support.paths import REPO_ROOT

SCRIPTS_ROOT = REPO_ROOT / "scripts"


class ScriptsTopLevelLayoutTests(unittest.TestCase):
    def test_no_loose_files_directly_under_scripts(self) -> None:
        loose = sorted(p.name for p in SCRIPTS_ROOT.iterdir() if p.is_file())
        self.assertEqual(loose, [], f"scripts/ has loose top-level files, expected none: {loose}")

    def test_every_top_level_entry_is_a_subsystem_directory(self) -> None:
        non_dirs = sorted(p.name for p in SCRIPTS_ROOT.iterdir() if not p.is_dir())
        self.assertEqual(non_dirs, [])


if __name__ == "__main__":
    unittest.main()
