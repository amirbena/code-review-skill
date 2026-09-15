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

# A body shaped like a coding-agent runtime's own generic default PR-body
# example (``## Summary`` / ``## Test plan``) rather than this repository's
# canonical `.github/PULL_REQUEST_TEMPLATE.md`. Regression fixture for the
# competing-instruction failure mode: an agent that never re-reads the live
# template can reach for this shape instead. It must fail structure
# validation even though it is well-formed Markdown with real content.
RUNTIME_DEFAULT_SUMMARY_BODY = """\
## Summary

- Adds a thing.
- Fixes a bug in the thing.

## Test plan

- [x] Ran the test suite locally.
"""

# A compliant body for genuinely issue-less maintainer-led work: declares
# "Fixes #N/A" explicitly instead of leaving "Fixes #" blank.
COMPLIANT_BODY_NO_ISSUE = COMPLIANT_BODY.replace("Fixes #135", "Fixes #N/A", 1)
