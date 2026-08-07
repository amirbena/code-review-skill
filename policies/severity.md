# Policy — Severity

Every actionable finding receives exactly one severity. This
classification is identical in passive and active review — see
[`review-ownership.md`](review-ownership.md) and `SKILL.md` for how
delivery mode never changes review standards.

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

- Any unresolved P0 blocks approval.
- Any unresolved blocking P1 blocks approval.
- P2 findings alone never block approval; they may coexist with Approve.
