"""Canonical packaging-domain logic shared by both platform orchestration
scripts (``scripts/packaging/package-skills.sh`` and ``scripts/packaging/package-skills.ps1``).

Named ``package_domain`` rather than ``packaging`` so it never shadows
the unrelated, widely-used PyPI ``packaging`` distribution when
``scripts/`` is prepended to ``sys.path``.

Split out so each concern can be read on its own; ``scripts/packaging/package_adapt.py``
is a thin entrypoint that calls ``main``.

Module map:

- ``adaptation`` — shared-link and metadata-path rewriting for staged Skills
- ``validation`` — SKILL.md frontmatter structural validation
- ``cli``        — argument parsing shared by both platform scripts

This package does not own the per-Skill package manifest
(``scripts/packaging/package-manifest.json`` / ``scripts/packaging/package_manifest.py``,
established by #196) or Skill discovery-metadata semantics
(``scripts/skill_metadata/``) — both stay where they are.
"""

from __future__ import annotations

from .cli import main

__all__ = ["main"]
