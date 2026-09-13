"""Canonical packaging-domain logic shared by both platform orchestration
scripts (``scripts/package-skills.sh`` and ``scripts/package-skills.ps1``).

Split out so each concern can be read on its own; ``scripts/package_adapt.py``
is a thin entrypoint that calls ``main``.

Module map:

- ``adaptation`` — shared-link and metadata-path rewriting for staged Skills
- ``validation`` — SKILL.md frontmatter structural validation
- ``cli``        — argument parsing shared by both platform scripts

This package does not own the per-Skill package manifest
(``scripts/package-manifest.json`` / ``scripts/package_manifest.py``,
established by #196) or Skill discovery-metadata semantics
(``scripts/skill_metadata/``) — both stay where they are.
"""

from __future__ import annotations

from .cli import main

__all__ = ["main"]
