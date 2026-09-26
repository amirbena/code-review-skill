# GitHub Review Status — Implementation Recommendation

Consolidation note for GitHub Issue
[#95](https://github.com/amirbena/code-review-skill/issues/95) (parent Epic
#49). It is the single design basis for
[`review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md)
(#34 / PR #112), tying together the mechanism research (#91), the
ruleset-vs-branch-protection research (#93), and the mapping and failure
behavior already shipped by #92 / #94.

This is a recommendation record, not a policy. It adds no capability and
re-researches nothing; the canonical policy wins any conflict.

## Recommendation in brief

| Decision | Recommendation | Detail |
| --- | --- | --- |
| Publishing mechanism | Commit Status API by default; Checks API only under a future GitHub App integration | [#91 research](../github-review-status-mechanism-research.md) |
| Detection of enforcement | Read the branch-rules endpoint and classic required status checks; `ENFORCED` if either lists the context, `UNKNOWN` if either read fails | [#93 research](ruleset-vs-branch-protection-research.md) |
| Opt-in setup target | The mechanism already governing the branch; never create the other one unprompted | [#93 research](ruleset-vs-branch-protection-research.md) |
| Verdict → status mapping, stale/failure behavior, authorization, idempotency | Already codified; referenced, not restated | [Policy](../../skills/github-pr-review/policies/review-status-enforcement.md) |

## Mechanism (#91)

Use the **Commit Status API** (`POST /repos/{owner}/{repo}/statuses/{sha}`).
It meets every need of the policy — one stable context, SHA binding,
in-place upsert, a non-success `pending` state, read-back, and use as a
required check — under ordinary `gh` / `gh api` token auth (fine-grained
**Commit statuses: write**, or classic `repo:status`). The Checks API's
extras (annotations, actions) are unused by the policy, and its write path
is restricted to GitHub Apps, which would make the capability unusable for
the default `gh`-driven runtime. Revisit the Checks API only when a
repository needs source pinning to a specific App. Keep the context string
unique to this Skill and use one mechanism per repository to avoid
ambiguous required-check results. Full comparison, permissions, and caveats:
[`github-review-status-mechanism-research.md`](../github-review-status-mechanism-research.md).

## Rulesets vs. branch protection (#93)

Both can require a named status context; they run in parallel with no
precedence, so a context is enforced if **either** requires it.
Consequently:

1. **Detect** through both: the rules-for-branch endpoint (aggregates all
   applicable rulesets) and classic `required_status_checks`. `ENFORCED` if
   either lists the context; `NOT ENFORCED` only when both were readable and
   neither does; otherwise `UNKNOWN`.
2. **Set up** on the mechanism already governing the branch: edit the
   ruleset if one requires status checks (a full read-normalize-diff-verify
   write, since rulesets have no per-context add), or use additive
   `POST .../contexts` under classic protection. Do not introduce the other
   mechanism without an explicit request, and report the other's state.
3. **Pin the source** (`integration_id` / `app_id`) where the publisher is
   known.

Migration and compatibility notes, plus the items still marked *unverified*
(per-endpoint ruleset permissions; org-level rulesets appearing in the
branch-rules endpoint), stay in
[`ruleset-vs-branch-protection-research.md`](ruleset-vs-branch-protection-research.md).

## Already shipped (#92 / #94) — referenced, not restated

The verdict → status mapping, exact reviewed-HEAD binding, stale-HEAD
withholding (`STATUS WITHHELD (HEAD advanced)`), failure and
non-publication behavior, the blocking-vs-positive authorization split,
enforcement-state detection, opt-in setup safety, and idempotency are
owned by
[`review-status-enforcement.md`](../../skills/github-pr-review/policies/review-status-enforcement.md).
Read them there.

## Review decision vs. merge enforcement

This boundary is stated once here, consistent with the policy's "Separate
from native review events" and "No merge" sections and with
[`github-review-publication.md`](../features/github-review-publication.md):

- **Review decision** is the Skill's output: a verdict, and — when
  authorized — a native `APPROVE` / `REQUEST_CHANGES` event and/or an
  aggregated status bound to the exact reviewed SHA. Maximum positive action
  is an approval or a `success` status.
- **Merge enforcement** belongs to the repository: required reviews,
  required status checks, and rulesets or branch protection decide whether a
  merge is possible. The Skill only **detects** that state (read-only) and,
  on an explicit user request, may add the context as a required check.
- The Skill never merges, never enables auto-merge, never changes
  draft/ready, never deletes branches, and never treats a published status
  as merge authority. A status on SHA A says nothing about SHA B.
- Self-approval stays forbidden in every mode; blocking signals are always
  permitted, positive ones need an independent, authorized reviewer.
