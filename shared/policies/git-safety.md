# Shared Policy — Git Safety

Applies to how both Code Review Skills inspect a target repository, and,
where this Skill repository's own development is concerned, to this
repository's own `AGENTS.md`.

## Preserve repository state

Both Skills perform read-only inspection of Git state. Neither commits,
pushes, rebases, resets, or otherwise mutates the repository it is
reviewing. (`github-pr-review` may publish comments/review decisions to
GitHub — that is a delivery action, not a Git mutation, and is governed by
that Skill's own `policies/github-review.md`.)

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
