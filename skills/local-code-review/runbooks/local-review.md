# Runbook — Local Review

The single runbook for `local-code-review`. Applies shared policies:
[`review-scope.md`](../../../shared/policies/review-scope.md),
[`severity.md`](../../../shared/policies/severity.md),
[`evidence.md`](../../../shared/policies/evidence.md),
[`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
[`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
[`git-safety.md`](../../../shared/policies/git-safety.md), and the shared
human-facing output shape in
[`review-summary.md`](../../../shared/templates/review-summary.md), plus
this Skill's own
[`../policies/invocation-approval.md`](../policies/invocation-approval.md)
(the invocation-approval precondition assumed below) and
[`../policies/repository-state.md`](../policies/repository-state.md)
(the committed/staged/unstaged/tracked/untracked category definitions,
per-category detection commands, and the staged-delta fingerprint used
below). When the caller supplies review context, also
[`../policies/review-context.md`](../policies/review-context.md)
(interpretation, evidence hierarchy, and review-focus mapping for that
optional input) — never loaded or applied otherwise. When the caller
supplies a PR reference, also
[`../policies/pr-context.md`](../policies/pr-context.md) (retrieval
scope, classification, finding reconciliation, and architectural-decision
handling) — never loaded or applied otherwise.

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
review context supplied? → yes → understand intended change, extract
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
  no value resolved by steps 2 or 3 — `git diff --cached --raw -M -z` and
  the `@{u}`-relative commands are self-contained. Both may be batched
  with step 1, with each other, or with step 3's batch, at the caller's
  discretion; neither needs to wait for `<base>` resolution.

Concretely: batch {1, 4, 5} freely at any point; resolve `<base>` in step
2 before issuing step 3's `<base>`-dependent command; batch step 3's four
commands together once `<base>` is known. This changes only how many
round-trips retrieving this state costs and in what groupings — never
which categories are detected, which commands are used, the order in
which a value must be resolved before it is used, or what is reported —
every category below is still independently detected and independently
attributed exactly as written.

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
   "Detection commands per category":
   - **Committed** delta relative to base: `git log <base>..HEAD --oneline`
     (commits) and `git diff <base>...HEAD` (content; files:
     `git diff --name-status <base>...HEAD`). This is relative to the
     **review base**, not to the branch's upstream — it says nothing
     about push status; see step 5 for that, and
     [`../policies/repository-state.md`](../policies/repository-state.md),
     "Committed delta is not push status."
   - **Staged** (tracked, indexed) delta: `git diff --cached` (files:
     `git diff --cached --name-status`).
   - **Unstaged** (tracked, working-tree-only) delta: `git diff`
     (files: `git diff --name-status`).
   - **Untracked** files: `git ls-files --others --exclude-standard`.

   ```text
   base         = A
   local HEAD   = B
   staged       = S (index vs. B)
   unstaged     = U (working tree vs. index)
   untracked    = T (working tree, not tracked)

   Review: A → B + S + U + T, each category attributed separately
   ```

   Record, for the report, whether each category is included in this
   review's scope or explicitly excluded — never silently omitted
   without saying so (see
   [`../templates/local-review-report.md`](../templates/local-review-report.md)).
4. Compute the **staged-delta fingerprint** per
   [`../policies/repository-state.md`](../policies/repository-state.md),
   "Staged delta fingerprint": run `git diff --cached --raw -M -z` and
   take the SHA-256 hash of its exact raw stdout bytes — never of a
   filename list, a human-readable diff, or a newline-converted form of
   that output. Record the resulting fingerprint for the report. If this
   invocation is a re-review and the caller supplied the previously
   reported staged fingerprint as context, compare the two per
   [`../policies/repository-state.md`](../policies/repository-state.md),
   "Fingerprint scope and re-review comparison," and "Re-review
   discipline" below — a match means the staged delta is unchanged since
   the prior review; a difference means it must be reviewed as new
   delta. This comparison says nothing about unstaged or untracked
   state, which are independently (re-)detected via their own commands
   above on every invocation regardless of the staged-fingerprint
   result.
5. Determine push/synchronization status against the branch's own
   configured upstream — this is the single source of truth for
   "local-only"/"not yet pushed" commits, never step 3's base-relative
   committed delta. Resolve local ahead/behind/diverged state with
   `git log @{u}..HEAD --oneline` (local-only, unpushed commits) and
   `git log HEAD..@{u} --oneline` (remote-only commits not yet merged
   locally), or the equivalent ahead/behind counts. If the branch has no
   configured upstream (resolving `@{u}` fails), report "no tracking
   branch configured" explicitly — do not guess or substitute an assumed
   `origin/<branch>` ref. This is informational for the report and the
   caller, not a decision this Skill makes on its own.
6. **Discover applicable repository-local instructions** per
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md):
   for each changed file, look for `AGENTS.md` / `CLAUDE.md` at the
   target repository root and along that file's directory ancestry, using
   that policy's "Deduplicated discovery" procedure — compute the union of
   candidate paths across all changed files first, read each unique
   candidate at most once, then apply results per file by ancestry
   membership, rather than repeating a read for every file that happens to
   share an ancestor directory. Do this before reviewing so discovered
   conventions inform the review itself, not just a post-hoc check.
