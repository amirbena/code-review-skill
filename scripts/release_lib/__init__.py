"""Focused building blocks for the direct-to-main release flow.

Split out of ``scripts/release_worthiness.py`` so each concern of the
release flow can be read on its own; the script re-exports these names and
wires them into the CLI. The end-to-end policy lives in docs/RELEASE.md.

Module map:

- ``classification``  — which changed paths make a change set release-worthy
- ``changelog``       — ``## Unreleased`` parsing, the release-time roll,
                        and per-version section extraction
- ``semver_version``  — ``X.Y.Z`` form validation and the bump arithmetic
- ``semver_policy``   — deterministic ``### <Category>`` -> patch/minor/major
- ``remote_state``    — pure comparisons over ``git`` / ``gh`` command output
- ``gitgh``           — the read-only Git/GitHub queries the CLI depends on
- ``cli``             — argument parsing and the thin command handlers
"""
