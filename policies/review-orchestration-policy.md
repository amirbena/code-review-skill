# Review Orchestration Policy

Canonical rules for **orchestrating the review Skills during development of
and around this repository**: the orchestration boundary, Skill-consumer
branch discipline, the implementer/reviewer separation, the explicit
per-run request, and human-facing review publication.

This is a repository-development / orchestration policy. It is **not**
packaged into any Skill archive, and no packaged Skill file may depend on
it. The **packaged** review semantics it points to live in `skills/` and
remain the single source of truth for how a review is performed. See
[`AGENTS.md`](../AGENTS.md) for global invariants and routing, and
[`skill-development-policy.md`](skill-development-policy.md) for the
portable-core / packaging boundary.

## Orchestration boundary

Review orchestration is external to the individual review Skills. Deciding
when to invoke a Skill, whether to invoke it again, how many review/fix
iterations to run, and when to progress from local review to opening a PR to
GitHub review is the responsibility of the calling runtime, Team Lead, or
implementing workflow — never of `review-core` or a mini-skill themselves.
This discretion is bounded, not open-ended: it never extends to an
implementing Agent publishing a review to the PR it just opened or updated
(see "Implementation Workflow Termination and Reviewer/Author Separation"),
nor to starting a review without the user's own request (see "Explicit
per-run request").

## Skill Consumer Branch Policy

This section governs branch discipline for Agents *consuming* a Code Review
Agent Skill against a target repository (the repository being reviewed) — as
distinct from [`repository-workflow.md`](repository-workflow.md), which
governs development of *this* repository.

The Code Review Agent must understand the distinction between:

- **external PR review** — reviewing a Pull Request that already exists on a
  remote GitHub repository, opened by some other Agent or developer;
- **local implementation review** — reviewing an implementation branch in a
  local working copy, before or during PR creation.

For local implementation workflows, formal review occurs on a dedicated
implementation branch, not directly on the repository's protected/default
branch, unless that repository's own rules explicitly permit it. Before
beginning a local implementation review, the reviewer verifies that:

- the target is a valid Git repository;
- the current branch is identifiable;
- the implementation scope is not accidentally being performed directly on a
  protected/default branch unless repository rules explicitly permit it;
- the branch actually contains the implementation intended for review;
- base and branch state are understood (base branch, base SHA, local HEAD,
  and any divergence from a remote tracking branch).

**The reviewer must not create arbitrary branches just to make review
possible.** Branch creation is owned by the implementing workflow, not by the
Code Review Agent. The reviewer's role is limited to validating branch state
and reviewing what already exists.

## Implementation Workflow Termination and Reviewer/Author Separation

An implementing Agent's normal workflow ends when it opens or updates the
Pull Request containing its own implementation work. Opening/updating that PR
is the **terminal step** of the implementation workflow, not a step that
automatically chains into review or publication:

```text
implement → validate → commit → push → open or update PR → STOP
```

An implementing Agent must never run `review-core` and then publish the
result with `review-publish-github` against the PR it just created or
updated as part of its own implementation workflow. A review published for
one's own work is a self-review, and a self-review never counts as an
independent approval: `review-publish-github` limits it to a `COMMENT` event
and never submits `APPROVE` or `REQUEST_CHANGES` on that work. The canonical
rule is S7 in `skills/review-publish-github/SKILL.md` and its
`rules/authority.md`; this summary does not restate it.

Valid shapes keep implementer and reviewer distinct:

```text
Agent A implements → opens PR → STOP
Agent B / a dedicated reviewer → review-core, then review-publish-github if asked to publish
```

An implementing Agent also cannot switch identities, tokens, bots, or nested
agents to manufacture its own approver.

## Explicit per-run request

No review Skill is invoked automatically at any point in an implementation
workflow. Each run — the first review and any later re-review after fixes —
requires the user's own request in that conversation (S2). A mode, a mini-skill
selection or an approval for one run never authorizes another. Obtaining the
request is the responsibility of the caller, Team Lead, runtime, or
implementing workflow, never of the Skill itself:

```text
implementation complete (or a fix just applied)
    ↓
caller asks the user whether to run a review
    ↓
user asks for this run?
├── yes → one review run
└── no  → do not invoke; continue without review

another review desired afterward → a new request is required again
```

A review is optional and user-authorized, never a mandatory terminal gate
before commit, push, or PR creation. The complete portable contract, including
what a Skill must never do, is S2 in `skills/review-core/SKILL.md`; this
summary does not restate it.

## Human-Facing Review Publication

Each Skill's output is a finalized review artifact, not a stream of
intermediate observations. A candidate finding may still be revised, merged,
upgraded, downgraded, or discarded during analysis, so publishing it before
finalization would expose reasoning that has not settled and risks noisy,
contradictory, or duplicate output.

`review-core` returns exactly one organized report per run and publishes
nothing. Only `review-publish-github` publishes, and only when the user's
request asks for it: it submits one batched review after the review is
complete, with a finding that has no valid inline location kept in the review
body rather than dropped or attached to an arbitrary line. The report shape is
owned by `skills/review-core/templates/report.md` and the published shape by
`skills/review-publish-github/templates/review.md`; this policy duplicates
neither.