7. **If, and only if, the caller supplied review context:** apply
   [`../policies/review-context.md`](../policies/review-context.md) now,
   after the local delta (steps 1-4) and repository-instruction
   discovery (step 6) are both established, and before PR-context
   reconciliation (step 8, if applicable) and the review step below —
   this is the "Context understanding" phase:
   1. Read the supplied context in full.
   2. Identify the intended change it describes.
   3. Extract the important requirements, acceptance criteria, and
      invariants it states.
   4. Identify any explicit non-goals it states.
   5. Map those requirements/invariants onto the relevant areas of the
      current local delta established in steps 1-4 — never onto files or
      concerns outside that delta.
   6. Carry that mapping into the review step below as focus, per
      [`../policies/review-context.md`](../policies/review-context.md),
      "Using context to focus review attention" — it directs *where to
      look carefully*, never a conclusion the review is forced to reach;
      the implementation is still inspected to determine whether
      described behavior actually exists, per that policy's "Evidence
      hierarchy."

   If no review context was supplied, skip this step entirely — proceed
   directly to step 8 exactly as this runbook already did before this
   step existed. This step never prompts the user for context when none
   was supplied.
8. **If, and only if, the caller supplied a PR reference:** apply
   [`../policies/pr-context.md`](../policies/pr-context.md) now, after
   the local delta (steps 1-4), repository-instruction discovery (step
   6), and review-context understanding (step 7, if applicable) are
   established, and before the review step below:
   1. Resolve the PR reference; if it cannot be resolved or no GitHub
      read capability is available, note the limitation and continue as
      if no PR reference had been supplied.
   2. Retrieve only PR review threads/comments relevant to the current
      local delta — never the PR's full historical diff or unrelated
      metadata.
   3. Classify each relevant thread per
      [`../policies/pr-context.md`](../policies/pr-context.md),
      "Classifying PR review context," reasoning over each thread as a
      whole and preferring its latest explicit resolution.
   4. Map relevant findings and settled architectural/design decisions
      onto the current local delta — status per "Reconciling existing
      reviewer findings" and "Architectural/design decisions" in that
      policy.
   5. Determine what still needs independent (re-)evaluation: a
      reconciled "still present" or "requires re-evaluation" finding, or
      a violated decision, feeds into this Skill's own review below
      rather than being independently rediscovered from scratch; a
      "resolved" finding or a followed/intentionally-superseded decision
      needs no further action.

   If no PR reference was supplied, skip this step entirely — proceed
   directly to the review step below exactly as this runbook already
   did before this step existed.
