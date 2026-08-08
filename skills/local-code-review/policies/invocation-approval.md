# Policy — Invocation Approval

This Skill's own policy for when it may be invoked, independent of any
particular runtime, orchestrator, or source repository. This file is the
single canonical owner of the per-invocation approval invariant; the
Skill's own [`../SKILL.md`](../SKILL.md) and
[`../runbooks/local-review.md`](../runbooks/local-review.md) state the
concise behavioral consequence and reference this file rather than
redefining the rule.

## The invariant

`local-code-review` MUST NOT be invoked automatically. This holds at
every point in an implementation workflow — not after implementation
finishes, not after validation, not after a fix, and not immediately
after a previous review returned findings.

Each invocation requires fresh, explicit user approval scoped to that
specific review run:

```text
implementation finished (or a fix just applied)
    ↓
caller asks the user whether to run local-code-review
    ↓
explicit approval for this run?
├── yes → invoke local-code-review once
└── no  → do not invoke; continue without review
```

## Approval is not persistent

Approval obtained for one invocation authorizes exactly that one
invocation. It must never be treated as:

- approval for the rest of the task;
- approval for all future reviews;
- approval for a review/fix loop;
- approval to automatically re-run after findings are fixed;
- approval to invoke whenever the implementation changes.

```text
user approves review #1
    ↓
local-code-review runs once
    ↓
findings returned
    ↓
fixes applied
    ↓
review #2 desired
    ↓
caller asks the user again — the approval for review #1
does not authorize review #2
```

Approval for review N never authorizes review N+1. This applies to every
subsequent iteration of a review/fix cycle, no matter how many times it
repeats.

## Prohibited invocation flows

```text
implement → validate → automatically invoke local-code-review            ✗ prohibited

user approved local review once → review → fix findings
    → automatically review again                                        ✗ prohibited

local-code-review returns findings → caller invokes it again on its own
    after fixes, without asking                                         ✗ prohibited

caller decides review is "best practice" or repository policy
    recommends it → invokes local-code-review without asking            ✗ prohibited
```

A general preference for review — from a caller, a runtime default, or a
target repository's own conventions — never substitutes for asking the
user before each specific invocation.

## Scope of explicit approval

Approval must be unambiguous and specific to the current review run —
for example, an instruction equivalent to "run local-code-review now,"
"yes, review the current implementation," or "perform one local review
before pushing." A previous approval from earlier in the task must never
be reused. General statements such as "review things carefully," or a
policy that merely recommends review, do not create standing
authorization for repeated invocations.

## Caller/orchestrator responsibility boundary

Obtaining approval is entirely the responsibility of the caller, Team
Lead, runtime, or implementing workflow that invokes this Skill:

```text
caller/orchestrator
    ↓
determines whether review is desired
    ↓
asks user
    ↓
receives explicit approval for this run
    ↓
invokes local-code-review once
```

This Skill itself does not, and must not attempt to:

- ask the user for permission;
- verify that approval was obtained;
- decide whether another review iteration should happen;
- automatically schedule or self-trigger a re-review;
- continue a review/fix/review loop on its own.

This Skill has no mechanism to confirm approval occurred and does not
need one — that responsibility belongs entirely to the caller, never to
this Skill. This Skill only reviews the scope it was explicitly invoked
to review, once, per invocation; see
[`../SKILL.md`](../SKILL.md), "Statelessness and Orchestration Boundary."

## Why this exists

Without this invariant, a caller could treat `local-code-review` as an
implicit, automatic completion gate — running it after every
implementation step, or re-triggering it after every fix, without the
user ever having asked for that specific review. This policy exists so
that review remains a deliberate, user-authorized action rather than an
unrequested standing obligation.
