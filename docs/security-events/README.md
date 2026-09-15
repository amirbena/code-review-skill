# Security Events — Denied Capability-Boundary Taxonomy

Repository-development design record for the **authoritative, closed
taxonomy of denied capability-boundary events**: the stable event names a
reviewer runtime reports when execution attempts a capability use that a
runtime capability boundary denies, the minimum evidence each event
carries, and the deterministic classification that distinguishes ordinary
fail-closed behavior from an actual boundary-violation attempt.

Like [`../finding-confidence/README.md`](../finding-confidence/README.md),
[`../review-context/README.md`](../review-context/README.md), and
[`../threat-model/README.md`](../threat-model/README.md), this is a
repository-development doc: **not** packaged into either Skill archive,
and no packaged Skill resource depends on it. It is an explanatory /
design record — the normative rule lives in the file named for it, and
each packaged policy that reports a denied-capability event references
this document by name (never by link) plus a caveat that it is
non-packaged.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`security-event-model.md`](security-event-model.md) | The closed set of denied-capability event names across every capability-boundary domain (mutation, sandbox, agent-spawn/delegation, GitHub review-action), the event field schema, the two-value classification (`expected_denial` / `boundary_violation_attempt`) and its deterministic derivation rule, and what an event must never record. | [#299](https://github.com/amirbena/code-review-skill/issues/299) |

## Relationship to the threat-model catalog

[`../threat-model/catalog/README.md`](../threat-model/catalog/README.md)'s
`expected_security_event` field on every `AUTH-###` / `SBOX-###` /
`DELEG-###` scenario previously drew from a **provisional** vocabulary
declared directly in
[`../../scripts/security/validate_threat_model.py`](../../scripts/security/validate_threat_model.py)
(`PROVISIONAL_EVENT_CLASSES`), pending this issue. This document is the
authoritative source those names now point back to: the validator's
vocabulary is the machine-checkable mirror of the closed set defined here,
not a second, independent taxonomy.

## Non-goals

- Emitting, transporting, storing, or querying a real event — owned by the
  runtime capability-enforcement issues
  ([#301](https://github.com/amirbena/code-review-skill/issues/301) /
  [#302](https://github.com/amirbena/code-review-skill/issues/302) /
  [#303](https://github.com/amirbena/code-review-skill/issues/303)) and
  their benchmark coverage
  ([#308](https://github.com/amirbena/code-review-skill/issues/308)).
  This document defines the vocabulary and shape those issues report
  against; it ships no emitter, sink, or query surface.
- Changing findings, severity, suppression, review depth, or the
  `REVIEW CLEAN` / `CHANGES REQUIRED` (or `Approve` / `Request Changes`)
  decision — see
  [`../../shared/policies/severity.md`](../../shared/policies/severity.md)
  and [`../../shared/policies/review-scope.md`](../../shared/policies/review-scope.md).
  A security event is observability only.
- Defining or weakening any capability boundary itself — owned by
  [`../../shared/policies/mutation-authority.md`](../../shared/policies/mutation-authority.md),
  [`../../shared/policies/agent-delegation.md`](../../shared/policies/agent-delegation.md),
  [`../../shared/policies/runtime-validation.md`](../../shared/policies/runtime-validation.md),
  and `github-pr-review`'s
  [`review-action-authorization.md`](../../skills/github-pr-review/policies/review-action-authorization.md).
  This document names what those boundaries report when they deny an
  attempt; it never changes when they deny one.

## Related

- The full model: [`security-event-model.md`](security-event-model.md).
- The threat-scenario catalog whose `expected_security_event` field this
  model makes authoritative:
  [`../threat-model/catalog/README.md`](../threat-model/catalog/README.md).
- The trust-domain architecture: [`../threat-model/threat-model.md`](../threat-model/threat-model.md).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
