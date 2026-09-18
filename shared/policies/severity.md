# Shared Policy — Severity

Every actionable finding, in either Skill, receives exactly one severity.
This classification is identical in `local-code-review` and
`github-pr-review`, and identical across passive and active delivery
within `github-pr-review` — see [`review-ownership.md`](review-ownership.md)
for the related one-owner-per-scope invariant. Delivery mode never
changes review standards, and neither does which Skill is invoking this
policy.

## P0 — Critical / Blocking

Unsafe to merge. Examples: a serious security vulnerability, destructive
data loss, a critical correctness failure, dangerous infrastructure
behavior, a broken production-critical flow.

P0 should be rare and strongly evidence-backed (see
[`evidence.md`](evidence.md)).

## P1 — Significant / Blocking

Should normally be corrected before approval. Examples: a functional bug,
a meaningful regression, a concurrency problem, a reliability defect, a
contract violation, an unsafe edge case, an important missing test around
changed behavior.

## P2 — Non-Blocking

A valid engineering improvement that does not independently block
approval. Examples: a maintainability issue, a localized design weakness,
avoidable complexity, a lower-risk test gap, a documentation
inconsistency, a non-critical reliability improvement.

**P2 must not be used for cosmetic noise** (formatting preferences, purely
stylistic taste with no engineering cost).

## Blocking rule

- Any unresolved P0 blocks a clean/approved result.
- Any unresolved blocking P1 blocks a clean/approved result.
- P2 findings alone never block a clean/approved result; they may
  coexist with `REVIEW CLEAN` (local) or `Approve` (GitHub).

## Decision derivation (mechanical)

The formal review decision is derived mechanically from the severities
already assigned above — it is never a separate, independent judgment
call that can contradict that derivation:

```text
blocking_findings = { f in findings : severity(f) in {P0, P1} }

blocking_findings is empty      → clean/approved decision
                                    (`REVIEW CLEAN` local, `Approve` GitHub)
blocking_findings is non-empty  → blocking decision
                                    (`CHANGES REQUIRED` local,
                                     `Request Changes` GitHub)
```

Deriving this is an explicit tally, not an impression. Before rendering
any decision, enumerate the finalized finding set by severity and state
the resulting count — for example "P0: 0, P1: 0" or "P0: 0, P1: 1" — as
the concrete basis for `blocking_findings` above. Only the P0 count and
the P1 count feed this tally; the P2 count and the total number of
findings are never inputs to it, no matter how large either is.
Inferring the decision instead from how the finding set reads overall,
how strongly a finding is worded, or how many findings exist in total —
without performing this tally — is exactly the failure mode this
derivation forbids, even in a case where the reviewer believes the
tally would land on the same result anyway: the tally is the derivation,
not a check on top of it.

There is no reviewer discretion in this step. A P2 finding — no matter
how strongly it is recommended, how many P2 findings exist, or where it
originated (a repository convention, reconciled PR context, supplied
review context, or the reviewer's own judgment) — never by itself
produces a blocking decision. A strong recommendation belongs in that
finding's own Impact/Fix text; it never substitutes
for, or overrides, severity when the decision is derived. Conversely, a
finding that actually warrants blocking must be classified P0 or P1
under the definitions above — the fix for "this should really block" is
to assign the correct severity, never to make the decision diverge from
the severity it was actually given.

This derivation runs exactly once per invocation, after the finding set
is finalized, and produces exactly one decision value. Every place that
value appears in a published report or review — a summary `Result` label,
a later `Decision` section, or any other rendering — presents that same
single value; none of them re-derives it independently. A report must
never show a provisional decision that is later superseded, correction
prose explaining that an earlier rendered decision was wrong, or two
`Result`/`Decision` renderings that disagree with each other. If a
decision needs to change, that means the finding set was not actually
finalized yet — finalize it first, per
[`evidence.md`](evidence.md) and the consuming Skill's own runbook
(finalize findings → derive decision → compose the report, in that
order, once), and only then derive and render the decision.

This derivation assumes the review that produced the finding set actually
reached complete coverage. When it did not, per
[`review-stopping-criteria.md`](review-stopping-criteria.md), the
review's rendered primary outcome is the incomplete state instead of the
clean/blocking value this derivation would otherwise produce — that
policy owns the coverage definition and the incomplete label, and this
derivation is not restated or bypassed by it: findings are still
classified and this mechanical derivation still runs exactly as above,
it is only the top-level rendered outcome that the coverage state can
override.

## Repository conventions and severity

A target repository's own instructions (`AGENTS.md`, `CLAUDE.md`, or
other repository-local convention — see
[`repository-instructions.md`](repository-instructions.md)) may
legitimately make something a finding. They never, by themselves,
determine that finding's severity or blocking status. A
repository-convention finding is classified under the P0/P1/P2
definitions above using exactly the same standard as any other finding:
it blocks only when it independently meets the P0 or P1 bar (an actual
correctness, security, reliability, or contract defect), never merely
because it originates from a stated repository convention or is phrased
emphatically ("must", "never", "always"). A style or convention finding
with no such independent defect is P2, and P2 alone never blocks per the
rule above — regardless of how firmly the source repository states the
convention.

This is the single canonical severity model. Neither Skill defines its
own copy — both reference this file.

## Relationship to candidate-finding validation

Whether a candidate claim clears the P0/P1 bar above (a violated
contract/invariant plus a concrete failure condition plus a causal
connection plus material impact) versus keeps its finding but downgrades —
`claim_valid = true, blocking_justification_valid = false` — is upstream
reasoning owned by the candidate-finding validation model (a
repository-development document, not a packaged resource, so it is named
here, not linked). That model never overrides this file's P0/P1/P2
definitions or the mechanical decision derivation above; it only decides
which classification a candidate has earned before this file's derivation
runs.

## Relationship to review-base-policy.md

A change under review targeting an integration base that reliably violates
the target repository's own review-base policy is classified P0 under
"P0 — Critical / Blocking" above. The repository-relative resolution of
that base, the fail-closed rule for an unresolved base, and the
requirement that this finding enters the finding set before
implementation-focused findings are owned by
[`review-base-policy.md`](review-base-policy.md) and are not restated
here. It introduces no new severity tier and does not change this file's
mechanical decision derivation, which still runs exactly once, over the
complete finalized finding set, including this finding like any other.
