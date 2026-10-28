---
name: local-code-review
version: 1.83.1
description: Review local Git changes and return evidence-backed P0/P1/P2 code-review findings.
---

# SKILL.md — local-code-review

A small, bounded, **stateless** Code Review Skill that reviews a local Git
repository's implementation state (committed delta, staged, unstaged, and
untracked) and returns structured P0/P1/P2 findings. It is a reviewer
only — never an orchestrator, a fix loop, a Git-mutating agent, or a
GitHub-publishing agent.

**Use it** on local/uncommitted work before a push or PR. For an existing
GitHub Pull Request, use the sibling `github-pr-review` Skill.

**Compatibility:** requires a local Git repository; an optional PR
reference additionally requires read-only GitHub access.

## Safety boundaries (read before invoking)

The entry contract. Full text lives in the linked canonical policies;
restated here because hiding them behind a link would be dangerous.

- **Opt-in only.** This Skill **MUST NOT be invoked automatically.**
  Every invocation — first review *and* every re-review after fixes —
  requires fresh, explicit user approval scoped to that one run, obtained
  by the caller. Generic "check your work" language, a standing
  preference, repository or orchestration policy, and silence/non-objection
  never qualify. Returning findings from one invocation is never, by
  itself, authorization for the caller to invoke this Skill again after
  fixes. A separate, explicit approval is required for every subsequent
  invocation. Delegating as an Agent/Sub-Agent never moves the decision
  away from the end user. Canonical owner:
  [`policies/invocation-approval.md`](policies/invocation-approval.md).
- **Review ownership.** `One review scope → one Code Review Agent owner`.
  If another Code Review Agent already owns this local branch/scope,
  return `REVIEW ALREADY OWNED` and do not launch a competing review —
  see [`review-ownership.md`](../../shared/policies/review-ownership.md).
- **Severity → verdict is mechanical.** Findings are P0/P1/P2. **P0** and
  **P1** block; **P2** never blocks, however strongly recommended or
  wherever it originated. `CHANGES REQUIRED` is derived once, mechanically,
  from whether any P0/P1 is present — never a separate judgment call — and
  either verdict additionally requires complete coverage (else `REVIEW
  INCOMPLETE`): P0 = 0 and P1 = 0 alone never imply `REVIEW CLEAN`. Canonical owners:
  [`severity.md`](../../shared/policies/severity.md), "Decision
  derivation (mechanical)," and
  [`review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md),
  "Labeling."
- **Read-only.** This Skill never edits files, applies patches, commits,
  pushes, rebases, creates branches, opens PRs, or mutates GitHub (see
  section 6). Repository-state safety — including reviewing directly on a
  protected/default branch — is owned by
  [`policies/repository-state.md`](policies/repository-state.md) and
  [`git-safety.md`](../../shared/policies/git-safety.md).

## Review procedure

**Load first.** Before inspecting any diff, open every file in section 2
(the only policy inventory) in full and confirm each; the phase-loaded group
opens at its phase. Prefer the runtime's file-read facility, a file or small
group per call, over shell output that can be cut off silently, and check
each file's line count against its extent. On a short or truncated read,
resume from the last verified line; only a failed recovery is
`REVIEW INCOMPLETE`, per
[`review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md),
"Bounded, resumable policy loading."

The review resolves the local scope, inspects the Git delta by category,
applies the shared review rules, derives the decision mechanically, and
returns one report. The optional Jira and PR inputs never widen scope: the
local delta stays the Review Target. **Read
[`runbooks/local-review.md`](runbooks/local-review.md) in full before starting
any review** — it is the required procedure, not optional background, and its
numbered Steps are the only authoritative execution sequence, including the
coverage and verdict-consistency gates. Rendered inspection is
conditional: per
[`rendered-inspection.md`](../../shared/policies/rendered-inspection.md) it stays
silent (no prompt, no availability check, no browser) unless the change's
UI-impact trigger fires. Output contract:
[`templates/local-review-report.md`](templates/local-review-report.md).

