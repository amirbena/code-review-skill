# Runbook — Active PR Review

Reviews an existing GitHub Pull Request and publishes findings and a final
decision. The numbered Steps below are the only authoritative execution sequence. The policy load set — what is unconditional, and which files open only when their predicate fires, fail-closed — is owned by [`../SKILL.md`](../SKILL.md) section 2; each step cites the canonical policy that owns its rules and restates none of them.

## Steps

**Mandatory-loading checkpoint (runs before step 1).** Confirm every unconditional file `SKILL.md` section 2 lists is open; a member introduced there by a context phrase counts only when that context holds. Load any that is not, and record an unloadable one as an incomplete trigger naming it, per [`review-stopping-criteria.md`](../../../shared/policies/review-stopping-criteria.md), "Mandatory-loading checkpoint and pre-verdict recheck". Conditional files stay fail-closed and are opened when their predicate fires; an unfired one is never required. Skipping a file, or reading only an excerpt of it (`head`, `sed -n`, a limited read), is not "unloadable": load it in full.

1. **Before any other step** (after the checkpoint above), resolve the repository and PR, then resolve
   the authenticated GitHub identity, the PR author, and whether the two
   share a controlling authority, per
   [`../policies/review-authority.md`](../policies/review-authority.md),
   "Self-review capability" and "Authority separation, not just identity
   separation." If the reviewer **is** the PR author, or is a reviewer
   under the same controlling authority (an alternate account / token /
   bot / service account / GitHub App identity / nested agent / spawned
   process), this invocation is a **self-review**: set
   `formal_review_mutation_allowed = false` and **continue** — the full
   review still runs (same evidence and process as an external review),
   but the review-action authorization gate (step 14) permits no `APPROVE`
   and no formal `REQUEST_CHANGES` on the reviewer's own work, and step 16
   submits none. There is no `REVIEW SKIPPED`; analysis is not skipped. If identity or controlling authority cannot be resolved with
   confidence, treat the invocation as a self-review for the mutation
   boundary (fail closed). This resolution precedes and is independent of
   the ownership check in step 2.
2. Check for an existing Code Review Agent owner of this scope per
   [`../../../shared/policies/review-ownership.md`](../../../shared/policies/review-ownership.md).
   If owned elsewhere, return `REVIEW ALREADY OWNED` and stop.
3. **Verify repository/review access** for the authenticated identity
   against the target repository/PR (see
   [`../policies/review-authority.md`](../policies/review-authority.md),
   "Review/repository access prerequisite"). Successful authentication
   alone is not sufficient.
   - If access cannot be confirmed: do not fake publication, do not claim
     Approve/Request Changes was submitted; fall back to
     [`passive-pr-review.md`](passive-pr-review.md) and clearly state
     that GitHub publication was unavailable.
