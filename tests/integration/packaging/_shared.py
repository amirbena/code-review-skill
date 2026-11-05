"""Shared paths and manifest helpers for the packaging-boundary guard tests
split across this package — see the package docstring in
tests/integration/packaging/__init__.py for what the guard protects.
"""

from __future__ import annotations

import json

from tests.support.paths import REPO_ROOT

PACKAGE_SCRIPT = REPO_ROOT / "scripts" / "packaging" / "package-skills.sh"
PACKAGE_MANIFEST = REPO_ROOT / "scripts" / "packaging" / "package-manifest.json"
PACKAGE_MANIFEST_HELPER = REPO_ROOT / "scripts" / "packaging" / "package_manifest.py"
DIST_DIR = REPO_ROOT / "dist"

SH = PACKAGE_SCRIPT
PS1 = REPO_ROOT / "scripts" / "packaging" / "package-skills.ps1"


def _package_manifest() -> dict:
    return json.loads(PACKAGE_MANIFEST.read_text(encoding="utf-8"))
