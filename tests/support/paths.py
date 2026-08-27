"""Canonical repository-root path for the whole test suite.

One deterministic definition so nested test modules never need a fragile
``Path(__file__).parent.parent...`` chain.
"""

from __future__ import annotations

from pathlib import Path

# tests/support/paths.py -> parents[2] is the repository root.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Guard against an unexpected relocation of this helper.
if not (REPO_ROOT / "AGENTS.md").is_file() or not (REPO_ROOT / "skills").is_dir():
    raise RuntimeError(f"unexpected repository layout: REPO_ROOT={REPO_ROOT}")
