"""Focused building blocks for Skill discovery-metadata validation.

Split out of ``scripts/validation/validate-skill-metadata.py`` so each concern can be
read on its own; the script is now a thin entrypoint that calls ``main``.
The "what a packaged Skill may declare / reference" contract lives in
docs and ``policies/skill-development-policy.md``.

Module map:

- ``expectations`` -- the allowed frontmatter fields and forbidden link targets
- ``_support``     -- generic assertions and YAML/frontmatter loaders
- ``links``        -- Markdown link containment and resolution
- ``frontmatter``  -- the SKILL.md frontmatter contract
- ``orchestrator`` -- ``validate()`` wiring the checks together
- ``cli``          -- argument parsing
"""

from __future__ import annotations

from .cli import main
from .orchestrator import validate

__all__ = ["main", "validate"]