3a. **If this invocation asks to publish/post a review already produced
   passively earlier in this same interaction** and does not itself resolve
   a presentation (per
   [`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md)),
   ask the user once, before step 4, which presentation to publish, per
   [`../policies/review-output.md`](../policies/review-output.md),
   "Publishing a previously produced passive review" — which owns the
   recommend-but-never-apply rule, the unresolved-answer withhold
   (`Mutation: WITHHELD (publication format unresolved)`), and every case
   that skips this step. Skip it for an ordinary fresh active review.
4. **Resolve review mode** per
   [`../policies/reviewer-delta-review.md`](../policies/reviewer-delta-review.md).
   Retrieve the immediately preceding completed review of this PR, if any,
   and its reviewer identity and reviewed SHA. If the current authenticated
   reviewer is the same identity as that reviewer, and the previously
   reviewed SHA can be established reliably, this invocation is a **delta
   re-review** bounded by that SHA and the current PR HEAD; otherwise (no
   previous completed review, a different reviewer, or any ambiguity in
   reviewer identity or the reviewed SHA) it is a **normal review**. If the
   previously reviewed SHA already equals the current PR HEAD, stop here
   with the `NO NEW DELTA` reasoning result — do not manufacture a new
   review.

   **If the caller supplied review context** (requirements, explicit user
   instructions, pasted Jira/ticket text, a pasted or referenced GitHub
   Issue, an HLD/ADR, an implementation plan) — or to use the PR description
   as a statement of intent — resolve and normalize it now per
   [`../policies/review-context.md`](../policies/review-context.md) and the
   shared [`review-context.md`](../../../shared/policies/review-context.md),
   "Input form."
   - **Resolve reference-based context first.** If the caller supplied a
     **Jira reference** (key or URL), execute the shared
     [`review-context.md`](../../../shared/policies/review-context.md), "Jira
     context resolution" → **"Resolution procedure"**, and this Skill's
     [`../policies/review-context.md`](../policies/review-context.md), "Jira
     context resolution (PR application)": identify an available Jira MCP /
     connector / runtime-exposed Jira read tool; invoke it **read-only** to
     fetch the referenced issue's contents (not the
     key/URL/branch/PR-title/commit/copied metadata); fetch relevant issue
     comments and linked requirement context when the integration supports
     them; normalize into Review Context (classify comments per "Jira
     comments" — do not promote every comment to an acceptance criterion);
     continue only after successful resolution. Any failure along that
     procedure — no integration, authentication failure, authorization
     failure, issue not found, malformed reference, or connector/MCP error or
     timeout — stops the Jira-scoped path with the `JIRA CONTEXT UNRESOLVED`
     reasoning result per
     [`../policies/review-output.md`](../policies/review-output.md), "Final
     decision": name the reference and integration(s) attempted, do **not**
     infer the ticket from its key/branch/PR title/commit/surrounding
     text/copied metadata, retrieve no PR scope for grading, and submit no
     formal review. A GitHub Issue **reference** is resolved through the same
     read-only GitHub access used for PR state, or supplied as pasted text.
     No automatic PR↔Issue discovery. Pasted/free-form context needs no
     resolution.

   This context step is optional; absence changes nothing. It never changes
   the review mode resolved above, never widens the PR delta, and never adds
   a review target.
5. Resolve and record the authoritative PR HEAD SHA. **Before computing
   any delta, resolve stack topology** per
   [`../policies/stacked-pr-review.md`](../policies/stacked-pr-review.md):
   resolve the PR's declared base ref/SHA, and determine whether it *is*
   the repository's default/target branch (the ordinary case — stop here;
   nothing below changes) or corresponds to another **open** PR (a stack
   layer). For a stack layer, walk the chain to the root, or fail safe to
   a wider scope per that policy's §4 when the chain or merge-base cannot
   be resolved cleanly — never silently narrow scope. The **effective
   review base** this resolves (the root, or the immediate parent's
   current head SHA) is what every step below uses as "the base" —
   never the repository's default/target branch when they differ.

   For a normal
   review, retrieve the complete paginated changed-file set and complete
   diff per [`../policies/pr-scope.md`](../policies/pr-scope.md), "Complete
   PR scope and pagination," computed against the effective review base.
   For a delta re-review, retrieve the bounded delta between the previously
   reviewed SHA and the current PR HEAD, plus
   enough surrounding context to confirm the requested fix, absence of
   regression, and continued validity of the previous review's assumptions
   — full-PR retrieval is not required unless the delta later escalates to
   a normal review (see
   [`../policies/reviewer-delta-review.md`](../policies/reviewer-delta-review.md),
   "Escalating from delta to full review"). Reconcile the retrieved count
   with PR metadata where available for a normal review. If any material
   scope remains missing or truncated, return `REVIEW INCOMPLETE`, report
   the missing scope, and do not submit a formal decision.

   Resolve the requested repository-access mode. For optional or required
   repository-backed inspection, prepare the checkout per
   [`../policies/repository-checkout.md`](../policies/repository-checkout.md)
   — its lifecycle, safety flags, failure classification, and read-only
   guarantee apply exactly as specified there; this runbook only sequences
   it and carries the outcome forward. Resolve the `NormalizedPrSource`
   from the PR metadata already retrieved; for a stack layer its base
   ref/SHA are the **effective review base** resolved above, not the
   repository's default/target branch. The PR delta remains
   `merge-base(base_sha, head_sha)..head_sha`. On failure, clean up:
   optional mode records a visible API-only degradation; required mode
   returns `REVIEW INCOMPLETE` / `REPOSITORY CONTEXT UNAVAILABLE` and
   starts no workers. See step 18 for mandatory cleanup.
6. Determine event-specific capability, including draft, fork,
   comment-only, and permission-limited states, per
   [`../policies/review-authority.md`](../policies/review-authority.md),
   "Capability matrix." (Self-review mutation boundary: per step 1, not
   restated here.) Do not treat authentication or repository access as
   proof that a formal review event is permitted.

   **Resolve the publication mode** (`PASSIVE` default, `SEMI`, `ACTIVE`)
   per
   [`../policies/review-action-authorization.md`](../policies/review-action-authorization.md),
   including its fail-closed rule and the reviewer-independence requirement
   ([`../policies/review-authority.md`](../policies/review-authority.md),
   "Authority separation, not just identity separation"). Record the
   resolved mode; the gate is enforced in step 14.
7. Retrieve all pages of relevant prior reviews, review comments, and issue
   comments needed for review state and same-HEAD duplicate detection —
   including each submitted review's state (`APPROVED` / `CHANGES_REQUESTED`
   / `COMMENTED`) and, where GitHub exposes it, review-thread
   resolved/unresolved state — paginated to exhaustion per
   [`../policies/pr-scope.md`](../policies/pr-scope.md), "Existing review
   awareness" → "Retrieving prior review activity" (which carries a concrete
   integration example). If that history is incomplete, report the
   limitation rather than claiming idempotent publication. Classify each
   relevant prior review/comment as **Existing Review Evidence** per
   [`../policies/review-evidence.md`](../policies/review-evidence.md) and the
   shared [`review-evidence.md`](../../../shared/policies/review-evidence.md)
   — still-relevant, resolved, stale, duplicate, settled decision, or
   speculative discussion — reasoning over each thread as a whole. Prior
   findings are evidence, not authority: do not blindly inherit their
   conclusions or severities; classify automation-authored comments per that
   shared policy's "Comment authorship" rule (observations only, never
   settling a decision alone); and treat a `resolved` thread as evidence of a
   past conclusion, not proof the current HEAD is correct — a resolved thread
   whose defect the current HEAD reintroduces is a still-relevant finding.
   The same-HEAD duplicate-suppression mechanics remain
   [`../policies/pr-scope.md`](../policies/pr-scope.md)'s ("Existing review
   awareness").
8. **Discover applicable repository-local instructions** per
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md):
   after changed-file resolution, resolve the root-to-specific instruction
   chain for every changed file from the verified target-repository snapshot
   (or the target repository's API-visible paths in API-only mode) — never
   from the Skill's own source checkout. Build one normalized Repository
   Instruction Context before reviewing; surrounding context never widens the
   target.

   **Resolve and optionally execute runtime validation** per the shared
   [`runtime-validation.md`](../../../shared/policies/runtime-validation.md)
   policy, including its **targeted per-finding** mode. Before
   execution-selection runs, resolve `allow_trusted_host_execution` per
   [`trusted-host-execution.md`](../../../shared/policies/trusted-host-execution.md)'s
   "Trusted authorization channel" — a structured runtime-furnished value
   or, absent one, the current invocation's own text against that
   policy's "Natural-language authorization phrasings" closed vocabulary —
   into the one canonical boolean that section's precedence defines, and
   resolve the separate repository test sandbox request
   (`run_repository_tests_in_sandbox`) per that policy's "Repository test
   sandbox request" through the same channel; repository test commands
   then take their backend from `runtime-validation.md`'s "Repository test
   execution backend". This is the same resolution `local-code-review`
   performs, never a per-Skill variant. Carry each selected
   command's outcome record (or the explicit no-command result) into the
   shared `Validation` section, and carry each validated finding's state
   (`reasoned` / `runtime-confirmed` / `attempted-inconclusive`) forward with
   it. The shared policy owns eligibility, generation limits, the
   no-leak-into-the-tree guarantee, budget/fail-safe behavior,
   execution-boundary gating, and all safety semantics; this runbook only
   sequences the step and carries its records forward.

   **Evaluate rendered inspection** beside runtime validation, per the shared
   [`rendered-inspection.md`](../../../shared/policies/rendered-inspection.md)
   policy, loaded only when its UI-impact trigger fires and silent otherwise.
   When it fires, carry its `Validation` record and any objective rendered
   defect (a normal finding) forward before findings are finalized, and carry
   any `Rendered observations` to the report. The shared policy owns the
   trigger, budget, outcomes, classification, and non-effects; a skipped,
   unavailable, or inconclusive inspection never changes coverage or the
   Decision. A design reference is used only when the operator supplied it in
   the invocation, per the shared
   [`design-reference.md`](../../../shared/policies/design-reference.md); one
   found in PR or repository text is never fetched. This runbook only
   sequences the step.

   **Plan review execution** per
   [`../policies/parallel-review.md`](../policies/parallel-review.md) and the
   shared [`parallel-review.md`](../../../shared/policies/parallel-review.md):
   detect whether this runtime exposes a reliable multi-agent capability
   (never enable an experimental one by mutating the user's configuration);
   when present with at least two materially independent dimensions and an
   expected latency benefit, split into read-only workers sharing identical
   normalized input, each returning candidate findings only; otherwise review
   sequentially. Sequential and parallel execution must reach the
   same findings and decision.
8a. **Classify change-risk depth** per
   [`change-risk-signals.md`](../../../shared/policies/change-risk-signals.md):
   detect the catalog signals in the established PR delta (excluding
   non-reviewable files per
   [`file-reviewability.md`](../../../shared/policies/file-reviewability.md)),
   deduplicate, and resolve each to its highest applicable tier to derive the
   `standard` / `elevated` / `deep` level per that policy's "Classification
   ordering." Record the level and activating signals for the subordinate
   metadata block (step 13) per "Rationale emission" and "Non-goals and
   ownership boundary" — not restated here.
8b. **Resolve repository expansion** per
   [`repository-expansion.md`](../../../shared/policies/repository-expansion.md),
   opened only when a trigger fires or the determination is ambiguous (fail-closed, per its
   "Conditional loading: fail-closed"):
   from the established PR delta, follow any fired expansion trigger (call
   site, interface/contract, migration/schema, config consumer) through the
   bounded, ring-based procedure whose ceiling is scaled by the change-risk
   depth from step 8a. Record every fired trigger with the ring reached and
   the locations inspected — or "none" when nothing fired, recorded without opening the policy — for the
   subordinate metadata block (step 13), per "Expansion decisions are
   reported" and "Non-goals and ownership boundary" — not restated here.
8c. **Partition large changes** per
   [`large-pr-partitioning.md`](../../../shared/policies/large-pr-partitioning.md),
   opened only when the diff-size count from `change-risk-signals.md` reaches its threshold or is
   ambiguous (fail-closed, per its "Conditional loading: fail-closed"):
   when the scope this invocation reviews — the full PR change, or in
   delta re-review only the bounded delta, per that policy's "Activation"
   (same exclusion of non-reviewable files as step 8a) — reaches that
   policy's partitioning threshold, build coherent review units by its
   deterministic directory-seed / coherence-merge / size-cap procedure
   (over the delta's files only, in delta mode); otherwise review that
   scope as a single unit as before. Size never selects delta mode or
   escalates a delta to a full review
   ([`reviewer-delta-review.md`](../policies/reviewer-delta-review.md),
   "Oversized delta"). When partitioned, apply step 9
   separately to each unit, then fold every unit's findings into step 10's
   aggregation — extended here to also reconcile and de-duplicate **across
   partitions** (including cross-partition consolidation per
   [`root-cause-consolidation.md`](../../../shared/policies/root-cause-consolidation.md))
   into **one** finding set before step 11 onward, which run exactly once,
   never per partition. Record whether partitioning activated and, if so,
   the partitions built for the subordinate metadata block (step 13); an
   unpartitioned review records nothing for this field, per "Reporting" and
   "Non-goals and ownership boundary" — not restated here.
8d. **Check review-base policy compliance** per
   [`review-base-policy.md`](../../../shared/policies/review-base-policy.md),
   using the stack topology resolved in step 5 and the repository
   instructions already discovered in step 8 (the source for that
   policy's explicit-statement resolution signal — this step performs no
   second discovery pass). This check applies to the resolved **root**
   (the repository's default/target branch the stack chain terminates at,
   or the PR's own declared base for a non-stacked PR) — never to an
   intermediate layer's parent-PR base, which
   [`stacked-pr-review.md`](../policies/stacked-pr-review.md) already
   treats as legitimate. Resolve the repository-resolved review base from
   that policy's ranked signals and, when both it and the resolved root
   are reliably known and they differ, record the single blocking P0
   finding that policy defines now, so it is already part of the finding
   set before step 9's implementation-focused review begins. When the
   repository-resolved review base cannot be established reliably, or
   step 5's topology resolution itself fell back to a Tier 1/Tier 2 safe
   failure, this step records nothing, per that policy's "Fail-closed on
   an unresolved base" — an unresolved stack is not, by itself, evidence
   of a policy violation.
9. Review per
   [`review-scope.md`](../../../shared/policies/review-scope.md) and the
   file-treatment rules in
   [`file-reviewability.md`](../../../shared/policies/file-reviewability.md),
   applying the instructions discovered in step 8. First apply
   [`../policies/review-reasoning.md`](../policies/review-reasoning.md),
   "Semantic Implication Review," to detect and reason about the
   system-level dimensions this invocation's scope materially implicates,
   then the same file's "Domain-Specific Deepening Review" (canonical
   home:
   [`specialist-depth.md`](../../../shared/policies/specialist-depth.md))
   to decide, per implicated dimension, whether deeper domain-specific
   reasoning is warranted, and the same file's "Null-Like Absence-Risk Review" for any changed
   data-flow or control-flow the reviewed language's nullability model
   makes credibly absence-prone. When this invocation's
   scope contains multiple related changes, reason about them per the same
   file's
   "Logical Cohort Review," and inspect the relevant dependency surface
   per "Code Impact / Dependency Analysis" in the same file. When the
   invocation changes observable behavior, also trace it into the existing
   tests that depend on it per "Affected-Test Impact Review" in the same
   file. When the invocation changes a repository contract another
   component consumes, also apply "API / Contract Compatibility Review" in
   the same file. When the invocation changes a dependency manifest,
   lockfile, container base-image reference, or CI/automation action
   reference, also apply "Dependency / Supply-Chain Deepening Review" in
   the same file. When the invocation adds an issue-tracker reference in a
   comment or introduces a possibly unclear variable name, also apply "Code
   Hygiene Review" in the same file. When the invocation introduces or
   reimplements validation, business-rule, or other shared-semantics logic,
   also apply
   [`review-scope.md`](../../../shared/policies/review-scope.md),
   "Existing behavior ownership." Those
   instructions refine evaluation but never override this Skill's own
   safety boundaries (see
   [`repository-instructions.md`](../../../shared/policies/repository-instructions.md),
   "Instruction precedence"); classify findings per
   [`severity.md`](../../../shared/policies/severity.md) with evidence per
   [`evidence.md`](../../../shared/policies/evidence.md), then apply
   [`../policies/review-reasoning.md`](../policies/review-reasoning.md),
   "Remediation-Scope Boundary Review" (canonical home:
   [`remediation-scope-boundary.md`](../../../shared/policies/remediation-scope-boundary.md)),
   to each material finding before finalizing. When review context
   is available, also apply the shared
   [`review-context.md`](../../../shared/policies/review-context.md),
   "Scope-boundary reasoning," to the PR: detect required behavior missing
   from the PR, the PR contradicting acceptance criteria, unrelated scope
   expansion, a valid-but-out-of-scope finding, and repository-policy
   violations that hold regardless of the ticket's stated scope — using that
   policy's precedence notes (repository policy/invariants can constrain the
   PR even when a ticket says otherwise; an accepted ADR/HLD generally
   outweighs speculative ticket discussion; newer explicit maintainer
   clarification supersedes stale discussion), not a rigid priority order;
   report an unresolved material conflict as an ambiguity. Use the prior
   Existing Review Evidence classified in step 7 to avoid repeating a
   settled finding, contradicting a settled decision without concrete new
   evidence, or missing an unresolved previously identified issue that still
   holds against the current HEAD. For a delta
   re-review, if what is found here meets any "Escalating from delta to
   full review" condition in
   [`../policies/reviewer-delta-review.md`](../policies/reviewer-delta-review.md),
   switch this invocation to a normal review, retrieve the remaining full
   scope per [`../policies/pr-scope.md`](../policies/pr-scope.md),
   "Complete PR scope and pagination," and continue reviewing from there
   rather than completing the review as delta-only.
10. **If parallel workers were used, or the change was partitioned per `large-pr-partitioning.md`, aggregate first** per the shared
    [`parallel-review.md`](../../../shared/policies/parallel-review.md),
    "Centralized aggregation": normalize → deduplicate (same location + same
    normalized claim; carry the higher candidate severity, report once) →
    reconcile overlapping/conflicting findings into the single reviewer's
    candidate set. Worker completion order must not affect the result, and
    workers derive nothing final. If a **required** dimension could not be
    produced by a worker or recovered by the parent reviewer, stop with the
    `REVIEW INCOMPLETE` reasoning result — never `REVIEW CLEAN` / `Approve`.
    An **optional** dimension the parent redoes itself does not degrade the
    result. Then continue with the finding-identity step below.
    Compute the stable internal identity defined by
    [`../policies/pr-scope.md`](../policies/pr-scope.md), "Existing review
    awareness" for every finding. Keep `F1`, `F2`, ... as display IDs. Mark
    a finding as suppressed (not for publication, though it may still
    appear in returned reasoning) only when the same authenticated
    reviewer/workflow already published the same finding identity for this
    same PR HEAD.
11. **Finalize findings** — this is the boundary between analysis and
    publication (see
    [`../policies/review-output.md`](../policies/review-output.md),
    "Analysis phase vs. publication phase"): the finding set is now fixed.
    For each non-suppressed finding, resolve inline eligibility per
    [`../policies/finding-placement.md`](../policies/finding-placement.md),
    "Inline comment eligibility" — inline-eligible findings render with
    [`../templates/inline-finding.md`](../templates/inline-finding.md);
    the rest render in full within the review body. Anchor each
    inline-eligible finding at its canonical fix/action location per that
    policy's "Anchor at the fix/action location" — semantic candidate
    resolution before GitHub commentability, never a line chosen because
    GitHub allows a comment there. A fix/action location that is
    unresolved or not inline-commentable moves the finding to the body
    with its explicit path/location (or unresolved marker); the finding's
    canonical location and identity are not altered. No publication has
    occurred yet.
11a. When resolved review context contains authoritative requirements or
    acceptance criteria, load and apply
    [`requirement-coverage.md`](../../../shared/policies/requirement-coverage.md)
    to the inspected PR and carry its separate task-relative completeness
    signal into the review body. With no activating contract, emit nothing
    for it.
11b. **Evaluate review coverage** per
    [`review-stopping-criteria.md`](../../../shared/policies/review-stopping-criteria.md),
    using the change-risk depth from step 8a and, when it activated, the
    partitions from step 8c: confirm every pass that depth (and partitioning)
    requires — including step 10's required-dimension check and every
    partition's aggregation — actually reached its own stop condition.
    Record `coverage: complete` or `incomplete` with its reason(s) for the
    subordinate metadata, per "Labeling — incomplete must never present as
    clean" and "Non-goals and ownership boundary" — not restated here. Required
    material from `SKILL.md` section 2 that was not loaded before the decision it governs is an
    incomplete trigger too, per that policy's "Incomplete triggers" — never
    `complete`. This step runs after every review pass, so it is also the pre-verdict recheck per [`review-stopping-criteria.md`](../../../shared/policies/review-stopping-criteria.md), "Mandatory-loading checkpoint and pre-verdict recheck": recompute coverage over the final state, including every conditional file whose predicate fired during the review, and carry no earlier value forward. Set the Coverage field (the metadata block's `coverage` field) from the files actually opened, never from memory, and apply the coverage invariant ([`review-stopping-criteria.md`](../../../shared/policies/review-stopping-criteria.md), "Labeling") to the rendered report. When `incomplete`, the reasoning result for step 13 onward is
    `REVIEW INCOMPLETE` per
    [`../policies/review-output.md`](../policies/review-output.md), "Final
    decision."
12. Re-check the current PR HEAD against the recorded HEAD (see
    [`../policies/review-output.md`](../policies/review-output.md), "HEAD
    revalidation"), immediately before constructing the review. If it
    changed, do not construct or submit a review for the stale SHA —
    review the new delta first (re-evaluating escalation per step 9 if
    this was a delta re-review) and re-finalize findings against it,
    then re-run step 11b over the new state: a coverage value from before
    the HEAD change, the new delta, or the re-finalization is never reused.
12a. **Derive the decision.** Step 11b's coverage must be the one just
    recomputed, with no review, delta change, or re-finalization after it.
    When that coverage is `incomplete`, the decision is the
    incomplete/ungraded outcome already set at that step, per
    [`review-stopping-criteria.md`](../../../shared/policies/review-stopping-criteria.md),
    "Labeling" — never `Approve`, regardless of what the finding set
    alone would otherwise produce. Otherwise, derive the decision
    mechanically per
    [`../../../shared/policies/severity.md`](../../../shared/policies/severity.md),
    "Decision derivation (mechanical)," from the finalized findings
    re-confirmed against the current HEAD in step 12 — stating the
    explicit P0/P1 tally that section requires as the basis for the
    decision, not an impression of the finding set. This is the only
    path to the decision;
    [`../policies/review-output.md`](../policies/review-output.md),
    "Final decision," names the resulting `Approve` / `Request Changes`
    wording but does not re-derive it.
12b. **Check verdict consistency** per
    [`../../../shared/policies/verdict-consistency.md`](../../../shared/policies/verdict-consistency.md),
    identical placement and check to
    [`passive-pr-review.md`](passive-pr-review.md)'s pre-render check:
    confirm the decision derived in step 12a agrees with the
    `Approve` / `Request Changes` / `REVIEW INCOMPLETE` signal about to
    be rendered into the review constructed next — including a `SEMI`
    `WOULD PUBLISH (<event>)` line. On a detected mismatch, do not
    construct the review — report an internal-consistency failure
    instead, per that policy's "On a detected mismatch:
    withhold-and-report," and stop here.
13. Construct **one** review from the finalized findings: the body using
    [`../templates/external-review-summary.md`](../templates/external-review-summary.md)
    (full findings for non-inline ones, summary-pointers for inline ones —
    never both, per
    [`../policies/finding-placement.md`](../policies/finding-placement.md), "No
    duplicate findings") plus the array of inline comments for
    inline-eligible findings. State the review mode used (full review or
    delta re-review, with the previously reviewed SHA and current HEAD
    when delta) per
    [`../policies/reviewer-delta-review.md`](../policies/reviewer-delta-review.md),
    "Reporting the mode." State the stacked-PR context resolved in step 5
    — the detected stack and active layer, or "no stack detected" — per
    [`../policies/stacked-pr-review.md`](../policies/stacked-pr-review.md),
    §7, and
    [`../policies/review-output.md`](../policies/review-output.md),
    "Stacked-PR context". **If the current invocation normalized
    `human_review_output`** (the presentation-option normalization at the
    top of this flow, per
    [`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md)),
    render the body in the concise senior-engineer voice per
    [`../templates/external-review-summary.md`](../templates/external-review-summary.md),
    "Concise human-style body (opt-in)" — same finalized findings,
    severities, inline comments, and decision; only the body wording
    differs. This includes any finding with no valid inline anchor: it
    still renders in full in the body (per
    [`../policies/finding-placement.md`](../policies/finding-placement.md)),
    but as the human full rendering per
    [`../../../shared/templates/finding-rendering-human.md`](../../../shared/templates/finding-rendering-human.md),
    "Canonical human full rendering," not the structured block — the same
    finding, identity, severity, and location, only its wording changes.
    **If the invocation also normalized `human_inline_findings`**
    (its default follows `human_review_output` per
    [`../../../shared/policies/invocation-options.md`](../../../shared/policies/invocation-options.md),
    "`human_inline_findings` derived default and phrasings"), render each
    inline comment in the same concise senior-engineer voice per
    [`../templates/inline-finding.md`](../templates/inline-finding.md),
    "Human-rendered inline finding (opt-in)" — same findings, severities,
    canonical fix/action anchors, `#164` / `#165` inline→body fallback,
    and decision; only the inline wording differs. An explicit
    `human_inline_findings=false` keeps the structured
    `[<severity>] / Evidence / Impact / Fix` inline block. **Evaluate the
    shared
    [`reasoning-checkpoint.md`](../../../shared/policies/reasoning-checkpoint.md)
    activation once, after findings and the decision are final;** when it
    activates, the body carries its `Reasoning check` section after
    `Decision` per
    [`../templates/external-review-summary.md`](../templates/external-review-summary.md),
    "Reasoning check (conditional)" — body only, never an inline comment,
    no effect on the decision or review event. Do not submit
    anything yet.
