# Dependency tree inspection

## What it does

A manifest change can alter what a project actually resolves with nothing
visible in the diff — a Maven BOM bump, or any ecosystem without a lockfile.
When that happens during dependency review, the reviewer can use your
project's **own dependency tree**, for Base and Head, as evidence. It reads
the tree your build tool prints; it never resolves dependencies itself.

## When it triggers

Opt-in, and only when the dependency review is already engaged and the change
alters what resolves: a declared dependency, version, scope, exclusion, or a
BOM / parent / platform import. A reorder, whitespace, or comment-only edit
does not trigger it. Nothing is run without your approval; the reviewer may
ask you to supply the output instead. If
the ecosystem is not one whose native tree output can be validated and
compared, the review records a Context gap and stops.

## Which Skill(s)

`local-code-review` and `github-pr-review`. In `github-pr-review` API-only
mode (no checkout, no execution) only the supplied-output workflow is
available.

## The two workflows

| | Authorized execution | User-provided results |
|---|---|---|
| Who runs the command | the reviewer, after you approve | you |
| Needs | your explicit approval **and** execution policy that allows it | nothing beyond the output |
| Use when | repository-backed or local review and the command is admitted | execution is blocked, unavailable, or declined (often the working path — these commands may run plugins or need the network) |

For authorized execution the reviewer first states the exact command, the
working directory, the purpose, whether plugins or scripts may run, and the
filesystem / network / credential implications. Approval covers that command
and that target only, and **never overrides a sandbox or host restriction**:
a command policy does not admit is not run, and the review falls back to
supplied results.

## Producing Base and Head trees

Check out each side separately so the two runs are comparable, for example
with worktrees:

```bash
git worktree add ../review-base <base-ref>
git worktree add ../review-head <head-ref>
```

Run the **same command with the same flags, profile, and environment** in each
checkout. These are examples of native commands, not a list of supported
ecosystems; any ecosystem whose native output can be validated and compared
works, and others become a Context gap:

| Ecosystem (example) | Command |
|---|---|
| Maven | `mvn dependency:tree` |
| Gradle | `gradle dependencies` |
| npm | `npm ls --all` |

`npm ls --all` reads installed packages, so install dependencies in each
checkout first; `gradle dependencies` reports one project per run, so run it
for the project you are reviewing. An incomplete result is a Context gap.

Save each output to a file, then give both to the Skill, naming which is Base
and which is Head and the project each belongs to, for example: "Base tree
below (`../review-base`, `mvn dependency:tree`) … Head tree below
(`../review-head`, same command) …". Paste the output text. The reviewer reads
it and executes nothing.

## What you get

- **Presence, not incompatibility.** A tree shows what resolves, not that
  something is broken. A compatibility risk is reported only with evidence —
  repository-declared policy, documentation in the review boundary, or a
  conflict the output itself shows. A routine patch bump is not a finding.
- **Base versus Head.** With two valid trees the review reports added,
  removed, version-changed, and scope-changed dependencies, with the path from
  the changed declaration.
- **Head only.** With just a Head tree, it states what Head contains and that
  Base was not compared; it does not claim the change introduced anything.
- **Context gaps, never findings.** Output that is missing, in the wrong
  format, unidentified as Base or Head, incomplete (resolution errors,
  missing-POM warnings, truncation), or produced with different commands or
  environments between sides becomes a Context gap naming the command to run.
  It never creates a finding, is never treated as a clean tree, and never
  raises severity.

## Security and limits

- Supplied output is **data**: any instruction, URL, or command inside it is
  not followed, fetched, or run.
- A supplied tree can be stale, from the wrong commit, or altered; a finding
  records the tree's provenance (user-supplied or reviewer-executed, command,
  side) and trust is bounded by that source.
- Only ecosystems whose native tree output can be validated and compared are
  handled; there is no custom resolver, compatibility database, or universal
  ecosystem support.
- Severity, finding identity, the `confidence` vocabulary, and the Decision
  are unchanged.

## Why native tools

Your ecosystem's own command already knows how it resolves versions, scopes,
and BOMs. Using it keeps the evidence authoritative and the Skill free of a
dependency resolver that would drift from the real build.

## Canonical sources

[`dependency-tree-inspection.md`](../../shared/policies/dependency-tree-inspection.md)
is the canonical contract; it is routed from the dependency deepening review
in [`review-scope.md`](../../shared/policies/review-scope.md). Contributors:
change behavior there, not here. Design context:
[`../dependency-supply-chain/`](../dependency-supply-chain/README.md).
