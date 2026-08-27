# Policy — Optional Review Context (local application)

This Skill's **local application** of the shared review-context model. The
canonical semantics — the review-target / review-context / repository-context
/ existing-review-evidence concepts, the textual-vs-reference input forms,
**Jira context resolution** (its numbered "Resolution procedure" — identify
an available Jira MCP / connector / runtime Jira tool, read-only fetch the
issue, fetch relevant comments/linked context when supported, normalize,
continue only on success — and the `JIRA CONTEXT UNRESOLVED` precondition),
the evidence hierarchy, using context
to focus attention, context-mismatch handling, scope-boundary reasoning and
its precedence notes, explicit non-goals, scope discipline, and tracing
findings back to context — are owned by
[`review-context.md`](../../../shared/policies/review-context.md) and are not
restated here. This file adds only what is specific to `local-code-review`:
the review target is the **local implementation delta**, and supplied context
is mapped onto that delta, never onto files or concerns outside it.
[`../SKILL.md`](../SKILL.md) and
[`../runbooks/local-review.md`](../runbooks/local-review.md) state the
concise behavioral consequence and reference this file rather than
redefining it.

**If no review context is supplied, this file does not apply and nothing
in this Skill's behavior changes.** Everything below is additive and
strictly conditional on the caller providing one. This Skill never asks
the user to supply context when none was given — it is purely opt-in.

## Why this exists

A diff alone answers "what changed," not "what was this change supposed
to accomplish, and therefore what should be inspected carefully." When
the caller has requirements, acceptance criteria, an HLD, or a ticket
already in hand, supplying it lets this Skill focus its attention on the
execution paths, invariants, and regressions that actually matter for
this change, instead of reconstructing intent from the diff alone.

```text
Local Delta
  +
Supplied Review Context (intended behavior, acceptance criteria,
                          invariants, constraints, non-goals)
      ↓
 Context Understanding
      ↓
Focused Review of the Local Delta
      ↓
Final local-code-review decision
```

This is not a requirements audit and not a second complete review pass
over the surrounding system. It is a targeted focusing step that informs
the one local review this Skill always performs — the review's object
remains the current local delta.

## Input form

Review context is optional. It may arrive as **textual / free-form** content
(requirements, explicit user instructions, pasted Jira/ticket text and/or
acceptance criteria, a pasted GitHub Issue, an HLD/ADR, an implementation
plan, a bug/incident description, a PR/task description, or constraints) —
consumed directly — or as a **reference** (a Jira ticket key or URL, or a
GitHub Issue reference) that must be resolved first. See
[`review-context.md`](../../../shared/policies/review-context.md), "Input
form," and "Jira context resolution," for the full contract:

- a supplied **Jira reference** is resolved to normalized context via an
  available Jira MCP / connector / equivalent integration (read-only) before
  the local review reasons about it; if it cannot be resolved, this Skill
  returns `JIRA CONTEXT UNRESOLVED` and does not perform the Jira-scoped
  review — it never infers the ticket from the key, the branch name, or
  surrounding text;
- a supplied **GitHub Issue reference** is resolved through read-only GitHub
  access when available, or supplied as pasted text; no automatic PR↔Issue
  discovery;
- for a GitHub Issue's or Jira ticket's comments, apply
  [`review-evidence.md`](../../../shared/policies/review-evidence.md)'s
  settled-vs-speculative distinction.

An optional `Context source:` label aids traceability; an unlabeled
free-form block is equally valid. Supplying no Jira reference is always
valid — Jira is never mandatory for a local review.

## What this file does not restate

The following are owned by
[`review-context.md`](../../../shared/policies/review-context.md) and apply
here unchanged — this file does not duplicate them:

- **Recommended internal normalization** of supplied context.
- **Evidence hierarchy** — actual code/diff/tests/config outrank repository
  instructions, which outrank supplied context, which outranks reviewer
  inference. Supplied context never proves that something is implemented.
- **Using context to focus review attention** — derive concrete inspection
  targets from acceptance criteria, invariants, and non-goals.
- **Context mismatch vs. implementation defect** — a clear requirement
  violation is a finding (severity from actual impact, never the context's
  emphasis); stale/conflicting context or an ambiguous requirement is a
  note, not an automatic finding.
- **Scope-boundary reasoning** and its precedence notes — missing required
  behavior, contradiction of acceptance criteria, unrelated scope expansion,
  valid-but-out-of-scope findings, and repository-policy violations that hold
  regardless of ticket scope.
- **Explicit non-goals** — a stated non-goal narrows what must be *built*,
  never what must be *safe*.
- **Scope discipline** — context narrows attention within the review target,
  never widens it.
- **Tracing findings back to context** — provenance goes in the finding's own
  Evidence field, never as a duplicate listing.

## Local application

- The review target is the **current local delta** (committed / staged /
  unstaged / untracked, per
  [`repository-state.md`](repository-state.md)). Context-derived focus areas
  and scope-boundary reasoning apply to that delta; they never pull in files
  or commits outside it, and never replace the evidence the review step
  gathers from the actual code (see
  [`../runbooks/local-review.md`](../runbooks/local-review.md), step 7 and
  the review step).
- A finding that would not exist, or whose severity would not be justified,
  without supplied context records that provenance in its own Evidence field
  per [`../../../shared/templates/finding.md`](../../../shared/templates/finding.md).

## Output

Do not add output noise. Supplied context that had no material effect on
the review is not called out. When context materially shaped the review
— it focused attention that produced a finding, surfaced a mismatch
worth flagging, or its non-goals prevented a false gap being reported —
state it concisely in the optional "Context" section of
[`../templates/local-review-report.md`](../templates/local-review-report.md).
The report's existing shape and decision labels (`REVIEW CLEAN` /
`CHANGES REQUIRED`) are unchanged by this policy; see
[`severity.md`](../../../shared/policies/severity.md), "Decision
derivation (mechanical)" — context informs which findings exist and their
severity classification exactly as any other evidence source would, it
never adds a separate decision path.

## Boundary with invocation approval and mutation boundary

Supplying review context is never itself approval to invoke this Skill,
and never bypasses the per-invocation, current-interaction,
explicit-approval requirement in
[`invocation-approval.md`](invocation-approval.md), which is unchanged
and fully in force. Context is read-only input to this Skill's own
review reasoning; it never grants this Skill any additional capability —
this Skill's [mutation boundary](../SKILL.md) is unchanged, and context
can never authorize editing files, applying patches, committing, pushing,
or any GitHub mutation.

## Backward compatibility

Review context is strictly optional. Existing invocations that supply no
context continue to work exactly as before this policy existed — this
Skill reasons from repository/diff-driven review alone, with no reference
to a missing input.