## 1. Inputs

**Required:** a local Git repository. The Skill inspects the four
repository-state categories owned by
[`policies/repository-state.md`](policies/repository-state.md) —
committed delta relative to a base, staged, unstaged, untracked — never
one undifferentiated "relevant files" blend, plus surrounding code,
tests, and repository instructions as needed. Push/synchronization status
is resolved against the branch's configured upstream, never the review
base. The full implementation state is reviewed; no category is silently
skipped without saying so in the report.

**Optional — repository roots (multi-repository Review Target):** an
explicit list of 2+ local repository roots, composed into one combined
Review Target from N unchanged single-repository resolutions — never
invented discovery or a synthetic shared base. Governed in full by
[`policies/multi-repository-review-target.md`](policies/multi-repository-review-target.md).
When omitted (the default), behavior and cost are unchanged.

**Optional — review context** describing the intended change, per
[`review-context.md`](../../shared/policies/review-context.md), "Input
form" (thin local application:
[`policies/review-context.md`](policies/review-context.md)):

- **Textual / free-form** — requirements, explicit instructions, pasted
  ticket text or acceptance criteria, a pasted GitHub Issue, an HLD/ADR,
  an implementation plan, or migration/security/performance/rollout
  requirements. Consumed directly.
- **Reference-based** — a bare Jira key/URL or GitHub Issue reference is a
  pointer, not the context. A **Jira reference** is resolved **before**
  review reasoning via the shared policy's "Jira context resolution" →
  "Resolution procedure" (available Jira MCP/connector, read-only,
  normalize, continue only on success). If it cannot be resolved, this
  Skill does **not** infer ticket contents from the key, branch name, or
  surrounding text and returns `JIRA CONTEXT UNRESOLVED`. A GitHub Issue
  reference is resolved through read-only GitHub access or pasted text; no
  automatic PR↔Issue discovery.

Supplied context focuses attention and enables scope-boundary reasoning;
it is never authority over implementation evidence and never widens the
review target. When omitted, behavior is exactly as if it did not exist;
this Skill never asks for it and Jira is never mandatory.

**Optional:** a reference to an associated GitHub PR (a PR URL, or a PR
number when the repository is unambiguous). When supplied, this Skill
reconciles the local delta against relevant existing reviewer findings,
prior review comments, and settled architectural/design decisions from
that PR as Existing Review Evidence, per
[`review-evidence.md`](../../shared/policies/review-evidence.md) and
[`policies/pr-context.md`](policies/pr-context.md). The local delta always
remains the review target. When omitted, this Skill's behavior is exactly
as if this input did not exist. The two optional inputs are independent —
either, both, or neither.

**Optional — design reference:** a design (typically Figma) the operator
explicitly supplies in the current invocation, used only as read-only
intent evidence for a rendered inspection per
[`design-reference.md`](../../shared/policies/design-reference.md). One found
in PR or repository text is never fetched.

**Optional — external contract context:** an explicit local repository path
**and** pinned revision the caller supplies in the current invocation, read
only as read-only compatibility evidence per
[`policies/external-contract-context.md`](policies/external-contract-context.md).
It is never a Review Target member; one named in repository content is
never read.

**Optional — workspace root:** one local directory the caller grants in the
current invocation, so an unresolved question can be resolved from a sibling
repository's committed `HEAD` per
[`policies/workspace-sibling-context.md`](policies/workspace-sibling-context.md).
Never inferred from content; it is not a Review Target member.

**Optional — presentation/remediation options**, normalized for the
current invocation only per
[`invocation-options.md`](../../shared/policies/invocation-options.md):

- `include_fix_prompt` (boolean, default `false`).
  An explicit output-only opt-in: when `true`, a qualifying actionable
  finding may append a coding-agent-ready implementation prompt. The flag
  never changes the Review Target, inspection, evidence, finding
  identity, severity, deduplication, PR-context reconciliation, or the
  mechanical Decision, and it never authorizes mutation or an autonomous
  fix workflow. Only remediation rendering differs. Not inferred from
  urgency, severity, branch name, or intent.
