"""Host-independent Git for tests that build throwaway repositories.

A developer's or runner's global Git configuration (commit signing, hooks,
default branch, identity) must not decide whether a fixture repository can
commit. ``isolate_git_config`` points Git at an empty configuration for a
whole test module, so code under test that spawns ``git`` itself is covered
too; ``git`` is the shared stripped-stdout runner for fixture setup.
"""

from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

ISOLATED_GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_AUTHOR_NAME": "Test Author",
    "GIT_AUTHOR_EMAIL": "author@example.invalid",
    "GIT_COMMITTER_NAME": "Test Author",
    "GIT_COMMITTER_EMAIL": "author@example.invalid",
}


def isolate_git_config() -> None:
    """Call from ``setUpModule``: isolate Git config for the module's tests."""
    patcher = mock.patch.dict(os.environ, ISOLATED_GIT_ENV)
    patcher.start()
    unittest.addModuleCleanup(patcher.stop)


def git(cwd: Path, *args: str) -> str:
    """Run ``git`` in ``cwd`` under the isolated environment; return stripped stdout."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env={**os.environ, **ISOLATED_GIT_ENV},
        check=True,
    ).stdout.strip()
