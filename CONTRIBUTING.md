# Contributing

Contributions are welcome. You do not need maintainer permission before
starting an open issue labeled `help wanted` or `good first issue`.

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

## Make the change

1. Fork the repository.
2. Create a focused branch in your fork.
3. Implement the issue without adding unrelated changes.
4. Run the relevant validation listed in the root [README](README.md#contributing-to-this-repository).
5. Open a pull request against this repository and use `Fixes #<issue>` when
   the pull request should close the issue.

The issue form should define the problem, scope, acceptance criteria, and
validation before work is claimed. Ask on the issue if those boundaries are
unclear.

## Review and merge

Starting work does not require approval; merging does. `main` remains
protected, and every pull request must satisfy the repository's checks and
review requirements before an authorized maintainer merges it. Claiming an
issue never bypasses review or guarantees merge.
