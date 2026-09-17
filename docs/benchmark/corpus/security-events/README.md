# Denied-Capability Security-Event Benchmark

Repository-development artifact for Issue
[#308](https://github.com/amirbena/code-review-skill/issues/308), depends
on [#299](https://github.com/amirbena/code-review-skill/issues/299) (the
authoritative denied-capability security-event taxonomy,
[`../../../security-events/security-event-model.md`](../../../security-events/security-event-model.md))
and the relevant enforced denial from
[#301](https://github.com/amirbena/code-review-skill/issues/301) /
[#302](https://github.com/amirbena/code-review-skill/issues/302) /
[#303](https://github.com/amirbena/code-review-skill/issues/303).

## What this corpus proves, and what it does not

The mutation-boundary
([`../mutation-boundary/README.md`](../mutation-boundary/README.md),
#305), sandbox-adversarial
([`../sandbox-adversarial/README.md`](../sandbox-adversarial/README.md),
#306), and delegation-spawn
([`../delegation-spawn/README.md`](../delegation-spawn/README.md), #307)
corpora already prove **whether** a capability boundary denies a given
attempt. This corpus assumes that denial already happened and asks a
narrower, orthogonal question: given a real enforced denial, does the
**emitted #299 `SecurityEvent`** carry the right `event_type` and
`classification`, the right correlation fields, and — just as
important — nothing it must never carry? It never re-derives an
allow/deny decision and is not a second implementation of any capability
gate.

Per the issue's own scope: *"Do not reuse ordinary review-quality
precision/recall metrics for this corpus."* Every comparison below is a
deterministic structural assertion — event-type/classification equality,
correlation-field presence, and a redaction pattern check — never an
LLM/rubric score, exactly like the three corpora above.

## Why this isn't a `benchmark-case/v2` corpus

Like the three corpora above, this domain has no representation in
[`../../fixture-format.md`](../../fixture-format.md): that schema's
`expected` block is findings/decision-shaped and has no field for an
event schema, a classification, or a redaction assertion. This corpus
follows the same test-only, data-driven reference-fixture pattern:

- [`../../../../tests/reference/benchmark/security_event_fixtures.py`](../../../../tests/reference/benchmark/security_event_fixtures.py) —
  the `SecurityEvent` dataclass (mirroring
  [security-event-model.md](../../../security-events/security-event-model.md)
  §3's field schema field-for-field — a field is simply absent, never
  padded, when not applicable to a domain, and there is deliberately no
  field capable of holding a secret, token, credential value, raw
  prompt, or full patch body: redaction is structural, not a filter
  applied after construction), the closed `event_type` vocabulary and
  `expected_denial` / `boundary_violation_attempt` classification (both
  reused verbatim from #299, never redefined here), and one
  `SecurityEventCase` per representative enforced denial, each a
  zero-argument `build()` closure returning the event a real denial in
  that family reports.
- [`../../../../tests/unit/benchmark/test_security_event_corpus.py`](../../../../tests/unit/benchmark/test_security_event_corpus.py) —
  runs every case's `build()` and checks it against its declared
  expectation, plus corpus-completeness (every required family), a
  closed-vocabulary drift check against
  [`../../../../scripts/security/validate_threat_model.py`](../../../../scripts/security/validate_threat_model.py)'s
  `PROVISIONAL_EVENT_CLASSES`, determinism (building a case twice, or in
  reversed corpus order, is byte-for-byte identical), redaction, the
  observational-only invariant, threat-scenario/enforcement-owner
  traceability, and the malformed-fixture rejection suite.

## Family coverage

Every family the issue's "Scope" section names has at least one case
(`REQUIRED_FAMILIES` in `security_event_fixtures.py`; enforced by
`RequiredFamilyCoverageTests`):

| Family | Case(s) | `event_type` | Classification |
| --- | --- | --- | --- |
| Mutation capability missing | `SEC-EVT-001` (AUTH-001) | `DENIED_MUTATION_CAPABILITY_ABSENT` | `expected_denial` |
| Mutation stale patch | `SEC-EVT-002` (AUTH-007) | `DENIED_MUTATION_STALE_APPROVAL` | `expected_denial` |
| Mutation scope mismatch | `SEC-EVT-003` (AUTH-009) | `DENIED_MUTATION_SCOPE_ESCAPE` | `boundary_violation_attempt` |
| Commit/push authorization missing | `SEC-EVT-004` (AUTH-010), `SEC-EVT-005` (AUTH-011) | `DENIED_MUTATION_UNAUTHORIZED` | `boundary_violation_attempt` |
| Sandbox network/filesystem/credential denial | `SEC-EVT-006` (SBOX-001), `SEC-EVT-007` (SBOX-004), `SEC-EVT-008` (SBOX-005) | `DENIED_SANDBOX_NETWORK_ACCESS` / `DENIED_SANDBOX_CREDENTIAL_ACCESS` / `DENIED_SANDBOX_FILESYSTEM_ACCESS` | `boundary_violation_attempt` |
| Sandbox unavailable boundary | `SEC-EVT-009` (SBOX-012) | `DENIED_SANDBOX_UNAVAILABLE_PRIMITIVE` | `expected_denial` |
| GitHub formal-review mutation without capability | `SEC-EVT-010` (existing: review-action-authorization.md), `SEC-EVT-011` (AUTH-014) | `DENIED_REVIEW_ACTION_UNAUTHORIZED` / `DENIED_REVIEW_ACTION_SELF_REVIEW` | `expected_denial` |
| Stale HEAD / authorization replay / scope mismatch | `SEC-EVT-012` (existing: review-action-authorization.md), `SEC-EVT-013` (AUTH-012) | `DENIED_REVIEW_ACTION_STALE_HEAD` / `DENIED_MUTATION_AUTHORIZATION_REPLAY` | `expected_denial` / `boundary_violation_attempt` |
| Spawn capability absent | `SEC-EVT-014` (DELEG-001) | `DENIED_SPAWN_UNAUTHORIZED` | `expected_denial` |
| Spawn count/depth exceeded | `SEC-EVT-015` (DELEG-002), `SEC-EVT-016` (DELEG-003) | `DENIED_SPAWN_BUDGET_EXCEEDED` / `DENIED_SPAWN_DEPTH_EXCEEDED` | `boundary_violation_attempt` |
| Delegated capability escalation | `SEC-EVT-017` (DELEG-006) | `DENIED_DELEGATION_AUTHORITY_ESCALATION` | `boundary_violation_attempt` |
| Inherited/forwarded authorization across agent boundary | `SEC-EVT-018` (AUTH-013), `SEC-EVT-019` (DELEG-007) | `DENIED_MUTATION_AUTHORIZATION_REPLAY` / `DENIED_DELEGATION_REPLAY` | `boundary_violation_attempt` |

Every case's `family`, cited `AUTH-###`/`SBOX-###`/`DELEG-###` (or, when no
catalog scenario exists yet, an `existing:<policy-path>` citation) — and
`enforcement_owner` (`#301`/`#302`/`#303`, or the literal `existing`) —
live in its `SecurityEventCase` definition in `security_event_fixtures.py`;
this table is a map, not a second source of truth. `SEC-EVT-011` cites
`AUTH-014` because that scenario's sole subject is the self-review
boundary it exercises. `SEC-EVT-010` and `SEC-EVT-012` cover a different
condition in the same authority domain (publication mode not `ACTIVE`,
and a stale reviewed HEAD) that has no dedicated `AUTH-###` entry of its
own yet, so they cite
`existing:skills/github-pr-review/policies/review-action-authorization.md`
directly rather than borrowing `AUTH-014`'s id for a case it does not
describe.

## What each case asserts

Per case, `test_security_event_corpus.py` asserts:

- **deterministic `event_type`** — from the closed #299 vocabulary,
  matching the case's declared expectation, byte-for-byte identical
  across repeated `build()` calls and independent of corpus iteration
  order;
- **`expected_denial` vs. `boundary_violation_attempt` classification** —
  matching the case's declared expectation, derived per
  [security-event-model.md](../../../security-events/security-event-model.md)
  §4's rule (a case is `boundary_violation_attempt` only when a concrete
  invocation of the gated operation was actually constructed and
  submitted by an actor whose capability set could never satisfy it —
  e.g. reusing an `APPLY_PATCH` authorization as `COMMIT`, or a child
  presenting a parent's authorization — versus `expected_denial` for a
  normal fail-closed result, such as a capability that was simply never
  granted or a `PASSIVE` review that never attempted publication);
- **invocation correlation** — every event carries the same
  `invocation_id`;
- **parent/child correlation where relevant** — every spawn/delegation
  case (`requires_parent_child_correlation=True`) carries a
  `parent_agent_id` and/or `child_agent_id`; every other case carries
  neither (a family that legitimately has no cross-agent boundary must
  not fabricate one);
- **target/scope identifiers** — the fields
  [security-event-model.md](../../../security-events/security-event-model.md)
  §3 defines for the domain (e.g. `expected_scope_identifier` for a
  scope-escape case, `pr_identity`/`reviewed_head` for the GitHub domain,
  `requested_delegation` for a capability-escalation case) are present
  when the domain calls for them;
- **no raw prompt, token, secret, credential value, full patch body, or
  unnecessary repository content** — `validate_event`'s redaction check,
  plus a structural test that `SecurityEvent` has no field shaped like
  one of these in the first place;
- **findings/severity/verdict remain identical with security-event
  recording enabled vs. disabled** — `record_event` is proven, over
  every case, to return a sample `ReviewOutcome` byte-for-byte unchanged
  whether recording is enabled, disabled, or no event was produced at
  all (security-event-model.md §2, "Non-weakening invariant").

## Threat-scenario and enforcement-owner traceability

Every case cites at least one `AUTH-###`/`SBOX-###`/`DELEG-###`
threat-scenario id from
[`../../../threat-model/catalog/`](../../../threat-model/catalog/README.md)
(issue #300) and one of `#301`/`#302`/`#303` as its `enforcement_owner` —
checked by `ThreatScenarioAndEnforcementOwnerTraceabilityTests`. This
corpus does not itself change any catalog scenario's `enforcement_owner`,
`enforcement_point`, `benchmark_reference`, or `regression_evidence` —
those stay owned by #301/#302/#303/#305/#306/#307 exactly as
[security-event-model.md](../../../security-events/security-event-model.md)
§7 describes; a handful of catalog scenarios this corpus directly
exercises now also list `security-event/#308` in their `benchmark_family`
alongside their existing family, pointing at this corpus in addition to
(never instead of) the existing #305/#306/#307 reference.

## Focused selection

Run this corpus independently of the rest of the benchmark suite:

```bash
python3 -m unittest tests.unit.benchmark.test_security_event_corpus
```

exactly like every other `test_*_corpus.py` module under
[`../../../../tests/unit/benchmark/`](../../../../tests/unit/benchmark/).

## Corpus validation

`security_event_fixtures.validate_case` / `validate_event` /
`validate_corpus` reject a malformed fixture: an unrecognized
`event_type` or `classification`, an unrecognized `family`, a
threat-scenario id that does not match `<AUTH|SBOX|DELEG>-<3 digits>`, an
`enforcement_owner` that isn't `#301`/`#302`/`#303`, a corpus missing a
required family, a duplicate `case_id`, an event with an empty universal
field or a negative `sequence_position`, and an event whose field value
looks like a credential/secret or is implausibly long for a label.
`MalformedFixtureRejectionTests` in the unit-test module exercises every
one of these against deliberately broken fixtures built from
`dataclasses.replace` over a real, passing case.
