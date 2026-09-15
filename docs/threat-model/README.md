# Threat Model — Design Record

Repository-development design record for the canonical threat model and
adversarial-scenario catalog for `code-review-skill`'s runtime-enforced
safety boundaries: the parent epic
[#298](https://github.com/amirbena/code-review-skill/issues/298) and its
enforcement children
[#301](https://github.com/amirbena/code-review-skill/issues/301) (mutation
authority),
[#302](https://github.com/amirbena/code-review-skill/issues/302) (sandbox
runner), and
[#303](https://github.com/amirbena/code-review-skill/issues/303)
(agent-spawn / delegation).

Like [`../dependency-supply-chain/README.md`](../dependency-supply-chain/README.md),
[`../api-compatibility/README.md`](../api-compatibility/README.md), and
[`../finding-confidence/README.md`](../finding-confidence/README.md), this
is a repository-development doc: **not** packaged into either Skill
archive, and no packaged Skill resource depends on it. Unlike those three,
this design record does not feed a review-time reasoning capability in
`shared/policies/` — it is the canonical input to a family of *runtime
security architecture* issues instead
([#299](https://github.com/amirbena/code-review-skill/issues/299),
[#301](https://github.com/amirbena/code-review-skill/issues/301),
[#302](https://github.com/amirbena/code-review-skill/issues/302),
[#303](https://github.com/amirbena/code-review-skill/issues/303),
[#305](https://github.com/amirbena/code-review-skill/issues/305),
[#306](https://github.com/amirbena/code-review-skill/issues/306),
[#307](https://github.com/amirbena/code-review-skill/issues/307),
[#308](https://github.com/amirbena/code-review-skill/issues/308),
[#310](https://github.com/amirbena/code-review-skill/issues/310)).

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`threat-model.md`](threat-model.md) | Trust domains, the six adversary/failure models, security assumptions, capability-boundary architecture, and how the canonical catalog is used by dependent issues. | [#300](https://github.com/amirbena/code-review-skill/issues/300) |
| [`catalog/README.md`](catalog/README.md) | The `threat-scenario-catalog/v1` schema, the one-file-per-category catalog layout, and the `COVERAGE_GAP` / `NOT_APPLICABLE` machine-detectable gap convention. | [#300](https://github.com/amirbena/code-review-skill/issues/300) |
| [`catalog/*.yaml`](catalog/) | The 68 canonical threat scenarios themselves, one file per threat domain (`AUTH`, `SBOX`, `DELEG`, `INJECT`, `GIT`, `SCOPE`, `DOS`). | [#300](https://github.com/amirbena/code-review-skill/issues/300) |

## Related

- The parent runtime-boundary epic this threat model informs but does not
  implement: [#298](https://github.com/amirbena/code-review-skill/issues/298).
- The three enforcement owners that consume `AUTH-###` / `SBOX-###` /
  `DELEG-###` scenarios:
  [#301](https://github.com/amirbena/code-review-skill/issues/301),
  [#302](https://github.com/amirbena/code-review-skill/issues/302),
  [#303](https://github.com/amirbena/code-review-skill/issues/303).
- The denied-capability security-event taxonomy that makes this catalog's
  `expected_security_event` field authoritative:
  [#299](https://github.com/amirbena/code-review-skill/issues/299)
  ([`../security-events/security-event-model.md`](../security-events/security-event-model.md)).
- The three benchmark-fixture issues that select their category's
  scenarios from this catalog:
  [#305](https://github.com/amirbena/code-review-skill/issues/305)
  (mutation), [#306](https://github.com/amirbena/code-review-skill/issues/306)
  (sandbox), [#307](https://github.com/amirbena/code-review-skill/issues/307)
  (delegation).
- The security-event benchmark that verifies emission for applicable
  scenarios: [#308](https://github.com/amirbena/code-review-skill/issues/308).
- The end-to-end traceability engine this catalog is designed to be
  mechanically queryable by:
  [#310](https://github.com/amirbena/code-review-skill/issues/310).
- The structural validator every scenario record is checked against:
  [`../../scripts/security/validate_threat_model.py`](../../scripts/security/validate_threat_model.py).
- Review-finding severity, which threat-scenario severity is a
  deliberately distinct scale from:
  [`../../shared/policies/severity.md`](../../shared/policies/severity.md).

## Non-goals

- Implementing runtime enforcement — owned by #301/#302/#303, never
  absorbed here.
- Implementing security-event recording or emission — #299 defines the
  taxonomy only; actual emission is owned by #301/#302/#303/#308.
- Implementing benchmark fixtures — owned by #305/#306/#307/#308.
- Implementing the traceability engine — owned by #310.
- Implementing local-remediation semantics — owned by
  [#132](https://github.com/amirbena/code-review-skill/issues/132).
- Speculative AGI / existential-risk analysis, or generic
  application-security guidance unrelated to this review system.
- Redefining review findings, severity, review scope, or mutation
  semantics already owned elsewhere in `shared/policies/`.
