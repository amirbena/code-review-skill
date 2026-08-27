---
name: local-code-review
description: >-
  Reviews local, not-yet-PR'd Git changes (committed delta, staged,
  unstaged, and untracked) and returns evidence-backed P0/P1/P2 findings.
  Read-only and opt-in only: never edits, commits, pushes, or touches
  GitHub, and every review or re-review requires explicit user selection.
  Optionally accepts free-form context such as requirements, Jira/HLD/ADR,
  acceptance criteria, or implementation plans to focus the review, plus
  an associated GitHub PR reference for reconciling prior findings and
  architectural decisions. The local delta always remains the review
  scope. For reviewing an existing PR itself, use github-pr-review.
---

# SKILL.md — local-code-review

A small, bounded, **stateless** Code Review Skill that reviews a local
Git repository's implementation state and returns structured P0/P1/P2
findings. It is a reviewer only.

**Compatibility:** requires access to a local Git repository; an
optional PR reference additionally requires read-only GitHub access.

```text
resolve local review scope
    ↓
resolve changed files, then one normalized per-file AGENTS.md/CLAUDE.md
    hierarchy from the target repository (the local repo under review)
    ↓
inspect Git delta by category: committed, staged, unstaged, untracked
    ↓
compute staged-delta fingerprint
    ↓
Jira reference supplied? → yes → resolve via Jira MCP/connector (read-only)
                                   → resolved → normalized Jira context
                                   → unresolvable → JIRA CONTEXT UNRESOLVED,
                                     stop (no key/branch inference)
                                → no  → unchanged
    ↓
optional review context supplied? → yes → understand intended change,
                                            extract requirements/
                                            invariants/non-goals, map onto
                                            the delta (never expands scope)
                                         → no  → unchanged
    ↓
optional PR reference supplied? → yes → read/classify/reconcile
                                          relevant PR context against
                                          this delta (never expands scope)
                                       → no  → unchanged
    ↓
inspect relevant surrounding code
    ↓
review against code + repository conventions, focused per any supplied
review context
    ↓
classify findings by severity (source never changes classification)
    ↓
derive decision mechanically from blocking severities (P0/P1)
    ↓
return P0/P1/P2 findings
    ↓
stop
```

**This Skill MUST NOT be invoked automatically.** Every invocation — the
first review of an implementation and any later re-review after fixes —
requires the caller to have already obtained fresh, explicit user
approval scoped to that one run before invoking this Skill. That
approval must have a meaning that unambiguously requests a local code
review in the current interaction — naming this Skill is one sufficient
form of that, never a required phrase. Generic validation/completion
language ("check your work," "make sure this is correct"), a remembered
or standing user preference, repository/orchestration policy, or
silence/non-objection never qualify by themselves, regardless of how
strongly they imply review would be welcome. An approval that authorized one
invocation never authorizes another. This holds regardless of whether
the implementing Agent invokes this Skill directly or delegates it as an
Agent/Sub-Agent call — the orchestration mechanism never changes who
owns the decision, which is always the end user, never the implementing
Agent. See [`policies/invocation-approval.md`](policies/invocation-approval.md)
for this Skill's complete, self-contained invocation-approval contract,
and "Statelessness and Orchestration Boundary" below for this Skill's
own side of that boundary: it does not ask for approval, does not track
prior approvals, and does not decide whether a re-review should happen.

See [`runbooks/local-review.md`](runbooks/local-review.md) for the full
procedure and [`templates/local-review-report.md`](templates/local-review-report.md)
for the output contract.

---

## 1. Identity

- **Name:** `local-code-review`
- **Purpose:** review the complete local implementation state of a Git
  repository (committed delta, staged, unstaged, and untracked changes)
  and return findings.
- **Not:** an orchestrator, a fix loop, a Git-mutating agent, or a
  GitHub-publishing agent. See the sibling `github-pr-review` Skill for
  GitHub Pull Request review.

## 2. Inputs