13a. **Compose the private Reviewer Brief** per
    [`../policies/reviewer-brief.md`](../policies/reviewer-brief.md), from
    the same finalized findings, severity, coverage, and verdict step 13
    just rendered. This is **not** part of the review constructed in step
    13: the brief is composed separately, using
    [`../templates/reviewer-brief.md`](../templates/reviewer-brief.md),
    and appended to the caller-facing **returned result** only — it is
    never added to the review body, never added to the inline-comments
    array, and never passed into steps 15-16 (status publication and
    submission), which construct and publish only what step 13 built.
    `human_review_output` (and its companion `human_inline_findings`) may
    adjust the brief's wording/compactness exactly as it does the review
    body, per
    [`../policies/reviewer-brief.md`](../policies/reviewer-brief.md),
    "Composition with invocation modes" — never its fields or boundaries.
    **When the caller explicitly requested a machine-readable result**,
    compose it here too, from the same finalized result, per
    [`../policies/structured-output.md`](../policies/structured-output.md);
    like the brief it joins the returned result only and is never passed
    into steps 15-16.
14. **Apply the review-action authorization gate** per
    [`../policies/review-action-authorization.md`](../policies/review-action-authorization.md)
    and [`../policies/review-output.md`](../policies/review-output.md),
    "Review-action authorization gate," using the mode resolved in step 6
    and the HEAD confirmed in step 12, to determine the permitted outcome;
    the outcome is executed by the single batched submission in step 16,
    not here. **If step 1 resolved this as a self-review**: the mutation
    boundary set there stands — publish the finalized review body as an
    informational `COMMENT` (verdict, reviewed HEAD, findings, and a note
    that the formal decision was withheld by policy) as the run's final
    publication in step 16 (in `ACTIVE` mode only — `PASSIVE`/`SEMI`
    publish nothing regardless of authorship), and report
    `Comments: COMMENTS PUBLISHED` /
    `Mutation: WITHHELD (self-review: reviewer is the PR author)`.
    Otherwise (external review): in **`PASSIVE`** mode the permitted
    outcome is no GitHub mutation (`Mutation: WITHHELD (publication mode
    is PASSIVE)`); in **`SEMI`** mode, compute the identical event `ACTIVE`
    would submit and report it as `Mutation: WOULD PUBLISH (<event>)`
    without submitting anything; in **`ACTIVE`** mode — an explicit
    request is its own authorization, so the permitted **Approve** or
    **Request Changes** event is submitted whenever established reviewer
    independence and event permission for the desired action both hold at
    the HEAD confirmed in step 12, with no further activation signal
    required.