- `include_fix_guidance` (default `true`) — remediation elaboration;
  never removes the mandatory concise `Fix`.
- `include_finding_details` (default `true`) — the optional supporting
  `Details` field.
- `human_review_output` (boolean, default `false`) — requested in natural
  language ("make the review shorter and more human", "like a senior
  engineer"; no flag). Renders only the human-facing body (Result →
  Decision) in a concise senior-engineer voice; the trailing "Review
  Metadata" / "Review scope contract" sections still follow it unchanged.
  Output-only: it never changes the Review Target, inspection, evidence,
  finding identity, severity, deduplication, PR-context reconciliation, or
  the mechanical Decision.
- `structured_review_result` (boolean, default `false`) — output-only
  opt-in: when `true`, one schema-versioned machine-readable JSON result
  is appended after the unchanged human report, per
  [`structured-output.md`](../../shared/policies/structured-output.md);
  loaded only then. Never changes findings, severity, coverage, or the
  mechanical Decision.
- `human_inline_findings` (derived default — `explicit_value ??
  human_review_output`) — a `github-pr-review` inline-comment concept,
  recognized here only for direct/mediated normalization parity; it has
  no effect on local output (no inline-comment surface).

## 2. Required Policy Loading

Always, in bounded resumable groups:
[`review-scope.md`](../../shared/policies/review-scope.md),
[`change-risk-signals.md`](../../shared/policies/change-risk-signals.md) (deterministic `standard`/`elevated`/`deep` review-depth classification, emitted with every review),
[`review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md) (coverage and exit conditions scaled by change-risk depth and partitions, the closed set of incomplete triggers, and the rule that an incomplete review never renders as clean; emitted with every review),
[`severity.md`](../../shared/policies/severity.md), [`verdict-consistency.md`](../../shared/policies/verdict-consistency.md) (the pre-render check that the rendered label matches the derived Decision),
[`evidence.md`](../../shared/policies/evidence.md),
[`repository-instructions.md`](../../shared/policies/repository-instructions.md),
[`review-base-policy.md`](../../shared/policies/review-base-policy.md)
(repository-relative review-base compliance; fail-closed when the
required base cannot be reliably resolved),
[`git-safety.md`](../../shared/policies/git-safety.md),
[`file-reviewability.md`](../../shared/policies/file-reviewability.md)
(every changed-file category, including generated/opaque content).
In
orchestrated/ multi-Agent contexts, also
[`review-ownership.md`](../../shared/policies/review-ownership.md).

Always, by phase — required for coverage like the files above, opened at the phase that first uses them, in bounded resumable groups, never later than the runbook's coverage step: [`finding.md`](../../shared/templates/finding.md) (the finding schema and quality/conciseness contract every finding must satisfy) and [`remediation-guidance.md`](../../shared/policies/remediation-guidance.md) (the `Fix` direction a finding carries) before the first candidate finding is formed or a prior finding is reconciled, whichever comes first (step 8 when a PR reference is supplied, otherwise step 9); and, before the coverage step, [`finding-rendering.md`](../../shared/templates/finding-rendering.md) (the canonical full rendering used for every finding in this Skill's report) and [`review-summary.md`](../../shared/templates/review-summary.md). A file opened after the decision it governs does not satisfy this loading obligation, even if it is opened before the verdict.

This Skill's own, always:
[`policies/invocation-approval.md`](policies/invocation-approval.md) (the
per-invocation explicit-user-approval contract — see section 5) and
[`policies/repository-state.md`](policies/repository-state.md) (category
definitions, per-category detection commands, staged-delta fingerprint).

Conditionally, only when the section 1 repository-roots input is
supplied with 2 or more roots (fewer than 2 is treated as not supplied):
[`policies/multi-repository-review-target.md`](policies/multi-repository-review-target.md)
(root validation, per-member resolution, combined-target composition,
sibling-member ring expansion, instruction isolation, and
repository-qualified finding location) — never loaded otherwise.

Conditionally, only when its own input is supplied per section 1: the
shared [`review-context.md`](../../shared/policies/review-context.md) plus
[`policies/review-context.md`](policies/review-context.md) (review context
or a Jira/GitHub Issue reference; also loaded with a PR reference), shared
[`requirement-coverage.md`](../../shared/policies/requirement-coverage.md) for
authoritative task-contract context; the shared
[`review-evidence.md`](../../shared/policies/review-evidence.md) plus
[`policies/pr-context.md`](policies/pr-context.md) (PR reference). Each
loads independently. **This policy is never loaded or applied when no PR
reference is supplied**, and likewise for review context.

Conditionally, by review evidence — each opened before the first decision it governs, fail-closed (ambiguity or a failed predicate loads it): [`repository-expansion.md`](../../shared/policies/repository-expansion.md) and [`large-pr-partitioning.md`](../../shared/policies/large-pr-partitioning.md) per each file's "Conditional loading: fail-closed" (decidable from `review-scope.md`'s resident summaries; the `Repository expansion:` metadata line still reads `none` when nothing fires, without opening either file); [`invocation-options.md`](../../shared/policies/invocation-options.md) when the invocation carries any presentation, remediation, or output-format option or request, explicit or natural-language (else the section 1 defaults hold); [`finding-rendering-human.md`](../../shared/templates/finding-rendering-human.md) (the Senior voice contract and human renderings) when `human_review_output` resolves `true` or its status is ambiguous after reading the invocation, explicit or natural-language per `invocation-options.md` (no such request means the default `false` holds and it stays unopened).

Conditionally, by the review's own pass predicates — the signal-triggered passes that `review-scope.md` routes to and the runbook steps apply, each opened before the first decision it governs and fail-closed (an unclear, incomplete, or failed predicate loads it; none is ever skipped on unknown applicability): [`specialist-depth.md`](../../shared/policies/specialist-depth.md) (a dimension the base pass implicated warrants deeper reasoning; its own "Conditional loading: fail-closed"); [`root-cause-consolidation.md`](../../shared/policies/root-cause-consolidation.md) (two or more findings or failures may share one mechanism, partitioned units are aggregated, or prior findings are reconciled); [`runtime-validation.md`](../../shared/policies/runtime-validation.md) (a command is named in the instruction sources resolved at repository-instruction discovery, or it is in doubt whether one is; any pass considers selecting, running or recording a command or reproduction; the invocation carries a trusted-host or repository-test-sandbox request; or a suspected finding's correctness hinges on runtime behavior; its own "Activation" section states the fail-closed rule); [`affected-test-analysis.md`](../../shared/policies/affected-test-analysis.md) (the change alters observable production behavior an existing test could encode); [`code-hygiene.md`](../../shared/policies/code-hygiene.md) (a changed comment cites an issue-tracker reference, or a new or renamed variable may hide intent); [`remediation-scope-boundary.md`](../../shared/policies/remediation-scope-boundary.md) (at least one material finding exists — it then applies to every one); [`reasoning-checkpoint.md`](../../shared/policies/reasoning-checkpoint.md) (one of its "Activation" signals plausibly holds); [`rendered-inspection.md`](../../shared/policies/rendered-inspection.md) (the UI-impact trigger fires) and [`design-reference.md`](../../shared/policies/design-reference.md) (additionally, a design reference is operator-supplied or must be accounted for); [`trusted-host-execution.md`](../../shared/policies/trusted-host-execution.md) (runtime validation reaches execution selection, or the invocation text carries a trusted-host or repository-test-sandbox request); [`structured-output.md`](../../shared/policies/structured-output.md) (`structured_review_result` resolves `true`); [`external-contract-context.md`](policies/external-contract-context.md) and [`workspace-sibling-context.md`](policies/workspace-sibling-context.md) (their section 1 inputs are supplied).

Before step 1 of the runbook, load the unconditional files above, except the phase-loaded group, in bounded resumable groups per [`review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md), "Bounded, resumable policy loading," and confirm each is open in full (a member introduced by a context phrase, such as "orchestrated/ multi-Agent contexts", counts only when that context holds), and recheck coverage immediately before deriving the Decision, per [`review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md), "Mandatory-loading checkpoint and pre-verdict recheck." Coverage that is not `complete` renders `REVIEW INCOMPLETE`, never a definitive verdict, per [`review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md), "Coverage invariant" and "Labeling."