A local Git repository. The Skill inspects the explicit repository state
categories owned by
[`policies/repository-state.md`](policies/repository-state.md) —
committed delta relative to a base, staged (tracked, indexed), unstaged
(tracked, working-tree-only), and untracked files — never a single
undifferentiated "relevant files" blend. It may also inspect current
branch, base branch, base SHA, local HEAD, relevant surrounding
repository code, tests, and repository instructions. Push/synchronization
status (including whether commits are local-only/not yet pushed) is a
distinct concern from base-relative committed delta and is resolved
against the branch's configured upstream, never against the review base
— see [`runbooks/local-review.md`](runbooks/local-review.md), step 5.
The full implementation state is reviewed — local `HEAD` alone is never
assumed to contain everything, and no category is silently skipped
without saying so in the report.

**Optional:** review context describing the intended change. Two forms,
per [`review-context.md`](../../shared/policies/review-context.md), "Input
form":

- **Textual / free-form** — requirements, explicit user instructions,
  pasted Jira/ticket text and/or acceptance criteria, a pasted GitHub
  Issue, an HLD/architecture document/ADR, an implementation plan, a bug or
  incident description, a PR/task description, or migration/security/
  performance/rollout requirements. Consumed directly, no resolution step.
- **Reference-based** — a bare Jira ticket key or URL, or a GitHub Issue
  reference. A reference is a pointer to context, not the context itself.
  When a **Jira reference** is supplied, this Skill executes the shared
  [`review-context.md`](../../shared/policies/review-context.md), "Jira
  context resolution" → **"Resolution procedure"** **before** review
  reasoning: identify an available Jira MCP / connector / runtime-exposed
  Jira read tool, invoke it read-only to fetch the issue's contents, fetch
  relevant comments and linked context when supported, normalize, and
  continue only on success. If the Jira reference cannot be resolved (no
  integration, authentication or authorization failure, issue not found,
  malformed reference, or connector/MCP error or timeout),
  this Skill does **not** infer ticket contents from the key, branch name,
  or surrounding text and does **not** perform the Jira-scoped review — it
  returns the explicit `JIRA CONTEXT UNRESOLVED` outcome instead. A GitHub
  Issue reference is resolved through read-only GitHub access when
  available, or supplied as pasted text; no automatic PR↔Issue discovery.

When supplied and (for a Jira reference) resolved, this Skill uses the
context to understand the intended change, focus review attention, and
reason about the scope boundary of the requested change — never as an
authority that overrides actual implementation evidence — before
performing the rest of its own review. The shared review-target /
review-context / repository-context model and the requirement-context
semantics are defined once in
[`review-context.md`](../../shared/policies/review-context.md);
[`policies/review-context.md`](policies/review-context.md) is this Skill's
thin local application of it (the review target stays the local delta).
When omitted, this Skill's behavior is exactly as if this input did not
exist, and this Skill never asks for it. Supplying no Jira reference is
always valid; Jira is never mandatory.

**Optional:** a reference to an associated GitHub PR (a PR URL, or a PR
number when the repository can be inferred unambiguously). When supplied,
this Skill reconciles the local delta against relevant existing reviewer
findings, prior review comments, and settled architectural/design decisions
from that PR — as Existing Review Evidence, per
[`review-evidence.md`](../../shared/policies/review-evidence.md) and this
Skill's thin local application
[`policies/pr-context.md`](policies/pr-context.md) — before performing the
rest of its own review. The local delta always remains the review target.
When omitted, this Skill's behavior is exactly as if this input did not
exist.

**Optional:** `include_fix_prompt` (boolean, default `false`). This is an
explicit output-only opt-in. When `true`, an actionable finding may append a
coding-agent-ready implementation prompt when the issue is blocking,
structural, cross-file, rooted in a canonical owner, or otherwise requires a
tricky correction. Simple findings may retain only a concise recommended
direction. The flag never changes the Review Target, inspection, evidence,
finding identity, severity, deduplication, PR-context reconciliation, or
mechanical Decision, and it never authorizes mutation or an autonomous fix
workflow. It is not inferred from urgency, severity, branch name, or intent.

