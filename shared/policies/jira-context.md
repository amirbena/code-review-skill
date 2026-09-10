# Shared Policy — Jira Context Resolution

Applies identically to `local-code-review` and `github-pr-review`. It owns
the transport-neutral procedure for turning a **supplied Jira reference**
into normalized review context, and the precondition rules when a Jira
reference is supplied but cannot be resolved.

This is the resolution sub-domain of
[`review-context.md`](review-context.md): that file owns the four-concepts
context model, the input forms, precedence, and boundaries; a bare Jira
reference is resolved here before it can inform review reasoning
([`review-context.md`](review-context.md), "Reference-based context —
requires resolution"). Jira context informs scope but never expands the
Review Target, and Jira access is context retrieval only — the read-only /
no-Jira-mutation boundary is in [`review-context.md`](review-context.md),
"Boundaries".

## Jira context resolution

When the caller supplies a Jira reference, Jira context is resolved **before**
review reasoning, as an external-context-resolution step:

```text
Review Invocation
      ↓
optional Jira reference
      ↓
External Context Resolution  ──  Jira MCP / connector / equivalent Jira integration
      ↓
Normalized Review Context
      ↓
Review
```

### Capability, not a specific transport

Resolution depends on the capability "resolve Jira context," satisfied by
whatever Jira integration the runtime exposes — a Jira MCP server, a Jira
connector, or an equivalent runtime-exposed Jira read tool. Do not hard-code
review semantics to one transport. If the runtime already exposes a canonical
connector/tool model, use that rather than inventing a new abstraction. The
downstream shared review policies consume the **normalized** context below,
never a raw connector payload.

### Resolution procedure

When a Jira reference is supplied, before any review reasoning that depends on
scope, the reviewer performs these steps in order:

1. **Identify an available Jira-capable integration** — a Jira MCP server, a
   Jira connector, or another runtime-exposed Jira read tool. Use whichever
   the runtime actually exposes; do not require a specific one. If none is
   available, this is a resolution failure ("Resolution is a precondition
   when Jira is supplied" below) — stop, do not proceed as if Jira scope
   were known.
2. **Invoke it in read-only mode** to retrieve the referenced issue by its
   key or URL. "Retrieve" means an actual tool/connector call that returns
   the ticket's contents — never reading the key, the URL, a branch name, a
   PR title, a commit message, or any copied metadata.
3. **Retrieve relevant comments and linked requirement context** through the
   same integration when it supports them — issue comments, linked issues,
   and linked architecture/design references — scoped to what bears on the
   change under review.
4. **Normalize** the retrieved issue and comments into the `ReviewContext`
   shape ("What to retrieve and normalize" and "Jira comments" below) —
   never the raw connector payload.
5. **Continue only after successful resolution.** If step 1, 2, 3, or 4
   fails, do not fall back to the reference text or to inferred context:
   report `JIRA CONTEXT UNRESOLVED` and stop the Jira-scoped path.

This procedure is shared verbatim by both Skills; each runbook references it
rather than restating it, and only the Review Target differs
(`local-code-review` → the local delta; `github-pr-review` → the PR).

### Read-only

Jira access here is **context retrieval only**. This never edits an issue,
transitions it, adds a comment, changes a field, creates a ticket, or assigns
a user. No Jira mutation of any kind is introduced by supplying a Jira
reference.

### What to retrieve and normalize

When the integration supports it, retrieve the task context relevant to
understanding intended behavior and boundaries: issue key, summary,
description, issue type, current status, acceptance criteria, components,
labels, priority (where relevant), parent/epic (where relevant), linked
issues (only where materially necessary), relevant comments, linked
architecture/design information, explicit non-goals, constraints,
clarifications, and settled decisions.

Do not inject the entire raw Jira payload into review reasoning. Normalize
only what informs **intended behavior, task boundaries, requirements,
acceptance criteria, constraints, exclusions, and settled decisions** — into
the same `ReviewContext` shape used for free-form context ("Recommended
internal normalization" below).

### Jira comments

Jira comments can materially improve context, but a comment is **evidence, not
automatically an authoritative requirement**. Classify each relevant comment,
similarly to Existing Review Evidence
([`review-evidence.md`](review-evidence.md)):

- **settled clarification** — an explicit, agreed clarification of intent;
- **accepted decision** — a design/scope decision explicitly concluded;
- **implementation note** — guidance or context, not a pass/fail requirement;
- **unresolved question** — an open question with no agreed answer;
- **speculative suggestion** — an idea floated, not adopted;
- **rejected approach** — an option explicitly declined;
- **superseded discussion** — overtaken by later comments or a decision.

Do not promote every comment into an acceptance criterion. Only a settled
clarification or accepted decision that states an actual pass/fail condition
becomes an acceptance criterion. Prefer a newer explicit maintainer/product
clarification over stale speculative discussion when repository evidence
supports that interpretation.

### Resolution is a precondition when Jira is supplied

- **No Jira reference supplied** → review proceeds normally; nothing here
  applies.
- **Jira reference supplied and resolved** → review proceeds using the
  normalized Jira information as Review Context.
- **Jira reference supplied but not resolvable** — any of: no Jira
  integration is available; authentication fails; authorization fails (the
  identity cannot read the issue); the issue does not exist; the reference is
  malformed; or the integration/connector errors or times out → **do not**
  silently fall back to treating the key/URL as sufficient context, and
  **do not** infer ticket contents from the ticket key, the branch name, the
  PR title, a commit message, surrounding text, or copied issue metadata
  without the ticket's actual contents. The reviewer explicitly reports that
  the supplied Jira context could not be resolved and does **not** perform
  the Jira-scoped review. The concise outcome is `JIRA CONTEXT UNRESOLVED`:
  an explicit incapability report naming the reference and the integration(s)
  attempted, not a graded `REVIEW CLEAN` / `CHANGES REQUIRED` (local) or
  `Approve` / `Request Changes` (GitHub) result. Re-invoking **without** a
  Jira reference yields a normal unscoped review.

This precondition applies only to the Jira-scoped path of that specific
invocation. It never makes Jira required for reviews that do not supply one.