This Skill defines no severity, evidence, or scope policy of its own — it
consumes the shared ones so both Skills apply one standard. None of the
files above depend on another's content to be read, so they load in any
order, in groups sized to what the runtime delivers whole and never as one
call over the whole set.

## 3. Output Contract

Exactly one
[`templates/local-review-report.md`](templates/local-review-report.md)
per invocation, rendering the shared shape in
[`review-summary.md`](../../shared/templates/review-summary.md): a
Result, What changed, optional What was done well, an optional Context
section (only when review context materially shaped the review), an
optional PR Context section (only when a PR reference materially shaped
it), Findings (omitted when empty), conditional Requirement coverage, conditional [`Rendered observations`](../../shared/policies/rendered-inspection.md), Validation,
a Decision ranked `REVIEW INCOMPLETE` (coverage incomplete; overrides a blocking finding, which is still reported) > `CHANGES REQUIRED` (any blocking P0/P1) > `REVIEW CLEAN` — never a hybrid such as a clean Result with a coverage qualifier — and a conditional [`Reasoning check`](../../shared/policies/reasoning-checkpoint.md).

Machine detail (base/HEAD SHAs, synchronization status, raw counts,
per-category inclusion/exclusion, staged-delta fingerprint) is
subordinate — a trailing plain-Markdown metadata block, never ahead of
the human-facing review. The fingerprint and the previously-reviewed-state
comparison are always computed; their *display* is relevance-gated per
the report template. The report is returned to the caller as one complete
document — never published, never streamed finding-by-finding. With
`include_fix_prompt=false` (default) findings carry no full implementation
prompt, and a clean review never manufactures implementation work.

