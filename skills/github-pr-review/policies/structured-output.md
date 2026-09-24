# Policy — Structured Output

Canonical semantics for the optional machine-readable review result
`github-pr-review` can return to its caller. Canonical index:
[`github-review.md`](github-review.md), which places this file after
[`reviewer-brief.md`](reviewer-brief.md): the document is a projection of
the same finalized analysis result and is composed only once findings,
severity, coverage, and the verdict are final.

The document is the same review-result document `local-code-review` emits:
identical field names, enums, and meaning. The shape is stated in
"Document shape" below so it is usable from the packaged Skill alone (this
repository's `docs/review-result/` holds the JSON Schema it mirrors; it is
not packaged). Beyond that shape, this policy states only what is specific
to a pull request — which values populate the PR-shaped fields — and
defines no finding, severity, or decision rule of its own.

## What it is not

- **Not a GitHub status or check.** A pass/fail commit status for the
  reviewed SHA is a different mechanism, owned by
  [`review-status-enforcement.md`](review-status-enforcement.md). Emitting
  this document never publishes, alters, or substitutes for that status.
- **Not a review body or inline comment.** It is returned to the caller
  only and is never an input to the publication payload built by
  [`review-output.md`](review-output.md), "Batched review construction and
  submission" — the same structural boundary as the Reviewer Brief.
- **Not a new analysis phase.** Composing it changes no finding, severity,
  coverage signal, or verdict, and it runs in every publication mode
  (PASSIVE, SEMI, ACTIVE), whether or not anything is published.

## Activation

Off by default. Emitted only when the caller explicitly asks for a
machine-readable, structured, or JSON review result (for example "also
return the review as JSON"). It is additive: the human-readable report,
the Reviewer Brief, and any publication are unchanged.

## Document shape

One JSON object. Keys are `snake_case`; required keys are always present;
an optional finding field with no value is omitted, never `null`.

```json
{
  "schema_version": "1.0.0",
  "skill": "github-pr-review",
  "reviewed_state": {
    "repository": "owner/name", "base_branch": "main",
    "base_sha": "<sha|null>", "merge_base_sha": "<sha|null>",
    "reviewed_head_sha": "<sha|null>", "reviewer_identity": "<string|null>",
    "completeness": "full | delta-re-review", "prior_reviewed_sha": "<sha|null>"
  },
  "coverage": "complete | incomplete",
  "decision": { "derived": "clean | blocking",
                "outcome": "clean | blocking | incomplete" },
  "counts": { "p0": 0, "p1": 0, "p2": 0 },
  "summary": "<the review's What changed prose>",
  "findings": [ { "id": "F1", "severity": "P0 | P1 | P2", "title": "",
    "location": "", "fix_location_resolved": true, "evidence": "",
    "impact": "", "fix": "",
    "runtime_validation": "reasoned | runtime-confirmed | attempted-inconclusive",
    "confidence": "confirmed | credible | runtime-validation-unavailable | external-contract-unvalidated | insufficient-context",
    "identity": { "stable_id": "fid_v1_<hex>", "matching_eligible": true } } ]
}
```

Optional finding fields, each from [`finding.md`](../../../shared/templates/finding.md)
and omitted when empty: `evidence_location`, `affected_locations`,
`follow_up`, `details`, `contextual_evidence`, `capability`, `defect_kind`.
`fix_location_resolved` is `false` exactly when the finding carries the
"evidence location; fix/action location unresolved" annotation. `counts`
equals the tally of `findings` by severity; no other key is permitted.

## Field population

Shared fields (`schema_version`, `findings`, `counts`, `coverage`,
`summary`, and each finding's fields) are populated exactly as
`local-code-review` populates them, from the finalized findings and the
shared [`finding.md`](../../../shared/templates/finding.md) contract. The
PR-specific values are:

| Field | Value for a PR review |
| --- | --- |
| `skill` | `github-pr-review` |
| `reviewed_state.repository` | the PR's base repository as `owner/name` |
| `reviewed_state.base_branch` | the PR's base branch name (the effective review base for a stacked PR) |
| `reviewed_state.base_sha` | the base SHA at review time |
| `reviewed_state.merge_base_sha` | the merge base of base and head at review time |
| `reviewed_state.reviewed_head_sha` | the exact PR head SHA the review analyzed and revalidated ([`review-output.md`](review-output.md), "HEAD revalidation") — never the current tip if it moved afterward |
| `reviewed_state.reviewer_identity` | the authenticated review identity, or `null` when it could not be established |
| `reviewed_state.completeness` | `full`, or `delta-re-review` when [`reviewer-delta-review.md`](reviewer-delta-review.md) applied |
| `reviewed_state.prior_reviewed_sha` | the same-reviewer prior reviewed SHA a delta review superseded; `null` at a chain root |
| `decision.derived` | mechanically derived from the finding set: `blocking` when any unresolved P0/P1 remains, otherwise `clean` |
| `decision.outcome` | `derived`, except `incomplete` when coverage is incomplete |

If the head cannot be established the review is incomplete: emit
`coverage: incomplete`, `decision.outcome: incomplete`, and
`reviewed_head_sha: null` — never a graded outcome.

### Decision consistency

`decision.derived` and `decision.outcome` are computed from the same final
verdict the human output states, never separately:

| Machine value | Human rendering |
| --- | --- |
| `clean` | `Approve` (permitted or not — see below) |
| `blocking` | `Request Changes` |
| `incomplete` (outcome only) | `REVIEW INCOMPLETE` |

The document records the derived decision, not the GitHub event that was
submitted. A self-review, a PASSIVE run, or an unauthorized `APPROVE`
still yields `clean` when the findings are clean; the event actually
posted is reported by the human output, not encoded here. `clean` never
means "no findings" — P2 findings still appear in `findings`.

## Delivery

One JSON document in a fenced `json` block, in a distinct part of the
returned result appended after the caller-facing report, never merged into
GitHub-shaped content. The final human-facing summary remains the last
review-owned publication of an active run
([`review-output.md`](review-output.md), "Submission ordering"); this
document is returned to the caller, not published, so it does not change
that ordering.
