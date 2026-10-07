# Workspace sibling context

## What it does

Some review questions can only be answered by a neighbouring repository: who
consumes this contract, does the producer really emit this field. When you
grant a **workspace root** — one local directory — the reviewer can resolve
that one unresolved question from a **sibling repository** inside it before
asking you, reading the sibling's **committed `HEAD`** read-only from its
object database. The sibling is evidence only: never a Review Target member,
never the location of a finding.

## When it is useful

- A contract change whose consumer lives in a repository checked out beside
  the one under review, and you would rather not name the repository and
  revision each time (for that, use
  [external contract context](external-contract-context.md), which takes
  precedence).
- A review that would otherwise end with a Context gap or a Reasoning check
  question a local checkout could answer.

## Which Skill(s)

`local-code-review` and `github-pr-review`. In GitHub mode it is available
only where the runtime has **local filesystem access to the granted root**;
API-only mode is unchanged. It does not clone, fetch, or use credentials
(remote second-repository reading is a separate capability).

## Default, conditional, or requested

**Conditional.** It loads only when you supply a workspace root in the
invocation **and** an eligible unresolved question arises. Without a root
nothing loads, is listed, or is read. The root is per invocation, never
remembered, and never taken from repository or PR content.

## How to use it

Supply the workspace root path in the invocation. There is no per-sibling
approval; the root and fixed bounds are the whole authorization (one listing
of immediate children, at most 3 siblings per review and 1 per question, no
recursion, secret-bearing paths never read). Parallel workers receive nothing.

## What you get

- Findings located in the Review Target, citing the sibling as
  `<repo>@<short-sha>:<path>` evidence, with provenance (repository, SHA,
  `workspace-resolved`, time, trust, dirty flag).
- If a sibling is ambiguous, absent, unreadable, or unconfirmed, no breakage
  claim and no "no consumers" statement: the question surfaces in Context
  gaps or the Reasoning check as it would have without the root.
- In `github-pr-review`, published output carries references only, never
  sibling content.

## Limitations

- Evidence answers the question and corroborates; it cannot alone make a
  finding `confirmed`.
- A dirty sibling is read at its commit, flagged as such, never through the
  uncommitted changes.
- Severity, finding identity, the confidence vocabulary, and the Decision are
  unchanged.

## Canonical sources

[`workspace-sibling-context.md`](../../shared/policies/workspace-sibling-context.md)
is the canonical contract; the per-Skill wiring is in each Skill's
`policies/workspace-sibling-context.md`. Design record:
[`../workspace-sibling-context/`](../workspace-sibling-context/README.md).
