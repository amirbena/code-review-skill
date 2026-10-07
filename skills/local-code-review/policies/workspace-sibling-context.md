# Policy — Workspace Sibling Context (local adapter)

This Skill's thin wiring for the shared contract in
[`workspace-sibling-context.md`](../../../shared/policies/workspace-sibling-context.md),
which owns every rule: the grant, discovery, nomination, the
`workspace-resolved` read, provenance, trust, failure mapping, and privacy.
Implements GitHub Issue #663. Nothing is restated here; this file adds only
what is specific to local review.

## Loading

Read only when the caller supplied a workspace root in the current invocation
**and** an eligible unresolved question arose (the shared policy's
"Activation and resolution order"). Without a grant this file is not read and
no directory is listed.

## Wiring

- **Grant intake.** The root is invocation input only, never inferred from the
  working directory, a member's parent, or repository content. A rejected grant
  is named in Context gaps and unused.
- **Exclusion.** Every Review Target member — the single repository or each
  member of a multi-repository target, per
  [`multi-repository-review-target.md`](multi-repository-review-target.md) — is
  matched by realpath **and** Git common directory, so linked worktrees are
  excluded. The repository named by the explicit channel
  ([`external-contract-context.md`](external-contract-context.md)) is also
  excluded and keeps precedence.
- **Linked-worktree target.** The explicit root is required; this Skill never
  walks to the main checkout's parent.
- **Read.** The shared contract's `workspace-resolved` read reuses
  [`external-contract-context.md`](external-contract-context.md)'s hardened
  object-database mechanism and caps, with `workspace-resolved` as the selection
  basis and `workspace-granted-read-only` as trust.
- **Output.** Provenance rides the finding's `contextual evidence` field
  ([`finding.md`](../../../shared/templates/finding.md)). The private report may
  carry minimal excerpts; a finding is still located in the Review Target.
- **Workers.** Parallel workers and copies receive no root, listing, or
  evidence; a question a sibling could answer is reported up unresolved.
- **Failure.** Scoped to the question: it surfaces in Context gaps or the
  Reasoning check exactly as without this capability, never `REVIEW INCOMPLETE`
  on this basis, and never as an absence claim.