The context and PR-reference optional inputs are independent — either, both,
or neither may
be supplied in a given invocation, with no ordering requirement between
them from the caller's side.

## 3. Required Policy Loading

Always: [`review-scope.md`](../../shared/policies/review-scope.md),
[`severity.md`](../../shared/policies/severity.md),
[`evidence.md`](../../shared/policies/evidence.md),
[`repository-instructions.md`](../../shared/policies/repository-instructions.md),
[`review-context.md`](../../shared/policies/review-context.md) (the shared
review-target / review-context / repository-context / existing-review-evidence
model; its requirement-context and scope-boundary sections bind only when
context is actually supplied),
[`git-safety.md`](../../shared/policies/git-safety.md). In orchestrated/
multi-Agent contexts, also
[`review-ownership.md`](../../shared/policies/review-ownership.md).
Always apply [`remediation-guidance.md`](../../shared/policies/remediation-guidance.md)
to finding guidance.
For every changed-file category, including generated or opaque content,
apply [`file-reviewability.md`](../../shared/policies/file-reviewability.md).

Also always: [`review-summary.md`](../../shared/templates/review-summary.md)
(the shared human-facing review body shape).

This Skill's own: [`policies/invocation-approval.md`](policies/invocation-approval.md)
(the complete per-invocation, explicit-user-approval contract — see
section 5 below) and
[`policies/repository-state.md`](policies/repository-state.md) (the
committed/staged/unstaged/tracked/untracked category definitions,
per-category detection commands, and the staged-delta fingerprint).
Additionally, only when review context is supplied per section 2: the shared
[`review-context.md`](../../shared/policies/review-context.md) requirement-
context and scope-boundary sections, and this Skill's thin
[`policies/review-context.md`](policies/review-context.md) (mapping supplied
context onto the local delta, never widening it). This policy is never
loaded or applied when no review context is supplied. Additionally, only
when a PR reference is supplied per section 2: the shared
[`review-evidence.md`](../../shared/policies/review-evidence.md) (the
Existing Review Evidence model) and
[`policies/pr-context.md`](policies/pr-context.md) (this Skill's thin local
application: retrieval scope and reconciliation of prior findings, prior
review comments, and settled decisions against the local delta). This
policy is never loaded or applied when no PR reference is supplied. Each
optional input's policies are loaded and applied independently of the
other, and only when its own respective input is supplied — never
otherwise.

This Skill defines no severity, evidence, or scope policy of its own — it
consumes the shared ones so both Skills apply one review standard.

None of the files above depend on another's content to be read — load
them together in a single batched/parallel operation rather than one at a
time in sequence. This changes only retrieval speed, never which policies
apply or what they require.

## 4. Output Contract

Exactly one [`templates/local-review-report.md`](templates/local-review-report.md)
per invocation, rendering the shared human-facing shape in
[`review-summary.md`](../../shared/templates/review-summary.md): a
Result, What changed, What was done well, an optional Context section
(present only when review context was supplied per section 2 and it
materially shaped the review — see
[`policies/review-context.md`](policies/review-context.md), "Output"), an
optional PR Context section (present only when a PR reference was
supplied per section 2 and it materially shaped the review — see
[`policies/pr-context.md`](policies/pr-context.md), "Output"), Findings,
Validation, and a Decision of `REVIEW CLEAN` or `CHANGES REQUIRED`
derived mechanically from blocking (P0/P1) severities — see
[`../../shared/policies/severity.md`](../../shared/policies/severity.md),
"Decision derivation (mechanical)."
Machine-oriented detail
(base/HEAD SHAs, synchronization status, raw P0/P1/P2 counts, per-category
inclusion/exclusion, and the staged-delta fingerprint per
[`policies/repository-state.md`](policies/repository-state.md)) is
subordinate, appearing only in a trailing metadata block, in plain
Markdown, never ahead of the human-facing review. The fingerprint and the
previously-reviewed-state comparison are always computed regardless of
whether they are shown, but their *display* is relevance-gated per
[`templates/local-review-report.md`](templates/local-review-report.md),
"Relevance-aware metadata rendering" — every other metadata field above
renders unconditionally. Returned to the caller as one complete report —
never published anywhere, and never streamed finding-by-finding as
findings are discovered.
With `include_fix_prompt=false` (the default), findings contain no full
implementation prompt. With the flag explicitly enabled, qualifying existing
findings may append one per the local report template; a clean review never
manufactures implementation work. Only remediation rendering differs.

