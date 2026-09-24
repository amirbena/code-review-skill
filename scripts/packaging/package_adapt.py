#!/usr/bin/env python3
"""Rewrite shared-links/metadata-paths, stamp the release version, and
validate SKILL.md frontmatter for a staged, standalone packaged Skill.

Thin CLI entrypoint. The canonical implementation lives in
``package_domain/`` (see ``package_domain/__init__.py`` for the map);
this file only wires ``sys.argv`` to it. Called identically by
``scripts/packaging/package-skills.sh`` and ``scripts/packaging/package-skills.ps1``.

Usage:
    python3 scripts/packaging/package_adapt.py adapt-shared-links <file>
    python3 scripts/packaging/package_adapt.py adapt-metadata-paths <file>
    python3 scripts/packaging/package_adapt.py validate-frontmatter <file> <expected_name>
    python3 scripts/packaging/package_adapt.py stamp-release-version <file> <changelog>
    python3 scripts/packaging/package_adapt.py finalize-tree <tree> <expected_name>
    python3 scripts/packaging/package_adapt.py write-tree-manifest <dist_dir>
    python3 scripts/packaging/package_adapt.py build-archive <tree> <archive>
    python3 scripts/packaging/package_adapt.py verify-archive <tree> <archive>
"""

from __future__ import annotations

from package_domain import main

__all__ = ["main"]


if __name__ == "__main__":
    raise SystemExit(main())
