#!/usr/bin/env python3
"""Validate Skill discovery metadata and declared package resources.

Thin CLI entrypoint. The checks are split into focused modules under
``skill_metadata/`` (see ``skill_metadata/__init__.py`` for the map); this
file only wires ``sys.argv`` to them and re-exports their public names so
existing importers keep working.

Usage:
    python3 scripts/validation/validate-skill-metadata.py <skill_root> [--containment-root <root>]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skill_metadata import main, validate  # noqa: E402

__all__ = ["main", "validate"]


if __name__ == "__main__":
    main()
