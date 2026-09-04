# Runtime validation evidence

## What it does

Lets a review **execute one repository-declared test, lint, or
validation command** and fold its result into the review as bounded
evidence. The reviewer resolves an exact command from the target
repository's own instruction sources (`AGENTS.md` / `CLAUDE.md`,
contribution or validation docs, a declared task-runner command), runs it
inside a disposable isolation boundary, and records exactly one outcome:

- `executed` — started and passed (with the observed exit status);
- `failed` — started and failed (failure evidence; becomes finding
  material when attributable to the change, with severity from impact);
- `skipped` — a declaration, scope, or safety gate was not met (with the
  reason);
- `unavailable` — a required local capability or the isolation boundary
  was missing (with the reason).

A passing run **adds evidence only** — it never removes, downgrades, or
rewrites a finding, and never changes the verdict mapping.

## When it is useful

- The repository documents a fast, focused check for the area you
  changed and you want the review to confirm it actually passes.
- You want a failing repository check surfaced as a review finding rather
  than discovered later.

## Which Skill(s)

Both, identically, when the reviewer considers a repository-defined
command.

## Default, conditional, or requested

**Conditional, and off unless every gate is met.** It requires a
trustworthy declared command *and* a runtime that can establish and
verify filesystem isolation, no host-secret access, denied network, no
Git/GitHub mutation capability, bounded non-interactive limits,
disposable state, and post-run verification that the tree was not
mutated. If the runtime has no such boundary, the command is recorded
`unavailable` — never run unsandboxed. The metadata capability value
`conditional` does not imply any current runtime supports live
execution.

## How to invoke it

There is no flag. The reviewer applies the policy automatically as part
of the normal flow; when isolation is available and the repository
declares a suitable command, the review's `Validation` section reports
the outcome. You do not enable it per invocation — you make it possible
by having a declared command and a runtime sandbox.

## Limitations & safety boundaries

- **Never a merge gate or a mutation capability.** It cannot approve,
  block by exit code, autofix, install dependencies, start services,
  deploy, or retry.
- **Command-source trust is not payload trust** — a declared command's
  code, hooks, and dependencies stay untrusted; destructive,
  secret-dependent, service-dependent, network-dependent, or interactive
  commands are skipped with a reason.
- `skipped` / `failed` / `unavailable` are **never** collapsed into "not
  run" or represented as passing. No declared command → the report says
  so explicitly.
- The isolated checkout used for context is **not** by itself the
  execution boundary.

## Canonical semantics

[`shared/policies/runtime-validation.md`](../../shared/policies/runtime-validation.md)
· pipeline placement in [`../ARCHITECTURE.md`](../ARCHITECTURE.md) §2.