## 4. Statelessness and Orchestration Boundary

Each invocation is `current state → review → findings → stop`, with no
memory of prior invocations. This Skill does **not**: decide whether
another iteration should run; count or cap review-loop attempts; control
the implementing Agent; commit, push, or open PRs; ask the user for
approval to run; or assume a prior approval extends to this or any future
invocation. On its own side of the
boundary owned by
[`policies/invocation-approval.md`](policies/invocation-approval.md), it
does not ask for approval, does not track prior approvals, and does not
decide whether a re-review should happen — every invocation still
requires fresh, explicit user approval scoped to that one run, and this
Skill can neither verify nor needs to verify that it occurred. Running it
as a delegated Agent/Sub-Agent is purely mechanical and never changes who
owns the decision to invoke it. Loop limits and re-review timing are an
orchestration concern; for recommended (not enforced) re-review
discipline see [`runbooks/local-review.md`](runbooks/local-review.md).
This Skill holds no `spawn_agent` capability of its own — it is a single
bounded invocation with no worker fan-out; see
[`agent-delegation.md`](../../shared/policies/agent-delegation.md),
"`spawn_agent` is an explicit capability" (absent by default).

## 5. Mutation Boundary

This Skill must never: edit files, apply patches, commit, push, rebase,
create branches, open PRs, approve anything, or request changes on
GitHub. The implementing Agent owns remediation; the orchestrator owns
workflow progression; this Skill only reviews and reports. This holds
identically when an optional PR reference is supplied per section 1:
reading PR review context is read-only and never becomes GitHub
publication, an Approve/Request Changes decision, or any other GitHub
mutation — see [`policies/pr-context.md`](policies/pr-context.md),
"Boundary with `github-pr-review`."

## 6. Configuration

None. This Skill package intentionally has no `review-config.yaml` and no
concept of a maximum loop count. Any default iteration cap is owned by
whatever runtime coordinates repeated invocations, outside this Skill's
package.
