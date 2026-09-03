# Policy — Review Status Enforcement

Governs the **optional, exact-HEAD, machine-readable GitHub review
status/check** that `github-pr-review` may publish for a reviewed PR, its
authorization split, enforcement-state detection, and the explicit opt-in
setup that makes the status a required merge check. Canonical index:
[`github-review.md`](github-review.md). This gate runs **after** the
verdict, HEAD revalidation, and the review-action authorization gate in
[`review-output.md`](review-output.md) have resolved, and adds nothing to
the verdict or to native-event authority. Its publication is placed
**before the final human-facing summary comment** — the one review
submission whose body carries that summary — so that
`final review comment == last publication event` holds and nothing this
review owns is published after the summary (see
[`review-output.md`](review-output.md), "Submission ordering"). This
ordering is the same whether or not `human_review_output` is enabled.

## Separate from native review events

Native `APPROVE` / `REQUEST_CHANGES` review events are unchanged and are
owned by
[`review-action-authorization.md`](review-action-authorization.md) and
[`review-output.md`](review-output.md), "Review-action authorization
gate." Under a base-branch rule that requires an approving review, those
native events already provide review-based merge enforcement:
`REVIEW CLEAN` → an authorized `APPROVE` may satisfy the required-review
rule; `CHANGES REQUIRED` → a permitted `REQUEST_CHANGES` blocks merge
while it stands.

The machine-readable status is an **additional, optional** signal. Its
value over native review state is a signal that is bound to **one commit
SHA**, that can represent **non-green / not-yet-reviewed** state a review
event cannot express, and that a repository may require **independently of
native approval state**. Publishing it is never a merge, never enables
auto-merge, never changes draft/ready, and never substitutes for the
native authorization gate. GitHub's own stale-review controls
(`dismiss_stale_reviews_on_push`, `require_last_push_approval`) address
part of the same "an approval must not survive a new commit" problem
without this capability; this policy does not read, set, or depend on
them.

## One stable aggregated status context

Exactly one status is published per review, under one stable aggregated
context identity (for example `code-review/github-pr-review`). The
context string is stable across invocations so republication converges on
the same status rather than accumulating variants. When review runs as
parallel workers, only the authoritative aggregator publishes it —
workers are read-only and non-authoritative, per
[`parallel-review.md`](parallel-review.md), "Aggregation and output." A
concrete mechanism (the Commit Status API or the Checks API) is an
implementation of this contract, not a canonical requirement; pick the
smallest one the available integration supports.

## Exact reviewed-HEAD binding

Every published status targets the **exact reviewed commit SHA**. A
status on SHA A is evidence about SHA A only.

```text
reviewed SHA A → status belongs only to SHA A
new SHA B      → inherits no status and no green from A
SHA B          → non-green / merge-blocked on this context until B is
                 itself reviewed clean and authorized to publish green
```

Immediately before publishing, re-read the live PR HEAD and confirm it
still equals the reviewed SHA — reuse
[`review-output.md`](review-output.md), "HEAD revalidation," and the
authorization-scope binding in
[`review-action-authorization.md`](review-action-authorization.md),
"Authorization scope (no replay)." If the live HEAD has advanced,
**withhold publication** and report `STATUS WITHHELD (HEAD advanced)`;
never retarget the reviewed result onto the new SHA, and never treat a
status on the old SHA as covering the new one.

## Verdict → status state (no second engine)

The status state is derived from the **canonical verdict already
computed** by
[`../../../shared/policies/severity.md`](../../../shared/policies/severity.md),
"Decision derivation (mechanical)." This policy introduces no second
severity or verdict path.

