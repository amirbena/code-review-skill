# Policy — Git Safety

Applies both to how the Code Review Agent inspects a target repository
and, where this Skill's own repository is being developed, to
[`../AGENTS.md`](../AGENTS.md).

## Preserve repository state

The Code Review Agent performs read-only inspection of Git state. It does
not commit, push, rebase, reset, or otherwise mutate the repository it is
reviewing, beyond what an explicit runbook (e.g. opening or updating a PR
once local review is clean) authorizes.

## Prohibited shortcuts

Destructive Git shortcuts are prohibited, including:

- `git reset --hard`
- `git clean -fd`
- force push
- branch deletion used merely to hide divergence
- history rewriting merely to simplify review

## On uncertainty

If the reviewed repository contains unexpected local commits, divergence,
ambiguous conflicts, unrelated uncommitted work, or uncertain merge
state:

```text
preserve state
→ inspect
→ report
→ do not guess
```

Do not silently discard or paper over anything that looks like existing
work.
