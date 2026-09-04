# GitHub publication & review authorization

## What it does

Controls what `github-pr-review` publishes to a PR and under what
authority. **Review analysis is always separate from GitHub mutation
authority**: the review always runs and produces a mechanically derived
verdict; whether that verdict is *submitted* to GitHub is a separate,
authorized step.

| Situation | What gets published |
| --- | --- |
| Passive review | Nothing — a report is returned to you |
| Self-review | Informational `COMMENT` + one disclosure line; no formal event |
| Active external review, no trusted authorization | Findings + verdict, **no** GitHub mutation (the safe default) |
| Active external review, blocking, `block-only` | `REQUEST_CHANGES` (needs reviewer independence + GitHub permission) |
| Active external review, `explicitly-authorized auto-action` | The permitted `APPROVE` **or** `REQUEST_CHANGES` |

An active review is published as **one batched submission** (body +
inline comments + event). Publication order is fixed:
`final review comment == last publication event` — any optional
machine-readable status is published *before* that submission, and
nothing review-owned is published or edited after it.

Optionally, `github-pr-review` can also publish **one stable, aggregated,
exact-HEAD machine-readable status/check** for the reviewed SHA, separate
from the native event: a blocking (non-`success`) status is blocking-only
enforcement and may be published even by a self-review; a `success`
status needs the same trusted positive authorization as `APPROVE` and is
never published by a self-review; a new HEAD inherits no green. The Skill
can also report, read-only, whether that context is `ENFORCED` /
`NOT ENFORCED` / `UNKNOWN`, and — only as a separate, explicitly
requested, minimal, preserving setup action — add that one context to a
base branch's required checks.

## When it is useful

- You want a report only, with zero writes to the PR → passive.
- You want the Skill to *block* a PR with serious issues but never
  approve → `block-only`.
- A human principal has authorized this specific review to approve a
  clean PR or request changes → auto-action.

## Which Skill(s)

`github-pr-review` only. `local-code-review` never publishes to GitHub,
even when given a PR reference.

## Default, conditional, or requested

**Default is `recommendation-only`** — a full review and verdict with no
GitHub mutation. You never need to say "do not approve" to get safe
behavior. Stronger modes are chosen from natural language, but the mode
is only a *request*: submitting `APPROVE` (or a `success` status)
additionally requires **trusted mutation authorization** that originates
from a principal independent of the agent performing/orchestrating the
review, reaches the Skill through a channel that agent cannot author or
replay, and is scoped to this exact repo / PR / reviewed HEAD / single
action. Ambiguity fails closed.

## How to invoke it

```text
just review PR #812 and tell me what you find          → report only
review #812; block it if there are serious issues       → may Request Changes
review #812 and approve it if it's clean                → Approve only if
                                                          independently authorized
```

For the machine-readable status / enforcement setup, ask explicitly, e.g.
*"also publish the review status check for this PR"* or *"make the
code-review status a required check on main"* (the latter is the separate
setup action).

## Limitations & safety boundaries

- **A verdict is not authorization; `APPROVE` is not merge authority.**
  This Skill never merges, never enables auto-merge, and never deletes
  branches. Maximum positive action is **Approve** / a `success` status.
- **Self-review is allowed; self-approval is not** — authorship (or a
  shared controlling authority: alternate account, token, bot, service
  account, GitHub App, nested agent) forbids any formal
  `APPROVE` / `REQUEST_CHANGES` on the reviewer's own work.
- **Reviewer independence is authority separation, not a different
  username.**
- **HEAD safety** — the reviewed HEAD is revalidated immediately before
  submission; a stale HEAD is never approved, and any authorization is
  bound to the exact HEAD.
- Agent-controlled input — flags, prompts, generated text, nested
  invocations, alternate tokens — can never establish mutation authority.
- The optional **isolated read-only PR checkout** used for richer context
  is a throwaway clone, never the target repo, and no target-repository
  code runs in it
  ([`repository-checkout.md`](../../skills/github-pr-review/policies/repository-checkout.md)).

## Canonical semantics

[`review-action-authorization.md`](../../skills/github-pr-review/policies/review-action-authorization.md)
· [`review-authority.md`](../../skills/github-pr-review/policies/review-authority.md)
· [`review-output.md`](../../skills/github-pr-review/policies/review-output.md)
("Submission ordering", "Review-action authorization gate") ·
[`review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md)
· active procedure in
[`runbooks/active-pr-review.md`](../../skills/github-pr-review/runbooks/active-pr-review.md).
