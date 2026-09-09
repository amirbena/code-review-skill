#!/usr/bin/env python3
"""Validate Skill discovery metadata and declared package resources.

Thin CLI entrypoint. The checks are split into focused modules under
``skill_metadata/`` (see ``skill_metadata/__init__.py`` for the map); this
file only wires ``sys.argv`` to them and re-exports their public names so
existing importers keep working.

Usage:
    python3 scripts/validate-skill-metadata.py <skill_root> [--containment-root <root>]
"""

from __future__ import annotations

from skill_metadata import main, validate

__all__ = ["main", "validate"]


if __name__ == "__main__":
    main()
