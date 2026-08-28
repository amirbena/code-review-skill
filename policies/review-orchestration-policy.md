# Review Orchestration Policy

Canonical rules for **orchestrating the review Skills during development of
and around this repository**: the orchestration boundary, Skill-consumer
branch discipline, review ownership, the implementer/reviewer separation,
the explicit `local-code-review` approval gate, and human-facing review
publication.

This is a repository-development / orchestration policy. It is **not**
packaged into either Skill archive, and no packaged Skill resource may
depend on it. The **packaged** review semantics it points to live in
`skills/` and `shared/` and remain the single source of truth for how a
review is performed. See [`AGENTS.md`](../AGENTS.md) for global invariants
and routing, and [`skill-development-policy.md`](skill-development-policy.md)
for the portable-core / packaging boundary.

## Orchestration boundary

Review orchestration is external to the individual review Skills.
Deciding when to invoke a Skill, whether to invoke it again, how many
review/fix iterations to run, and when to progress from local review to
opening a PR to GitHub review is the responsibility of the calling
runtime, Team Lead, or implementing workflow — never of
`local-code-review` or `github-pr-review` themselves. See
[`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md), "Orchestration Boundary." This
discretion is bounded, not open-ended: it never extends to an
implementing Agent invoking `github-pr-review` on the PR it just opened
or updated for its own implementation work — see "Implementation Workflow
Termination and Reviewer/Author Separation" below. Nor does it extend to
invoking `local-code-review` automatically — every invocation requires
fresh, explicit user approval scoped to that one run — see "Explicit User
Approval Required for `local-code-review` Invocation" below.

## Skill Consumer Branch Policy

This section governs branch discipline for Agents *consuming* either
Code Review Agent Skill against a target repository (the repository being
reviewed) — as distinct from [`repository-workflow.md`](repository-workflow.md),
which governs development of *this* repository.

The Code Review Agent must understand the distinction between:

- **external PR review** — reviewing a Pull Request that already exists
  on a remote GitHub repository, opened by some other Agent or developer;
- **local implementation review** — reviewing an implementation branch in
  a local working copy, before or during PR creation.

For local implementation workflows, formal review occurs on a dedicated
implementation branch, not directly on the repository's protected/default
branch, unless that repository's own rules explicitly permit it. Before
beginning a local implementation review, the reviewer verifies that:

- the target is a valid Git repository;
- the current branch is identifiable;
- the implementation scope is not accidentally being performed directly
  on a protected/default branch unless repository rules explicitly permit
  it;
- the branch actually contains the implementation intended for review
  (see [`../skills/local-code-review/runbooks/local-review.md`](../skills/local-code-review/runbooks/local-review.md));
- base and branch state are understood (base branch, base SHA, local
  HEAD, and any divergence from a remote tracking branch).

**The reviewer must not create arbitrary branches just to make review
possible.** Branch creation is owned by the implementing workflow, not by
the Code Review Agent. The reviewer's role is limited to validating branch
state and reviewing what already exists.

## Review Ownership

Preserved as a canonical repository-wide principle, applying
independently to both Skills:

```text
One review scope → one Code Review Agent owner
```

The full invariant — including the "Access vs. Ownership" distinction and
the multi-Agent/parallel-review guards — is defined once, in
[`../shared/policies/review-ownership.md`](../shared/policies/review-ownership.md),
so it is packaged with either Skill rather than living only in this
repository-development document. Both `local-code-review` and
`github-pr-review` reference that file directly.

## Implementation Workflow Termination and Reviewer/Author Separation

An implementing Agent's normal workflow ends when it opens or updates the
Pull Request containing its own implementation work. Opening/updating
that PR is the **terminal step** of the implementation workflow, not a
step that automatically chains into review:

```text
implement
    ↓
validate
    ↓
commit
    ↓
push
    ↓
open or update PR
    ↓
STOP
```

The following flow is prohibited: an implementing Agent must never invoke
`github-pr-review` against the PR it just created or updated as part of
its own implementation workflow.

```text
implement → validate → commit → push → open PR → invoke github-pr-review on that PR   ✗ prohibited
```

This holds regardless of whether the implementing Agent technically has
access to the `github-pr-review` Skill. `github-pr-review` is a reviewer
role, not a post-implementation validation step, and it requires a
genuine reviewer/author separation to mean anything — see
[`../skills/github-pr-review/SKILL.md`](../skills/github-pr-review/SKILL.md)
and [`../skills/github-pr-review/policies/review-authority.md`](../skills/github-pr-review/policies/review-authority.md),
"Self-review capability."

Valid shapes keep implementer and reviewer distinct:

```text
Agent A implements → opens PR → STOP
Agent B / a dedicated reviewer → invokes github-pr-review

existing external PR → github-pr-review
```

If local review is wanted for implementation work in progress, that
belongs to `local-code-review`, invoked before or during implementation
completion, subject to its own invocation conditions — see "Explicit User
Approval Required for `local-code-review` Invocation" below — and never
invoked automatically, and never to `github-pr-review` used as a
substitute completion check:

```text
implementation
├─ optional local-code-review, if its invocation conditions are satisfied
└─ commit / push / PR
   └─ STOP

review assignment (separate task, separate identity)
    ↓
github-pr-review
```

Orchestration is the primary safeguard here. `github-pr-review` also
carries its own defensive self-review guard for the case where it is
nevertheless invoked against a PR authored by the authenticated identity
— see [`../skills/github-pr-review/policies/review-authority.md`](../skills/github-pr-review/policies/review-authority.md),
"Self-review capability." That guard is a fallback, not a substitute for
orchestration honoring the rule above.

## Explicit User Approval Required for `local-code-review` Invocation

`local-code-review` MUST NOT be invoked automatically at any point in an
implementation workflow. Each invocation — the first review and any
later re-review after fixes — requires fresh, explicit user approval
scoped to that specific run; approval for review N never authorizes
review N+1. Obtaining that approval is entirely the responsibility of
the caller, Team Lead, runtime, or implementing workflow — never of the
Skill itself:

```text
implementation complete (or a fix just applied)
    ↓
caller asks the user for approval to run local-code-review
    ↓
fresh approval for this run?
├── yes → one local-code-review invocation
└── no  → do not invoke; continue without review

another review desired afterward → fresh approval required again
```

`local-code-review` is optional and user-authorized, never a mandatory
terminal gate before commit, push, or PR creation.

This is a repository-level orchestration summary only. The complete
portable contract — approval scope, prohibited invocation flows, the
caller/orchestrator responsibility boundary, and what the Skill itself
must never do — is owned by
[`../skills/local-code-review/policies/invocation-approval.md`](../skills/local-code-review/policies/invocation-approval.md),
which this rule does not duplicate. Unlike `github-pr-review`'s self-review
guard, `local-code-review` has no external fact it can check to verify
approval actually occurred — see that policy's "Structural limitation: this
Skill cannot verify that approval occurred," which is why obtaining and
scoping approval correctly is entirely the orchestrator's responsibility
here, with no Skill-side defensive fallback. See also
[`../skills/local-code-review/SKILL.md`](../skills/local-code-review/SKILL.md),
"Statelessness and Orchestration Boundary," and
[`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md), "Handoff Between Skills," for how
this approval gate fits into the overall implementation lifecycle.