## 5. Statelessness and Orchestration Boundary

**This Skill does not own a multi-step fix loop.** Each invocation is:

```text
current implementation state
    ↓
review
    ↓
findings
    ↓
stop
```

It has no memory of prior invocations and does not need to know whether
this is review pass 1, 2, 3, or later. Specifically, this Skill does
**not**:

- decide whether another review iteration should run;
- count review-loop attempts or track a maximum;
- control or instruct the implementing Agent;
- commit fixes, push changes, or open PRs;
- ask the user for approval to run;
- assume a prior approval extends to this invocation, or to any future
  one.

**Every invocation requires fresh, explicit user approval scoped to
that one run**, obtained by the caller before invoking this Skill — see
[`policies/invocation-approval.md`](policies/invocation-approval.md) for
the complete, self-contained contract. This Skill has no mechanism to
verify that approval occurred and does not need one: obtaining and
scoping approval is entirely the caller's/orchestrator's responsibility,
never this Skill's. In particular, this Skill must never be treated as
self-triggering: returning findings from one invocation is never, by
itself, authorization for the caller to invoke this Skill again after
fixes are applied. A separate, explicit approval is required for every
subsequent invocation.

**Invocation ownership is independent of orchestration mechanics.** The
implementing Agent may run this Skill as a delegated Agent/Sub-Agent
under whatever orchestration model it uses; that delegation is purely
mechanical and never changes who owns the decision to invoke it. The end
user, not the implementing Agent, decides whether a given review or
re-review happens at all — invoking this Skill as a Sub-Agent call is
never itself a substitute for that user decision, and an implementing
Agent must not autonomously choose to run this Skill merely because it
has the technical ability to invoke it as a delegated Agent/Sub-Agent.

**Loop limits, re-invocation timing, and workflow progression are
entirely an orchestration concern**, owned by the calling
runtime/Team Lead/implementing workflow — not by this Skill. A caller
that wants an iterative review/fix loop must obtain a new, explicit user
approval before each individual invocation in that loop — see
[`policies/invocation-approval.md`](policies/invocation-approval.md). For
recommended (not enforced) re-review discipline across repeated,
separately-approved invocations, see
[`runbooks/local-review.md`](runbooks/local-review.md).

## 6. Mutation Boundary

This Skill must never: edit files, apply patches, commit, push, rebase,
create branches, open PRs, approve anything, or request changes on
GitHub. The implementing Agent owns remediation; the orchestrator owns
workflow progression; this Skill only reviews and reports. This holds
identically when an optional PR reference is supplied per section 2:
reading PR review context is read-only and never becomes GitHub
publication, an Approve/Request Changes decision, or any other GitHub
mutation — see [`policies/pr-context.md`](policies/pr-context.md),
"Boundary with `github-pr-review`."

## 7. Review Ownership

Subject to the same `One review scope → one Code Review Agent owner`
invariant as `github-pr-review` — see
[`../../shared/policies/review-ownership.md`](../../shared/policies/review-ownership.md).
If another Code Review Agent already owns this local branch/scope, return
`REVIEW ALREADY OWNED` and do not launch a competing review.

## 8. Configuration

None. This Skill package intentionally has no `review-config.yaml` and no
concept of a maximum loop count — see section 5. A separate,
orchestration-level configuration (owned by whatever runtime coordinates
repeated invocations) may define a default iteration cap; that is outside
this Skill's package.
