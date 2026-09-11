# Contributing

Contributions are welcome. You do not need maintainer permission before
starting an open issue labeled `help wanted` or `good first issue`.

## Contribution paths

Issues carry an ownership label so you can tell at a glance what kind of
work an Issue is. `Good First Issue != unimportant`, and
`Contributor-owned != maintainer-only`.

### `good first issue`

Choose this when you are new to the repository and want a bounded task
whose expected behavior is already well defined — fixtures, regression
corpora, docs, bounded tests, or isolated tooling. You are primarily
implementing an established contract and can validate the result
deterministically without learning the whole reviewer. An Issue whose
Type is Infrastructure (label `type:infrastructure`) is an *automation*
good first issue: validators, packaging/reference checks, CI diagnostics,
or maintenance scripts.

### `contributor-owned`

Choose this when you are comfortable taking ownership of a whole
capability. The Issue defines boundaries, invariants, and acceptance
criteria but intentionally leaves the implementation and design approach
open. You are expected to investigate the repository, propose the
approach, and drive the work through implementation, tests,
documentation, and review. It may be large or hard — that is expected.

### `maintainer-led`

Semantic and architectural contracts — finding identity and semantics,
severity, the review decision, evidence thresholds, deduplication,
re-review state, GitHub enforcement, autofix authorization, privileged
release behavior, shared cross-Skill contracts. Do not claim the
core-semantic part of this work without coordinating on the Issue first.
A `maintainer-led` Epic often still has child Issues labeled
`good first issue` or `contributor-owned` that are open for you to take.

### A natural progression

```text
good first issue  →  bounded contributor work  →  contributor-owned capability / Epic
```

The full classification model is the canonical
[`policies/contribution-ownership-policy.md`](policies/contribution-ownership-policy.md);
this section is the human-facing summary.

## Choose and claim an issue

1. Choose an open, unclaimed issue with one of the contribution-ready labels.
2. Comment `/claim`. The bot adds `claimed` and records you as the claimant.
3. If you stop working on it, comment `/unclaim` so someone else can take it.

Claims do not use GitHub assignees, so contributors do not need repository
write access. A claim is a coordination signal, not a guarantee that a pull
request will be merged.

If a claim has no meaningful contributor activity for seven days, a
maintainer may release it with `/unclaim`. Maintainers should first check for
a linked pull request that is still progressing.

Only successful ownership changes contribute to churn protection: a claim of
an available issue or an authorized unclaim that actually releases it. Six
such changes by one actor within ten minutes temporarily disable that actor's
repository-wide claim ability for thirty minutes; `/unclaim` remains available.
Failed, unauthorized, duplicate, idempotent, or cooldown-rejected commands do
not count, and retries during a cooldown neither extend it nor generate repeated
bot replies. Maintainers can tune the three named `CLAIM_*` values in
`.github/workflows/claim-issue.yml`.

## Make the change

1. Fork the repository.
2. Create a focused branch in your fork using the convention below.
3. Implement the issue without adding unrelated changes.
4. Run the relevant validation listed in the root [README](README.md#contributing-to-this-repository).
5. Open a pull request against this repository and use `Fixes #<issue>` when
   the pull request should close the issue.

The issue form should define the problem, scope, acceptance criteria, and
validation before work is claimed. Ask on the issue if those boundaries are
unclear.

### Branch names

Use `<type>/<short-description>`, with a lowercase, concise, descriptive
kebab-case name for one logical task:

| Prefix | Use for |
| --- | --- |
| `feat/` | New functionality |
| `fix/` | Bug fixes |
| `docs/` | Documentation-only changes |
| `test/` | Test-only changes |
| `refactor/` | Restructuring without intended behavior changes |
| `chore/` | Repository, tooling, or maintenance work |
| `research/` | Research or analysis without implementation |

Describe the work, not its author: do not include usernames, coding-agent
names, timestamps, or random identifiers. An Issue number is optional (for
example, `fix/42-checkpoint-recovery`); the rest of the name must remain
understandable without GitHub. Good standalone names include
`chore/open-source-release-readiness` and `docs/contribution-workflow`.

## Changelog

Never edit `CHANGELOG.md`. When your change is *release-worthy* — it
affects shipped Skill content (`skills/`, packaged `shared/`) or the
packaging/distribution scripts — fill in the two release-intent lines of
the PR template instead:

- `Release category:` — `Added`, `Changed`, `Deprecated`, `Fixed`,
  `Security`, `Removed`, or `Breaking`;
- `Release entry:` — one line describing the change for users (the PR
  number is appended for you).

Leave `Release category: none` for anything else. The `Release worthiness`
check fails closed if a release-worthy PR has no valid release intent, and
its run summary shows the entry that will be generated; editing the
description re-runs it. The release automation writes the entry into
`CHANGELOG.md` when it publishes. Full convention:
[`docs/RELEASE.md`](docs/RELEASE.md).

## Review and merge

Starting work does not require approval; merging does. `main` remains
protected, and every pull request must satisfy the repository's checks and
review requirements before an authorized maintainer merges it. Claiming an
issue never bypasses review or guarantees merge.
