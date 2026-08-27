# Runbook — Local Review

The single runbook for `local-code-review`. This runbook defines
**execution flow, phase ordering, and which policy governs each phase** —
it is not a second copy of any policy's semantics. Where a step names a
policy, that policy's own text is authoritative; this runbook says only
when that policy is invoked and how its output feeds the next phase. Where
prose here appears to restate a rule, the linked policy governs in case of
any apparent difference.

Applies shared policies:
[`review-scope.md`](../../../shared/policies/review-scope.md),
[`severity.md`](../../../shared/policies/severity.md),
[`evidence.md`](../../../shared/policies/evidence.md),
[`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
[`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
[`git-safety.md`](../../../shared/policies/git-safety.md),
[`review-context.md`](../../../shared/policies/review-context.md) (the shared
review-target / review-context / repository-context / existing-review-evidence
model — its requirement-context and scope-boundary sections bind only when
context is supplied), and the shared human-facing output shape in
[`review-summary.md`](../../../shared/templates/review-summary.md), plus
this Skill's own
[`../policies/invocation-approval.md`](../policies/invocation-approval.md)
(the invocation-approval precondition assumed below) and
[`../policies/repository-state.md`](../policies/repository-state.md) (the
committed/staged/unstaged/tracked/untracked category definitions,
per-category detection commands, push/synchronization status, and the
staged-delta fingerprint and its re-review comparison contract — this
runbook's single source for all of that Git-mechanics detail). When the
caller supplies review context, also
[`../policies/review-context.md`](../policies/review-context.md) (this
Skill's thin local application of the shared model — mapping supplied
requirements/Jira/GitHub-Issue/HLD/ADR/plan context onto the local delta and
reasoning about the requested change's scope boundary) — never loaded or
applied otherwise. When the caller supplies a PR reference, also
[`review-evidence.md`](../../../shared/policies/review-evidence.md) (the
shared Existing Review Evidence model) and
[`../policies/pr-context.md`](../policies/pr-context.md) (this Skill's thin
local application: retrieval scope and reconciliation of prior findings,
prior review comments, and settled decisions against the local delta) —
never loaded or applied otherwise.

## Flow

```text
resolve local review scope
    ↓
discover applicable AGENTS.md / CLAUDE.md
    ↓
detect each category separately: committed, staged, unstaged, untracked
    ↓
compute staged-delta fingerprint
    ↓
review context supplied? → yes → resolve any Jira reference first (Jira
                                   MCP/connector, read-only); unresolvable →
                                   JIRA CONTEXT UNRESOLVED, stop. Then
                                   understand intended change, extract
                                   requirements/invariants/non-goals, map
                                   onto the delta established above
                                 → no  → unchanged
    ↓
PR reference supplied? → yes → read/classify/reconcile relevant PR
                                 context against the delta established
                                 above (scope never expands to the PR)
                               → no  → unchanged
    ↓
inspect relevant surrounding code
    ↓
review against code + repository conventions, focused per any supplied
review context
    ↓
classify findings by severity (source never changes the classification)
    ↓
derive decision mechanically from blocking severities (P0/P1)
    ↓
return P0/P1/P2 findings, each attributed to its source category
    ↓
stop
```

## Execution efficiency (does not change what is inspected)

Steps 1–5 below are read-only Git inspection commands, but they are not
all mutually independent — batch only the commands that have no data
dependency on another command's output, and never batch a command
concurrently with the command that resolves a value it needs:

- **Step 1** (verify the repository, inspect branch/HEAD) depends on
  nothing below and may always be issued first, on its own or batched
  with step 4 and/or step 5 (see below).
- **Step 2** (resolve `<base>` and the base SHA) depends on step 1 having
  established a valid repository and current branch, and must complete
  — with `<base>` actually resolved — before any command that references
  `<base>` is issued. In particular, step 3's committed-delta detection
  (`git log <base>..HEAD`, `git diff <base>...HEAD`) requires a resolved
  `<base>` as a literal command argument; it cannot be batched concurrently
  with step 2 itself, only after step 2 completes.
- **Step 3's four category-detection commands** (committed, staged,
  unstaged, untracked) do not depend on one another's output. Once `<base>`
  is resolved (after step 2), issue all four together as a single
  batched/parallel operation (e.g. one combined shell invocation, or
  parallel tool calls in one turn) rather than one command at a time in
  sequence.
- **Step 4** (staged fingerprint) and **step 5** (sync status) reference
  no value resolved by steps 2 or 3 — both are self-contained per
  [`../policies/repository-state.md`](../policies/repository-state.md).
  Both may be batched with step 1, with each other, or with step 3's
  batch, at the caller's discretion; neither needs to wait for `<base>`
  resolution.

Concretely: batch {1, 4, 5} freely at any point; resolve `<base>` in step
2 before issuing step 3's `<base>`-dependent command; batch step 3's four
commands together once `<base>` is known. This changes only how many
round-trips retrieving this state costs and in what groupings — never
which categories are detected, which commands are used, the order in
which a value must be resolved before it is used, or what is reported.

## Steps

1. Verify the target is a valid Git repository; inspect working-tree
   status, current branch, and HEAD.
2. Resolve the base branch and base SHA. Verify the implementation scope
   is not accidentally being reviewed directly on a protected/default
   branch unless the target repository's own rules explicitly permit it.
   **Do not create a branch** — validate what already exists; branch
   creation belongs to the implementing workflow.
3. Determine the **complete** local delta — do not assume local `HEAD`
   contains the whole task, and do not blend categories into one
   undifferentiated set. Detect each category with its own command per
   [`../policies/repository-state.md`](../policies/repository-state.md),
   "Detection commands per category" — committed (relative to `<base>`,
   never to push status; see that policy's "Committed delta is not push
   status"), staged, unstaged, and untracked, each independently. Record,
   for the report, whether each category is included in this review's
   scope or explicitly excluded — never silently omitted without saying
   so (see
   [`../templates/local-review-report.md`](../templates/local-review-report.md)).
4. Compute the **staged-delta fingerprint** per
   [`../policies/repository-state.md`](../policies/repository-state.md),
   "Staged delta fingerprint," and record it for the report. If this
   invocation is a re-review and the caller supplied the previously
   reported fingerprint as context, compare the two per that policy's
   "Fingerprint scope and re-review comparison" and this runbook's
   "Re-review discipline" below.
5. Determine push/synchronization status per
   [`../policies/repository-state.md`](../policies/repository-state.md),
   "Push / synchronization status" — against the branch's own configured
   upstream, never against step 3's base-relative committed delta.
   Informational for the report; not a decision this Skill makes.
6. **Discover applicable repository-local instructions** per
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
   "Deduplicated discovery" and "Normalized Repository Instruction Context,"
   for every changed file. Resolve the root-to-specific chain once from the
   current local snapshot; unrelated subtrees are not scanned and the local
   delta remains the Review Target. Do this before reviewing so discovered
   conventions inform the review itself, not just a post-hoc check.
7. **If, and only if, the caller supplied review context:** apply the
   shared [`review-context.md`](../../../shared/policies/review-context.md)
   and this Skill's thin
   [`../policies/review-context.md`](../policies/review-context.md) in full
   now — after the local delta (steps 1–4) and repository-instruction
   discovery (step 6), and before PR-context reconciliation (step 8, if
   applicable) and the review step below.
   - **7a. Resolve reference-based context first.** If the caller supplied a
     **Jira reference** (key or URL), execute the shared
     [`review-context.md`](../../../shared/policies/review-context.md), "Jira
     context resolution" → **"Resolution procedure"** in order: (1) identify
     an available Jira MCP / connector / runtime-exposed Jira read tool;
     (2) invoke it **read-only** to fetch the referenced issue's contents
     (not the key/URL/branch/PR-title/commit/copied metadata); (3) fetch
     relevant issue comments and linked requirement context when the
     integration supports them; (4) normalize the issue and comments into
     Review Context (classify comments per "Jira comments" — do not promote
     every comment to an acceptance criterion); (5) continue only after
     successful resolution. If **any** of steps 1–4 fails — no integration
     available, authentication failure, authorization failure, issue not
     found, malformed reference, or connector/MCP error or timeout — stop the
     Jira-scoped path: return `JIRA CONTEXT UNRESOLVED` naming the reference
     and the integration(s) attempted, do **not** infer the ticket from its
     key, the branch name, the PR reference's title, a commit message,
     surrounding text, or copied metadata, and do **not** grade the review. A
     GitHub Issue **reference** is resolved through read-only GitHub access
     when available, or supplied as pasted text; no automatic PR↔Issue
     discovery. Pasted/free-form context needs no resolution.
   - **7b.** With context (resolved where reference-based) in hand, follow
     the policies' context-understanding procedure: extract requirements/
     invariants/non-goals, map them onto the delta established above, and
     reason about the requested change's scope boundary per the shared
     policy's "Scope-boundary reasoning." This runbook does not restate it.

   If no review context was supplied, skip this step entirely and proceed
   directly to step 8 — this step never prompts the user for context when
   none was supplied.
8. **If, and only if, the caller supplied a PR reference:** apply the shared
   [`review-evidence.md`](../../../shared/policies/review-evidence.md) and
   this Skill's thin
   [`../policies/pr-context.md`](../policies/pr-context.md) in full now —
   after the local delta (steps 1–4), repository-instruction discovery
   (step 6), and review-context understanding (step 7, if applicable),
   and before the review step below. Those policies own the complete
   retrieval, classification, and reconciliation procedure (resolving the
   PR reference; retrieving only relevant threads; classifying each prior
   finding/comment as still-relevant, resolved, stale, duplicate, a settled
   decision, or speculative discussion; and reconciling it against the
   current local delta without blindly inheriting it); this runbook does
   not restate them. If no PR reference was supplied, skip this step
   entirely and proceed directly to the review step below.
9. Review the complete delta against
   [`review-scope.md`](../../../shared/policies/review-scope.md) and the
   file-treatment rules in
   [`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
   applying **all applicable upstream context established above** —
   repository instructions (step 6), the review-focus mapping from
   supplied review context (step 7, if applicable), and reconciled
   PR-context findings/decisions (step 8, if applicable) — and inspecting
   relevant surrounding repository code and tests. Review context and PR
   context still only ever *focus* this step, per their own policies'
   scope-discipline rules — they never expand review scope beyond the
   current local delta and never substitute for the evidence this step
   itself gathers from the actual code. This step applies
   [`review-scope.md`](../../../shared/policies/review-scope.md) in full,
   including "Related changes as one unit," "Existing behavior ownership,"
   and "Failure state, retry safety, and recovery" (the last two
   signal-triggered per that policy's own gating conditions — not applied
   unconditionally to every diff), and
   [`evidence.md`](../../../shared/policies/evidence.md), "Findings beyond
   the changed lines," when a finding depends on code outside the delta.
   These are the same shared review-quality invariants `github-pr-review`
   applies to a PR; this runbook does not restate their full text.
   Target-repository instructions refine how the code is evaluated; they
   never override this Skill's own safety boundaries (see
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
   "Instruction precedence").
10. Classify findings per
    [`severity.md`](../../../shared/policies/severity.md), each backed by
    evidence and impact per
    [`evidence.md`](../../../shared/policies/evidence.md), using the
    shared finding shape in
    [`finding.md`](../../../shared/templates/finding.md). Attribute each
    finding to its source category per
    [`../policies/repository-state.md`](../policies/repository-state.md),
    "Attribution in findings." When step 7 and/or step 8 ran, trace a
    finding's provenance back to supplied review context or reconciled PR
    context per those policies' own "Tracing findings back to context" /
    "Avoiding duplicate findings" rules, rather than reporting the same
    underlying issue twice. Finalize the complete set of findings —
    including any that were revised, merged, or discarded during review —
    before composing the report; do not report findings piecemeal as they
    are discovered.
11. Derive the Decision mechanically per
    [`severity.md`](../../../shared/policies/severity.md), "Decision
    derivation (mechanical)," from the finalized findings. This is the
    only path to the decision — no independent, subjective judgment on
    top of it.
12. Compose the human-facing body per
    [`review-summary.md`](../../../shared/templates/review-summary.md),
    including the terse optional "Context" / "PR Context" notes per
    [`../templates/local-review-report.md`](../templates/local-review-report.md)
    when steps 7/8 ran and materially shaped the review.
13. Render
    [`../templates/local-review-report.md`](../templates/local-review-report.md)
    as one complete report — including the review scope contract fields
    (review base, per-category inclusion/exclusion, initial-review-vs-
    re-review, and, per that template's own "Relevance-aware metadata
    rendering," the staged fingerprint and whether previously reviewed
    state changed) — and return it. **Stop.**

## Constraints

- Must not mutate GitHub state.
- Must not modify implementation files, apply patches, commit, push,
  rebase, create branches, or open PRs.
- Must not decide whether to run again, count iterations, or control the
  implementing Agent — see
  [`../SKILL.md`](../SKILL.md), "Statelessness and Orchestration
  Boundary."
- Must not otherwise mutate the repository beyond read-only inspection
  (see [`git-safety.md`](../../../shared/policies/git-safety.md)).
- Must not ask the user for approval, and must not be invoked as a
  self-triggered re-run. This runbook assumes the caller has already
  obtained fresh, explicit user approval scoped to this specific
  invocation before entering this flow — see
  [`../policies/invocation-approval.md`](../policies/invocation-approval.md)
  for the complete, self-contained contract. This runbook does not
  verify that approval was obtained; that responsibility belongs
  entirely to the caller.

## Re-review discipline (recommended, not enforced by this Skill)

Each invocation of this runbook is independent and stateless. Every
invocation, including a re-review immediately after fixes, requires its
own separate, fresh, explicit user approval — the approval that
authorized a previous invocation never authorizes this one. When an
orchestrator has obtained that new approval and chooses to invoke this
runbook again against updated implementation state, it should primarily
verify:

- whether previously reported blocking findings were resolved;
- whether the fix introduced a regression;
- whether newly changed code creates a new blocking issue.

Do not use a re-review as license for unbounded scope expansion. That
said, a newly discovered P0/P1 with concrete evidence must still be
reported even if it wasn't visible in an earlier pass — do not suppress a
real finding merely because it is new.

Before treating a matching staged-delta fingerprint as a short-circuit for
the staged category, this runbook's step 4 above applies the complete
precondition and comparison contract owned by
[`../policies/repository-state.md`](../policies/repository-state.md),
"Fingerprint scope and re-review comparison" — including which files must
be materially unchanged for the short-circuit to apply at all, and how a
match, a difference, and an unestablished precondition are each handled.
That policy is the single canonical owner of this contract; this runbook
does not duplicate it. Unstaged and untracked state carry no fingerprint
and are independently (re-)detected via step 3's own commands on every
invocation regardless of the staged-fingerprint result — see that same
policy section.