| Reasoning result | Status state |
|---|---|
| `REVIEW CLEAN` | `success` **candidate** — positive/unblocking, gated below |
| `CHANGES REQUIRED` | non-`success` (`failure`) — blocking |
| `REVIEW INCOMPLETE`, `JIRA CONTEXT UNRESOLVED`, repository context unavailable, or any unresolved / ungraded / errored state | non-`success` (`failure`, or the mechanism's neutral "not yet reviewed" state) — **never `success`** |
| `NO NEW DELTA` | no new publication — the existing SHA-bound status already belongs to the current HEAD |

**No false green.** A state that is not a fully clean, complete,
current-HEAD verdict never publishes `success`.

## Authorization: blocking authority vs. positive authority

Deriving the intended state is always allowed. **Publishing** it splits
by direction, reusing — never duplicating —
[`review-action-authorization.md`](review-action-authorization.md):

- **A non-`success` (blocking) status is blocking-only enforcement.** It
  may be published whenever the review is permitted to publish blocking
  enforcement — the same bar as a native `REQUEST_CHANGES` (reviewer
  independence is *not* required) — **including a self-review**, because
  it can only make the merge gate stricter and can never unlock a PR. It
  still requires GitHub write capability for the status/check and a fresh
  reviewed HEAD.
- **A `success` status is positive / unblocking authority.** It requires
  exactly what a native `APPROVE` requires: `explicitly-authorized
  auto-action` mode established by trusted mutation authorization
  (independent of the review-performing/orchestrating agent, scoped to
  this repo / PR / reviewed HEAD / action, consumed once) **and**
  reviewer independence (authority separation, not merely a different
  GitHub username).
- **A self-review must never publish a `success` status.** This is
  absolute, exactly like self-approval — no mode, natural-language
  request, or presented authorization lifts it. On a clean self-review
  the outcome is `STATUS WITHHELD (self-review: success not published)`;
  a blocking self-review may still publish the `failure` status.
- **Ambiguity fails closed.** Any doubt about mode, authorization
  provenance or scope, reviewer provenance, or whether the verdict is a
  complete current-HEAD `REVIEW CLEAN` resolves to not publishing
  `success` (a blocking status, or no publication).

```text
self-review:            CHANGES REQUIRED → may publish failure
                        REVIEW CLEAN     → no success status
authorized independent: CHANGES REQUIRED → publishes failure
review:                 REVIEW CLEAN     → publishes success
```

## Enforcement-state detection (read-only)

Independently of publishing, the Skill can report whether the aggregated
context is actually a required merge check for the PR's base branch, read
**only** — it never infers enforcement from the mere existence of a
published status:

- `ENFORCED` — the context is required by an active branch **ruleset**
  (`required_status_checks`) or by **classic branch protection** for the
  base branch.
- `NOT ENFORCED` — the configuration is readable and the context is
  absent from required checks.
- `UNKNOWN` — the configuration cannot be read (permission or API
  failure) or is ambiguous.

Inspect **both** repository rulesets and classic branch protection;
report `UNKNOWN` rather than guessing when either cannot be read.

## Explicit opt-in required-check setup

Making the status a required check is a **separate, explicitly requested
setup action**. It never happens during an ordinary review, and it is
gated by the same trusted authorization required to publish a `success`
status (it changes repository governance). Procedure:

```text
read current base-branch configuration (ruleset + classic protection)
    → normalize it
    → compute the minimal change: add this one context to required checks
    → preserve every unrelated rule, every existing required check,
      every bypass actor, the approving-review count,
      dismiss_stale_reviews_on_push, require_last_push_approval, and
      every other setting
    → apply only on explicit request
    → read the configuration back
    → verify the context is now required and nothing else changed
```

**Already required → no-op.** Never remove, replace, or reorder unrelated
required checks; never alter bypass actors, approval-count rules, or
stale-review settings — Issue #34 does not require changing them, so this
capability does not. If the configuration cannot be read first, do not
mutate.

## Idempotency

Publication and setup are upserts on a stable key:

- same reviewed SHA + same verdict → converges on the one status; only
  re-write when the state or description actually changes;
- a transport failure is safe to retry — no duplicate status, no
  progressively destructive edit;
- setup when the context is already required → no-op.

## No merge

This capability never merges a PR, never enables auto-merge, never
deletes branches, and never modifies bypass actors or unrelated
governance. Maximum positive action remains **Approve** /
`success` status.
