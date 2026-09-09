"""Focused building blocks for Skill discovery-metadata validation.

Split out of ``scripts/validate-skill-metadata.py`` so each concern can be
read on its own; the script is now a thin entrypoint that calls ``main``.
The "what a packaged Skill may declare / reference" contract lives in
docs and ``policies/skill-development-policy.md``.

Module map:

- ``expectations``     — the required-marker / ordering / field tables
- ``_support``         — generic text assertions and YAML/frontmatter loaders
- ``links``            — packaged Markdown link containment and resolution
- ``metadata``         — SKILL.md frontmatter parity, adapters, declared paths
- ``shared_resources`` — the packaged ``shared/`` templates and policies
- ``github_family``    — the modular ``github-pr-review`` policy layout
- ``local_family``     — ``local-code-review`` approval-gate markers
- ``orchestrator``     — ``validate()`` wiring the checks together
- ``cli``              — argument parsing
"""

from __future__ import annotations

from .cli import main
from .orchestrator import validate

__all__ = ["main", "validate"]