9. Review the complete delta against
   [`review-scope.md`](../../../shared/policies/review-scope.md) and the
   file-treatment rules in
   [`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
   applying **all applicable upstream context established above** —
   repository instructions (step 6), the review-focus mapping from
   supplied review context (step 7, if applicable), and reconciled
   PR-context findings/decisions (step 8, if applicable) — and inspecting
   relevant surrounding repository code and tests. This is a
   cross-reference to those steps' own output, not a restatement of them:
   review context and PR context still only ever *focus* this step, per
   their own policies' scope-discipline rules — they never expand review
   scope beyond the current local delta and never substitute for the
   evidence this step itself gathers from the actual code. In particular,
   apply [`review-scope.md`](../../../shared/policies/review-scope.md),
   "Related changes as one unit" — review related files/hunks in the
   delta together rather than in isolation, including following a changed
   contract/return value/exception to its actual callers — and
   [`evidence.md`](../../../shared/policies/evidence.md), "Findings beyond
   the changed lines," when a finding depends on code outside the delta.
   When the delta's own shape gives concrete reason to, also apply
   [`review-scope.md`](../../../shared/policies/review-scope.md),
   "Existing behavior ownership" (a targeted search for whether this delta
   duplicates an existing canonical owner of the behavior it introduces)
   and "Failure state, retry safety, and recovery" (partial-failure state,
   retry/idempotency safety, evidenced recovery, and proportional
   observability, reasoned about as one signal-triggered move, per that
   section's own trigger conditions). These are the same shared
   review-quality invariants `github-pr-review` applies to a PR; this
   runbook does not restate their full text.
   Target-repository instructions refine how the code is evaluated; they
   never override this Skill's own safety boundaries (see
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
   "Instruction precedence").
10. Classify findings per
   [`severity.md`](../../../shared/policies/severity.md), each backed by
   evidence and impact per
   [`evidence.md`](../../../shared/policies/evidence.md), using the shared
   finding shape in
   [`finding.md`](../../../shared/templates/finding.md). Severity is
   independent of a finding's source: a finding derived from a target
   repository's own convention (step 6) is classified against the same
   P0/P1/P2 definitions as any other finding, never automatically
   escalated to a blocking severity merely because the source repository
   states the convention emphatically — see
   [`severity.md`](../../../shared/policies/severity.md), "Repository
   conventions and severity." Attribute each
   finding to the source category it came from — committed, staged,
   unstaged, or untracked — per
   [`../policies/repository-state.md`](../policies/repository-state.md),
   "Attribution in findings." When step 8 ran, a finding reconciled from
   PR context (still-present or requiring re-evaluation) says so in its
   evidence rather than presenting itself as newly discovered, and a
   violated architectural decision is reported as its own finding per
   [`../policies/pr-context.md`](../policies/pr-context.md); do not
   report the same underlying issue twice merely because both PR context
   and this review independently identified it. Likewise, when step 7
   ran, a finding that materially traces back to supplied review context
   says so in its evidence per
   [`../policies/review-context.md`](../policies/review-context.md),
   "Tracing findings back to context" — used sparingly, not on every
   finding. Finalize the complete set of findings — including any that
   were revised, merged, or discarded during review — before composing
   the report. Do not report findings piecemeal as they are discovered;
   the report in step 12 is composed once, from the finalized set.
11. Derive the Decision mechanically per
    [`severity.md`](../../../shared/policies/severity.md), "Decision
    derivation (mechanical)": compute `blocking_findings` as the
    finalized findings whose severity is `P0` or `P1`; the decision is
    `REVIEW CLEAN` when that set is empty and `CHANGES REQUIRED`
    otherwise. This is the only path to the decision — do not layer an
    independent, subjective "should this really block" judgment on top
    of it, and do not let a strongly-worded repository convention, a
    strongly recommended P2, or reconciled context (step 7/8) push the
    decision to `CHANGES REQUIRED` when `blocking_findings` is empty. All
    finalized findings, including any P2s, remain reported in Findings
    regardless of the decision — a clean decision never means the
    findings list is emptied or downgraded to obtain it.
12. Compose the human-facing body per
    [`review-summary.md`](../../../shared/templates/review-summary.md):
    a concrete "What changed" summary, an evidence-backed "What was done
    well" (omit or keep to one line if nothing concrete stands out), the
    finalized findings, the Decision derived in step 11, and a
    "Validation" section listing only what was actually inspected or
    executed by this review — do not claim a validation step ran if it
    did not. When step 7 (review context) materially shaped the review,
    include the terse "Context" note per
    [`../templates/local-review-report.md`](../templates/local-review-report.md);
    when step 8 (PR context) ran and materially shaped the review,
    include the terse "PR Context" note per that same template — each is
    omitted entirely when its respective input was not supplied or had
    no material effect.
13. Render
    [`../templates/local-review-report.md`](../templates/local-review-report.md)
    as one complete report — including the review scope contract fields
    (review base, per-category inclusion/exclusion, staged fingerprint,
    initial-review-vs-re-review, and whether previously reviewed state
    changed) — and return it. **Stop.**

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

### Precondition: the applicable review standard must be unchanged

The staged-delta fingerprint proves only that the *reviewed content* is
byte-identical to what a prior invocation fingerprinted — it says
nothing about whether the *review standard applied to that content* is
also unchanged. A matching content fingerprint is **not by itself**
sufficient to reuse prior reasoning; before applying the short-circuit
below, the caller/orchestrator must first establish that everything this
Skill's review reasoning actually depends on is materially unchanged
since the prior review whose fingerprint is being compared against:

- this Skill's own [`../SKILL.md`](../SKILL.md);
- this runbook ([`local-review.md`](local-review.md));
- this Skill's own policies
  ([`../policies/invocation-approval.md`](../policies/invocation-approval.md),
  [`../policies/repository-state.md`](../policies/repository-state.md),
  and, when applicable,
  [`../policies/review-context.md`](../policies/review-context.md) and
  [`../policies/pr-context.md`](../policies/pr-context.md));
- the shared review policies
  ([`review-scope.md`](../../../shared/policies/review-scope.md),
  [`severity.md`](../../../shared/policies/severity.md),
  [`evidence.md`](../../../shared/policies/evidence.md),
  [`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
  [`git-safety.md`](../../../shared/policies/git-safety.md),
  [`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
  and, in orchestrated/multi-Agent contexts,
  [`review-ownership.md`](../../../shared/policies/review-ownership.md));
- the target repository's own applicable instructions (`AGENTS.md`,
  `CLAUDE.md`, and any other repository-local context discovered in step
  6) for the files in the staged category.

This does not require a new persisted cryptographic fingerprint over
those files. Establishing "materially unchanged" is the
caller's/orchestrator's responsibility — for example, because nothing in
this list was touched between the two invocations in the same
session/task, or because the caller has otherwise confirmed their
content is identical. If any of these materially changed, the
fingerprint-match short-circuit below **does not apply** to the staged
category: treat it as requiring fresh reasoning under the current
standard, exactly as if the fingerprint had not matched, regardless of
what the content fingerprint alone reports. This precondition narrows
when the short-circuit may be used; it never narrows what steps 1–11
above require, and it never substitutes for re-verifying previously
reported blocking findings, discovering new P0/P1s, or independently
(re-)detecting unstaged/untracked state — see those existing
requirements below and in step 3.

When the caller supplies the previously reported staged-delta
fingerprint as re-review context **and the precondition above holds**,
compare it against the fingerprint freshly computed in step 4 above, per
[`../policies/repository-state.md`](../policies/repository-state.md),
"Fingerprint scope and re-review comparison":

- **Match** — this is a safe, testable short-circuit: skip re-deriving
  review reasoning for the staged category from scratch, and instead
  spend that effort verifying whether each previously reported blocking
  finding in the staged delta was actually resolved. This never shrinks
  scope — the staged category is still fully accounted for in the
  report, and a newly discovered P0/P1 in that same staged delta (found
  while verifying) is still reported. It only avoids repeating settled
  reasoning over content that provably has not changed, under a review
  standard that has also provably not changed.
- **Differ** — the staged delta changed and must be reviewed as new
  delta, same as any other newly detected content.
- **Precondition not established** (the applicable review standard
  changed, or the caller cannot confirm it did not) — treat this
  exactly as a fingerprint **Differ**: review the staged category as new
  content under the current standard, regardless of what the content
  fingerprint itself reports.

This comparison is scoped to the staged category only. Unstaged and
untracked state carry no fingerprint and must be independently
(re-)detected via their own commands (step 3) on every invocation,
regardless of whether the staged fingerprint matched — an unchanged
staged fingerprint must never be read as "nothing changed" when unstaged
or untracked content differs.
