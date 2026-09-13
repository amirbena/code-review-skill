"""Shared sys.path wiring for the scripts/package_domain/ unit tests."""

from __future__ import annotations

import sys

from tests.support.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
