# github-pr-review

Review an existing GitHub Pull Request the way a strong senior reviewer
would: repository-aware reasoning, evidence-backed `P0` / `P1` / `P2`
findings, and one clear verdict. **Passively** it returns a report;
**actively**, with authenticated GitHub access, it publishes inline
comments and one consolidated review, and — only under independently
trusted authorization — submits Approve / Request Changes.

For local changes that aren't a PR yet, use the sibling
[`local-code-review`](../local-code-review/SKILL.md) Skill.
[`../../docs/CODE_REVIEW_COMPARISON.md`](../../docs/CODE_REVIEW_COMPARISON.md)
explains where each fits.

## When to use it

- Review someone's open PR by URL or number — passively as a report, or
  actively with published comments.
- Re-review after a push — same reviewer + a reliable previous SHA gives
  a bounded [delta re-review](../../docs/features/delta-re-review.md)
  (`NO NEW DELTA` when nothing changed); otherwise a full review.
- Review **your own** PR — analysis always runs; a self-review just never
  submits a formal `APPROVE` / `REQUEST_CHANGES` (see boundaries below).

## How to invoke it

Plain language; the phrasing you use also sets how far it may go:

```text
review PR https://github.com/acme/app/pull/812
just review PR #812 and tell me what you find        → report only
review #812; block it if there are serious issues     → may Request Changes
review #812 and approve it if it's clean              → Approve only if
                                                        independently authorized
```

Optional add-ons, each with a usage guide under `docs/features/`:
attach [review context](../../docs/features/review-context.md) (a ticket,
Issue, ADR, plan, or a Jira key resolved read-only) to focus the review
without widening the PR delta; ask for
[human-style output](../../docs/features/human-review-output.md) ("review
it like a senior engineer") for a concise summary. Runtime validation
evidence and parallel review apply automatically when the repository and
runtime support them.

## What a review looks like

```markdown
## Code Review

**Result: ⚠️ CHANGES REQUIRED**

Not safe to merge at `a1b2c3d` yet; see the inline comments for detail.

### Findings

- **P1 — Pagination can stop after page one and pass a false clean review**
  `src/reviews/scan.py:84`
- **P2 — Validation output hides the failing check name**
  `scripts/validate.py:117`

### Decision
**REQUEST CHANGES**
```

A clean review is just the result line and `APPROVE`. The body never
repeats a finding's detail when it already has an inline comment;
machine/process state sits in a trailing `<details>` block.

## Boundaries worth knowing

| Rule | Short version |
| --- | --- |
| **Analysis ≠ mutation authority** | The verdict always exists; submitting it to GitHub is a separate, authorized step. Default: `recommendation-only`, no GitHub mutation. |
| **Self-review ≠ self-approval** | Analysis always runs; no formal event on your own work; an informational `COMMENT` instead. A shared controlling authority (alternate account, token, bot, GitHub App, nested agent) counts as self-review. |
| **Independence is authority, not username** | A different login under the author's controlling authority is the same reviewer. |
| **Trusted authorization** | `APPROVE` / a `success` status needs a signal from a principal independent of the reviewing agent, scoped to this PR + HEAD + action. A flag, prompt, or "approve if clean" text never counts; ambiguity fails closed. |
| **HEAD safety** | The reviewed HEAD is revalidated before the decision; a stale HEAD is never approved; authorization is bound to the exact HEAD. |
| **Severity → verdict** | `P0`/`P1` block; `P2` never does; derived mechanically. |
| **One owner per scope** | Another Code Review Agent already on this PR ⇒ `REVIEW ALREADY OWNED`. |
| **Never merges** | Maximum positive action is **Approve** / an optional exact-HEAD machine-readable `success` status; branch protection is untouched except one opt-in required-check setup. |

Full walkthrough of passive vs. active, the modes, self-review, and the
machine-readable status/check:
[`docs/features/github-review-publication.md`](../../docs/features/github-review-publication.md).

## Deeper documentation

- [`SKILL.md`](SKILL.md) — the execution entry contract
- Feature guides under `docs/features/` — how to use the optional
  capabilities:
  [review context](../../docs/features/review-context.md),
  [runtime validation](../../docs/features/runtime-validation.md),
  [parallel review](../../docs/features/parallel-review.md),
  [human-style output](../../docs/features/human-review-output.md),
  [delta re-review](../../docs/features/delta-re-review.md),
  [GitHub publication & authorization](../../docs/features/github-review-publication.md)
- [`policies/github-review.md`](policies/github-review.md) — the canonical
  policy index (identity, authorization, delta re-review, PR scope,
  repository checkout, context, evidence, reasoning, parallelism,
  placement, output, status enforcement)
- [`runbooks/passive-pr-review.md`](runbooks/passive-pr-review.md) /
  [`runbooks/active-pr-review.md`](runbooks/active-pr-review.md) — the
  full procedures
- [`templates/`](templates/external-review-summary.md) — the review body
  and inline-comment output contracts
- [`../../shared/policies/`](../../shared/policies/severity.md) — the
  review standard shared with `local-code-review`

## Development

```bash
python3 scripts/validate-skill-metadata.py skills/github-pr-review --containment-root .
./scripts/package-skills.sh github     # -> dist/github-pr-review-skill.zip
python3 -m unittest discover -s tests -t .
```

PowerShell packaging: `./scripts/package-skills.ps1 github`.

This README is onboarding documentation only. It carries no normative
authority — [`SKILL.md`](SKILL.md), the `policies/`, and the shared
policies do.
