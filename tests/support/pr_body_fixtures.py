"""A minimal PR description that satisfies the canonical PR-template
structure (`.github/PULL_REQUEST_TEMPLATE.md`), for tests that need a body
which passes structure validation without asserting on structure itself.
"""

from __future__ import annotations

COMPLIANT_BODY = """\
Fixes #135

## What

- **Behavior / contracts:** Adds a thing.
- **Governance / policy:** None
- **Packaging / portability:** None
- **Changelog:** generated at release from the two lines below — never edit `CHANGELOG.md` (see `docs/RELEASE.md`)
- **Release category:** none
- **Release entry:**

## Validation

- [x] Relevant validation was run, or the reason it could not be run is stated.
- Ran `python -m unittest discover -s tests -t .`.
"""