15. **Publish any optional machine-readable status** for the reviewed SHA
    per
    [`../policies/review-status-enforcement.md`](../policies/review-status-enforcement.md),
    **before** the final summary comment. First re-confirm the live PR HEAD
    still equals the reviewed SHA, per
    [`../policies/review-output.md`](../policies/review-output.md),
    "Submission ordering": if HEAD has advanced, withhold the status
    (`STATUS WITHHELD (HEAD advanced)`) AND do not submit the review in
    step 16 — review the new delta, re-finalize findings against the
    current HEAD (re-evaluating escalation per step 9 if this was a delta
    re-review), and only then re-run steps 13–16. Otherwise map the
    verdict to a status state and publish it only as that status policy's
    "Authorization: blocking authority vs. positive authority" permits. Only the
    authoritative aggregator publishes it; parallel workers never do.
    Never merge.
15a. **Re-check verdict consistency against the literal event about to be
    submitted**, per
    [`../../../shared/policies/verdict-consistency.md`](../../../shared/policies/verdict-consistency.md) —
    the pre-publish reconciliation point, re-checking the same
    mechanically-derived decision checked at step 12b against step 14's
    resolved `APPROVE` / `REQUEST_CHANGES` event object (an informational
    self-review `COMMENT` carries no decision claim and is never checked
    here). This catches a second, silent rendering introduced between
    step 12b and this submission. On a detected mismatch, withhold the
    formal event and do not proceed to step 16 — report why no final
    formal review was submitted, per that policy's "On a detected
    mismatch: withhold-and-report," reusing step 16's own "GitHub
    otherwise disallows the formal event" reporting path.
