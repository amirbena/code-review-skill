# local-code-review

Review the code you have **right now** — committed, staged, unstaged, and
untracked — before it becomes a push or a PR. You get back evidence-backed
`P0` / `P1` / `P2` findings and one `REVIEW CLEAN` / `CHANGES REQUIRED`
verdict. The Skill is read-only: it never edits, commits, pushes, or
touches GitHub.

For an existing GitHub Pull Request, use the sibling
[`github-pr-review`](../github-pr-review/SKILL.md) Skill instead.
[`../../docs/CODE_REVIEW_COMPARISON.md`](../../docs/CODE_REVIEW_COMPARISON.md)
explains why this Skill exists alongside native and third-party reviewers.

## When to use it

- Right before `git push` or opening a PR — a last check on the full
  local delta, not just `HEAD`.
- After applying review fixes locally, to confirm they hold (re-review
  needs its own approval — see below).
- When you want the change checked against a ticket, an ADR, or
  acceptance criteria you can paste in.

## How to invoke it

Ask for it in plain language — there is no required syntax:

```text
review my local changes before I push
run a local code review of the current diff
review the working tree against BILLPAY-1234's acceptance criteria
```

Optionally attach context to focus the review (all optional, any
combination):

```text
/local-code-review

Context: Jira BILLPAY-1234
Acceptance criteria:
- reject unsupported CC + RTP combinations
- validation must run before execution
```

- **Review context** — free-form requirements, a pasted ticket/Issue, an
  HLD/ADR, an implementation plan, or a bare Jira key (resolved read-only
  before the review). It focuses attention and enables scope-boundary
  reasoning; it never overrides the actual code and never widens the
  review beyond the current delta.
- **PR reference** — an associated PR whose prior findings and settled
  decisions are reconciled against your local delta, so the review does
  not re-litigate what a reviewer already settled.
- **`include_fix_prompt`** (default off) — when on, qualifying findings
  append a coding-agent-ready implementation prompt. Output only; nothing
  else changes.

A plain request with no context is fully supported and behaves exactly
as before these inputs existed.

## What a review looks like

```markdown
## Code Review

**Result: ⚠️ Changes Requested**

Not safe to proceed: the retry path can double-process a payment.

### Findings

#### F1 [P1] Retry can duplicate processing
- **Location:** `src/pay/execute.py:88` _(staged)_
- **Evidence:** the handler re-enters `charge()` on timeout without an
  idempotency key.
- **Impact:** a retried webhook charges the customer twice.
- **Fix:** key the charge on the payment intent id and no-op on repeat.

### Decision
**CHANGES REQUIRED**
```

A clean review is just the result line, an optional one-line change
summary, validation, and `REVIEW CLEAN`. Machine detail (SHAs,
per-category scope, counts) sits in a trailing metadata block.

## Boundaries worth knowing

| Rule | Short version |
| --- | --- |
| **Opt-in only** | Never runs automatically. Every review *and* every re-review needs fresh, explicit approval for that run. |
| **Read-only** | No edits, patches, commits, pushes, branches, PRs, or GitHub writes — ever. |
| **Severity → verdict** | `P0`/`P1` block; `P2` never does. The verdict is derived mechanically, not by judgment. |
| **One owner per scope** | If another Code Review Agent owns this branch, it returns `REVIEW ALREADY OWNED`. |
| **Scope stays local** | A Jira ticket or PR reference focuses the review; it never expands it past the current local delta. |

These are summaries. The binding text lives in
[`SKILL.md`](SKILL.md) and the canonical policies it links —
[`policies/invocation-approval.md`](policies/invocation-approval.md),
[`../../shared/policies/severity.md`](../../shared/policies/severity.md),
[`../../shared/policies/review-ownership.md`](../../shared/policies/review-ownership.md).

## Deeper documentation

- [`SKILL.md`](SKILL.md) — the execution entry contract
- [`runbooks/local-review.md`](runbooks/local-review.md) — the full
  numbered procedure
- [`policies/`](policies/repository-state.md) — the rules this Skill owns
  (invocation approval, repository-state categories, optional review
  context, optional PR context)
- [`templates/local-review-report.md`](templates/local-review-report.md)
  — the output contract
- [`../../shared/policies/`](../../shared/policies/review-scope.md) — the
  review standard shared with `github-pr-review`

## Development

```bash
python3 scripts/validate-skill-metadata.py skills/local-code-review --containment-root .
./scripts/package-skills.sh local     # -> dist/local-code-review-skill.zip
python3 -m unittest discover -s tests -t .
```

PowerShell packaging: `./scripts/package-skills.ps1 local`.

This README is onboarding documentation only. It carries no normative
authority — [`SKILL.md`](SKILL.md), this Skill's `policies/`, its runbook,
and the shared policies do.
