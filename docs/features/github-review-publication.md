# GitHub publication & review authorization

## What it does

Controls what `github-pr-review` publishes to a PR and under what
authority. **Review analysis is always separate from GitHub mutation
authority**: the review always runs and produces a mechanically derived
verdict; whether that verdict is *submitted* to GitHub is governed by one
canonical publication mode.

| Publication mode | What gets published |
| --- | --- |
| `PASSIVE` (default) | Nothing — a report is returned to you |
| `SEMI` | Nothing to GitHub — a "would publish" preview of the exact `ACTIVE` outcome |
| `ACTIVE`, self-review | Informational `COMMENT` + one disclosure line; no formal event |
| `ACTIVE`, external, clean | `APPROVE` (needs reviewer independence + GitHub permission) |
| `ACTIVE`, external, blocking | `REQUEST_CHANGES` (needs reviewer independence + GitHub permission) |

An explicit `ACTIVE` request is, by itself, sufficient authorization to
publish that review's own outcome — there is no second activation phrase
or out-of-band signal to supply, only the unchanged self-review,
reviewer-independence, GitHub-permission, and HEAD-freshness checks.

An active review is published as **one batched submission** (body +
inline comments + event). Publication order is fixed:
`final review comment == last publication event` — any optional
machine-readable status is published *before* that submission, and
nothing review-owned is published or edited after it.

Optionally, `github-pr-review` can also publish **one stable, aggregated,
exact-HEAD machine-readable status/check** for the reviewed SHA, separate
from the native event: a blocking (non-`success`) status is blocking-only
enforcement and may be published even by a self-review; a `success`
status needs the same `ACTIVE` publication mode + reviewer independence as
`APPROVE` and is never published by a self-review; a new HEAD inherits no
green. The Skill can also report, read-only, whether that context is
`ENFORCED` / `NOT ENFORCED` / `UNKNOWN`, and — only as a separate,
explicitly requested, minimal, preserving setup action — add that one
context to a base branch's required checks.

## When it is useful

- You want a report only, with zero writes to the PR → `PASSIVE`.
- You want to see exactly what would be published — findings, body, and
  the Approve/Request Changes decision — without touching GitHub →
  `SEMI`.
- You want the Skill to actually publish its decision to GitHub → `ACTIVE`.

## Which Skill(s)

`github-pr-review` only. `local-code-review` never publishes to GitHub,
even when given a PR reference.

## Default, conditional, or requested

**Default is `PASSIVE`** — a full review and verdict with no GitHub
mutation. You never need to say "do not approve" to get safe behavior.
`SEMI` and `ACTIVE` are chosen from natural language; an explicit `ACTIVE`
request is real and immediately actionable — it is not a mere candidate
awaiting a second signal. It still requires reviewer independence
(authority separation, not merely a different GitHub username), GitHub
event permission, and a current reviewed HEAD; the self-review boundary is
absolute regardless of mode. Ambiguity fails closed to `PASSIVE` (or to a
withheld mutation when an `ACTIVE` request's independence/permission/HEAD
facts are unfavorable).

## How to invoke it

```text
just review PR #812 and tell me what you find          → PASSIVE (report only)
review #812 and tell me what would happen, but          → SEMI (preview, no
don't touch GitHub                                        publication)
review #812; approve if clean, request changes if        → ACTIVE (publishes,
there are blocking findings                                subject to the
                                                            unchanged guards)
```

For the machine-readable status / enforcement setup, ask explicitly, e.g.
*"also publish the review status check for this PR"* or *"make the
code-review status a required check on main"* (the latter is the separate
setup action).

## Limitations & safety boundaries

- **A verdict is not, by itself, a GitHub event; `APPROVE` is not merge
  authority.** This Skill never merges, never enables auto-merge, and
  never deletes branches. Maximum positive action is **Approve** / a
  `success` status.
- **Self-review is allowed; self-approval is not** — authorship (or a
  shared controlling authority: alternate account, token, bot, service
  account, GitHub App, nested agent) forbids any formal
  `APPROVE` / `REQUEST_CHANGES` on the reviewer's own work, in every
  publication mode.
- **Reviewer independence is authority separation, not a different
  username.**
- **HEAD safety** — the reviewed HEAD is revalidated immediately before
  submission; a stale HEAD is never approved, even for an otherwise
  fully-qualified `ACTIVE` request.
- **Authority boundary** — this document, and the policy it summarizes,
  governs review-publication outputs only (inline comments, review body,
  `APPROVE`/`REQUEST_CHANGES`/`COMMENT`). It never authorizes file
  modification, patch application, commit, push, merge, repository
  settings changes, or agent spawning — see this repository's canonical
  threat model
  ([`../threat-model/threat-model.md`](../threat-model/threat-model.md),
  issues #298/#301).
- The optional **isolated read-only PR checkout** used for richer context
  is a throwaway clone, never the target repo, and no target-repository
  code runs in it
  ([`repository-checkout.md`](../../skills/github-pr-review/policies/repository-checkout.md)).
- **Inline comments anchor at the fix/action location** — the line an
  author must change to resolve a finding — not merely where the problem
  is observable or where GitHub happens to allow a comment. A finding
  whose fix/action location is outside the PR diff, not inline-commentable,
  or unresolved is surfaced at review-summary level with an explicit path
  (or an explicit unresolved marker) and remediation, never attached to an
  unrelated nearby line; finding identity and deduplication are unaffected
  by where the finding is published
  ([`finding-placement.md`](../../skills/github-pr-review/policies/finding-placement.md),
  "Anchor at the fix/action location").

## Canonical semantics

[`review-action-authorization.md`](../../skills/github-pr-review/policies/review-action-authorization.md)
· [`review-authority.md`](../../skills/github-pr-review/policies/review-authority.md)
· [`review-output.md`](../../skills/github-pr-review/policies/review-output.md)
("Submission ordering", "Review-action authorization gate") ·
[`review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md)
· active procedure in
[`runbooks/active-pr-review.md`](../../skills/github-pr-review/runbooks/active-pr-review.md).