16. **Submit the one review** — only when step 15's HEAD re-confirmation
    and step 15a's verdict-consistency check still hold (either aborts
    this step and sends the flow back through re-review, or withholds
    the formal event and reports why, respectively). Submit the body
    (concise per step 13
    when `human_review_output` is on), the inline comments (senior-voiced
    per step 13 when `human_inline_findings` is on), and the permitted
    event from step 14 — as a single batched submission per
    [`../policies/review-output.md`](../policies/review-output.md),
    "Batched review construction and submission." For a self-review, this
    is step 14's informational `COMMENT`, carrying the same body plus the
    closing disclosure line, with the same reported statuses. If GitHub
    rejects a specific resolved inline location, apply the
    [`../policies/finding-placement.md`](../policies/finding-placement.md)
    "Rejected inline location fallback" and complete the submission. If
    GitHub otherwise disallows the formal event, preserve the clean/blocking
    reasoning result and report why no final formal review was submitted.
    Never claim a GitHub mutation that did not succeed, and never submit
    more than one review for this finalized finding set. **This one review
    submission carries the final human-facing summary and is the last
    review-owned publication of the run** (`final review comment == last
    publication event`): after it, publish nothing further and edit nothing
    already published — no comment, no inline comment, no status, no check.
17. Return separate reasoning, publication-mode, comments-publication, and
    decision-publication statuses per
    [`../policies/review-output.md`](../policies/review-output.md),
    "Final decision" and "Review-action authorization gate," whether or
    not GitHub mutation succeeded. A withheld mutation is reported
    explicitly with its reason; a clean reasoning result with a withheld
    approval is never reported as "approved."
18. **Guaranteed cleanup.** If a repository-backed checkout was prepared in
    step 5, remove it now — and on **every** other exit path: a
    `NO NEW DELTA` / `REVIEW INCOMPLETE` return, a self-review that
    withholds its formal event, any context-resolution failure after the
    checkout was allocated, any review or worker failure, any publication
    failure, or an interruption the runtime surfaces. This runs in a `finally` (or the runtime's
    equivalent). Before deleting, verify the target resolves inside the
    scratch parent, is not the scratch parent itself, and carries this
    Skill's ownership marker — never an unconstrained recursive delete. Then
    stop. Never merge, never delete branches in the target repository, never
    modify implementation code, never take ownership of repository lifecycle
    cleanup, and never run target-repository commands outside the shared
    runtime-validation policy.
