# Canonical-home registry

Design record for issue #80. This document is **not packaged into either
Skill archive**. It records the maintainer decisions the registry rests on;
the registry itself is [`scripts/governance/canonical_homes.json`](../../scripts/governance/canonical_homes.json),
checked by [`scripts/governance/canonical_homes.py`](../../scripts/governance/canonical_homes.py) and
[`tests/policy/governance/test_canonical_homes.py`](../../tests/policy/governance/test_canonical_homes.py).

## What counts as a registered normative anchor

An anchor is an **exact string** a maintainer declares to have one owning
file: a heading line a sub-policy owns, a phrase a routed policy owns, or a
verbatim normative sentence reviewers must emit. It is matched after
normalization (blockquote markers, `**` and backticks removed, whitespace
collapsed). Similarity or duplication scores are never the blocking
signal: registration is explicit, so the check has no threshold to tune and
no false positives from intentional repetition (independent runbooks,
"not packaged" boilerplate).

Each anchor declares `id`, `group`, `text`, `owner`, `scope` (path globs
searched for restatements) and `allow` (path + reason entries).

| Group | Replaces / adds | Scope |
| --- | --- | --- |
| `routed-policy` | the old `ROUTED_POLICIES` phrase table | `AGENTS.md` |
| `github-index-owned` | the old `GITHUB_POLICY_OWNED_HEADERS` table | `skills/github-pr-review/policies/github-review.md` |
| `exact-string` | normative wording that must not drift unpinned | every text file outside `tests/` |

`ROUTED_POLICIES` in the instruction-architecture test and
`GITHUB_POLICY_OWNED_HEADERS` in `scripts/skill_metadata/expectations.py`
are now derived views of the registry.

## Blocking rules

- The owner file contains the anchor.
- No file in scope other than the owner contains it, unless allowlisted.
- Every allowlist entry uses a reason from the vocabulary and still
  contains the anchor (a stale entry fails, which doubles as a parity check
  for mirrored wording).
- No file is listed in the `files:` of more than one
  `capabilities/*/capability.yaml`.

## Allowlist reason vocabulary

- `design-record-mirror` — a `docs/` design record mirrors the owner's
  exact wording to specify the contract; the owner wins any conflict.
- `template-rendering` — an output template must render the anchor
  verbatim so reviewers emit it.
- `packaged-independence` — a packaged Skill resource must stay
  self-contained and cannot link to a repository-only owner.

Adding a reason is a maintainer decision made by editing the registry and
this list together.

## Deferred

The optional advisory containment scan (owner blocks located by file and
span, never failing the build) is not implemented.
