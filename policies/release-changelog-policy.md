# Release / Changelog Policy

Canonical repository-development rules for classifying `CHANGELOG.md`
entries by SemVer intent. This policy is **not packaged into either Skill
archive**. See [`../docs/RELEASE.md`](../docs/RELEASE.md) for the release flow
and [`../scripts/release_worthiness.py`](../scripts/release_worthiness.py) for
the deterministic implementation.

## Category-to-SemVer contract

The category heading under `## Unreleased` determines the version bump:

| Category | Bump |
| --- | --- |
| `Added`, `Changed`, `Deprecated` | **minor** |
| `Fixed`, `Security` | **patch** |
| `Removed`, `Breaking` (`Breaking Changes`) | **major** |

Use `Changed` for an intentional backward-compatible change to user-visible
behavior or capability: existing behavior changes by design, supported
behavior is broadened or altered, workflow or contract semantics change, or
users must understand a new behavioral expectation.

Use `Fixed` for a compatible correction or refinement that restores or cleans
up intended behavior without adding a capability. This includes bug or
regression fixes; corrections to wording, examples, or stale runtime guidance;
product-neutral or compatibility-preserving cleanup; an accompanying regression
guard; and fail-closed tightening that implements already-intended semantics.

**Decision rule:** if users receive a new or intentionally changed capability,
use `Added` or `Changed`; if the change corrects, cleans up, or restores intended
compatible behavior, use `Fixed`.

The highest-impact category in a release wins. Classification is mechanical;
do not infer impact from arbitrary entry prose or change
`classify_semver_impact()` to do so.