## Human-Facing Review Publication

Preserved as a canonical repository-wide principle, applying
independently to both Skills:

```text
analyze complete review scope
    ↓
collect candidate findings
    ↓
verify evidence
    ↓
finalize severity
    ↓
deduplicate findings
    ↓
determine decision
    ↓
publish one organized review
```

Each Skill's output is a finalized review artifact, not a stream of
intermediate reviewer observations. A candidate finding may still be
revised, merged, upgraded, downgraded, or discarded during analysis —
publishing it before finalization would expose reasoning that has not
yet settled, and risks noisy, contradictory, or duplicate output. Neither
Skill publishes a finding, comment, or partial review as it is
discovered; both publish once, after the review scope is complete and
findings are finalized.

`local-code-review` always returns exactly one organized report per
invocation, never a sequence of separately surfaced findings followed by
a summary — see
[`../skills/local-code-review/SKILL.md`](../skills/local-code-review/SKILL.md),
"Statelessness and Orchestration Boundary," and
[`../skills/local-code-review/runbooks/local-review.md`](../skills/local-code-review/runbooks/local-review.md).

`github-pr-review`, whenever the GitHub review capability supports a
submission carrying both a review body and multiple inline comments,
submits finalized inline findings together as part of one coherent
GitHub review rather than one standalone comment per discovered finding.
When a resolved inline location is unavailable or rejected, the finding
remains represented in the review body rather than being dropped or
attached to an arbitrary line. The complete batching, inline-eligibility,
and fallback contract is owned by
[`../skills/github-pr-review/policies/review-output.md`](../skills/github-pr-review/policies/review-output.md)
("Analysis phase vs. publication phase," "Batched review construction
and submission") and
[`../skills/github-pr-review/policies/finding-placement.md`](../skills/github-pr-review/policies/finding-placement.md)
("Rejected inline location fallback"), indexed from
[`../skills/github-pr-review/policies/github-review.md`](../skills/github-pr-review/policies/github-review.md).
This policy does not duplicate that contract.

The complete human-facing output shape (result, what changed, meaningful
strengths, findings, validation, decision) and the finding contract
(what/where/evidence/impact/fix) are owned by
[`../shared/templates/review-summary.md`](../shared/templates/review-summary.md)
and [`../shared/templates/finding.md`](../shared/templates/finding.md),
consumed identically by both Skills — this policy does not duplicate their
complete templates. Machine-oriented state (reviewed HEAD, finding
counts, a normalized decision value, internal identifiers) may remain
available where genuinely required by orchestration, but stays
subordinate to that human-facing output in both Skills' published and
returned review artifacts.
