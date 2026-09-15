# Security Event Model — Denied Capability-Boundary Taxonomy

Repository-development design record (Issue #299). Defines the
authoritative, closed vocabulary of **denied capability-boundary
events**: what a reviewer runtime reports whenever review execution
attempts a capability use that a runtime capability boundary denies. This
document is descriptive of the boundaries
[`mutation-authority.md`](../../shared/policies/mutation-authority.md),
[`agent-delegation.md`](../../shared/policies/agent-delegation.md),
[`runtime-validation.md`](../../shared/policies/runtime-validation.md),
and `github-pr-review`'s
[`review-action-authorization.md`](../../skills/github-pr-review/policies/review-action-authorization.md)
already define and enforce; it never defines or weakens a boundary
itself, and it never introduces a capability, a gate, or a new way for a
capability to be granted.

## 1. Purpose

Once a capability boundary is enforced, the system still needs visibility
into attempted boundary crossings so a maintainer can distinguish
ordinary fail-closed behavior from a suspicious or repeated attempt to
exceed authority. This is a **security-event model**, not:

- [#182](https://github.com/amirbena/code-review-skill/issues/182)'s
  execution telemetry — what a review inspected and executed;
- [#131](https://github.com/amirbena/code-review-skill/issues/131)'s
  analytics — review outcomes and quality metrics.

A denied-capability event is emitted only when a capability boundary
actually refuses something. It is forensic and observational only.

## 2. Non-weakening invariant (load-bearing)

A security event **never**:

- changes which findings exist, their severity, their suppression, or the
  review depth;
- changes the mechanical `REVIEW CLEAN` / `CHANGES REQUIRED` (or
  `Approve` / `Request Changes`) decision;
- grants, widens, or substitutes for any capability;
- becomes, by its own existence, a reason to deny or allow a *later,
  unrelated* action (an event is a record of what already happened, not
  an input to a future capability check).

Recording an event is strictly additive to the capability boundary's own
existing behavior. If a boundary would deny an attempt with no event
model at all, it denies the attempt identically with one; the model only
adds a structured record of that denial.

## 3. Event field schema

Every denied-capability event carries only the fields below. A field is
included only when applicable to the domain; none is ever inferred or
padded when not applicable.

| Field | Meaning |
| --- | --- |
| `event_type` | One of the closed set in §5 below. Stable — never a free-form string. |
| `classification` | `expected_denial` or `boundary_violation_attempt` — see §4. |
| `invocation_id` | The correlation id for this review/runtime invocation. |
| `parent_agent_id` / `child_agent_id` | When the denial occurs across, or because of, an agent-spawn boundary — see [`agent-delegation.md`](../../shared/policies/agent-delegation.md). |
| `repository` / `pr_identity` | When applicable — the target repository, and PR identity for `github-pr-review`. |
| `reviewed_head` / `working_tree_base` | The reviewed HEAD or working-tree base state relevant to the denied attempt, when applicable. |
| `approved_patch_digest` / `expected_scope_identifier` | The digest or scope the denied attempt was checked against, when the domain is patch-shaped (`APPLY_PATCH` / `COMMIT` / `PUSH`). |
| `requested_capability` | The capability or action that was requested (e.g. `APPLY_PATCH`, `COMMIT`, `PUSH`, `spawn_agent`, `APPROVE`, a sandbox primitive name). |
| `requested_delegation` | The capability set a child requested from a parent, when the domain is agent-spawn/delegation. |
| `denial_reason` | A short, stable, human-readable reason — not a substitute for `event_type`. |
| `boundary` | The named gate/policy that denied it (e.g. `mutation-authority.md`, `runtime-validation.md`, `agent-delegation.md`, `review-action-authorization.md`). |
| `timestamp` / `sequence_position` | When the denial occurred, and its position in the invocation's event sequence. |

### What an event must never record

Per the issue's own scope, an event never carries: secrets, tokens,
credential values, repository file contents, raw prompts, full patch
bodies, or any user data beyond the minimum identifiers above. A
`requested_capability` or `denial_reason` value is a short, closed-set-or-
stable-phrase label, never a dump of the attempted payload.

## 4. Classification: expected denial vs. boundary-violation attempt

Two classes, both closed, both **required** on every event:

1. **`expected_denial`** — a normal fail-closed result: execution simply
   never advanced past a gate, because the capability or precondition it
   would have needed was never sought, never granted, or structurally
   unavailable before any attempt could even be made. Examples: runtime
   validation stays `unavailable` because no safe sandbox boundary
   exists; a reviewer stays at `READ_ONLY` because no `PROPOSE_PATCH` was
   ever advanced past advisory text; a `PASSIVE` review never attempts
   GitHub publication at all.
2. **`boundary_violation_attempt`** — execution actively constructed and
   submitted a concrete invocation of a gated operation (a tool call, a
   Git/GitHub API call, a spawn call, a network syscall) that this
   actor's capability set could never have satisfied — a structurally
   absent capability, a replayed or foreign-invocation authorization, a
   scope escape, a request over a hard budget/depth limit, or an
   authority-escalation attempt across an agent-spawn boundary. Examples:
   network access from a network-denied validation container; an
   `APPROVE` submission attempt with no reviewer-independence
   established; a spawned child attempting `APPLY_PATCH` using its
   parent's authorization; a child requesting a capability outside its
   explicit delegation.

### Deterministic derivation rule

Classification is derived from **runtime evidence only**, never from
inferred model intent, per this rule:

```text
classification = boundary_violation_attempt
    iff BOTH:
      (a) a concrete invocation of the gated operation was constructed
          and submitted to the enforcement point — not merely a
          proposal, advisory text, or a plan that was never acted on;
      (b) the acting agent's capability set, at invocation time, could
          never have satisfied the request under any pending step of the
          ordinary flow (the capability is outside the closed set, the
          presented authorization does not and could never cover this
          exact action/scope/invocation, the authorization was already
          consumed or belongs to a different invocation, or a hard
          budget/depth ceiling was exceeded).

classification = expected_denial
    otherwise — including every case where no invocation was ever
    attempted, or where the actor is legitimately mid-flow toward a
    capability that a later, different step could still grant (e.g. a
    proposed patch correctly waiting for `USER_APPROVES_EXACT_PATCH`
    is not, by itself, a denial at all — it is not an attempt of
    `APPLY_PATCH` and produces no event).
```

The same `event_type` (§5) can occur under either classification: what
distinguishes them is whether condition (a)+(b) held for that specific
occurrence, never the event name alone. An event's `denial_reason` and
`boundary` fields must be sufficient, on their own, for a reader to see
which condition applied without re-deriving it from surrounding prose.

## 5. The closed taxonomy

Grouped by the capability-boundary domain that raises it. Every name
below is stable, machine-readable, and **may be split, but never
silently redefined** — see [`../ARCHITECTURE.md`](../ARCHITECTURE.md) for
governance style. The five mutation-domain names, the eight
sandbox-domain names, and the five spawn/delegation-domain names below
were already declared provisionally by
[`mutation-authority.md`](../../shared/policies/mutation-authority.md#reporting-an-event)
and
[`scripts/security/validate_threat_model.py`](../../scripts/security/validate_threat_model.py)'s
`PROVISIONAL_EVENT_CLASSES`; this issue confirms them as final and adds
the three previously-undefined GitHub review-action-domain names.

### Source/Git mutation (`shared/policies/mutation-authority.md`)

A `requested_capability` of `APPLY_PATCH`, `COMMIT`, or `PUSH`
distinguishes which capability in the pipeline the event concerns; the
event type itself names *why* it was denied, not *which* capability.

| `event_type` | Fires when |
| --- | --- |
| `DENIED_MUTATION_CAPABILITY_ABSENT` | The capability was never granted (default `READ_ONLY`), or the requested operation is outside the closed 5-member set entirely (merge, branch deletion, deployment, repository-settings change — `AUTH-015`). |
| `DENIED_MUTATION_UNAUTHORIZED` | The capability exists in the closed set but no valid trusted authorization covers this attempt — including an `APPLY_PATCH` authorization presented for `COMMIT` or `PUSH` (`AUTH-003`, `AUTH-004`, `AUTH-010`, `AUTH-011`). |
| `DENIED_MUTATION_STALE_APPROVAL` | A prior authorization no longer matches the current patch digest or working-tree base (`AUTH-007`, `AUTH-008`). |
| `DENIED_MUTATION_SCOPE_ESCAPE` | The operation, or its verified result, exceeds the authorized path/file scope, including any attempt to target `.git/` (`AUTH-009`). |
| `DENIED_MUTATION_AUTHORIZATION_REPLAY` | A consumed, foreign-invocation, or non-inherited authorization was presented again, including a spawned child presenting its parent's grant (`AUTH-012`, `AUTH-013`). |

### Sandbox / runtime-validation (`shared/policies/runtime-validation.md`)

| `event_type` | Fires when |
| --- | --- |
| `DENIED_SANDBOX_NETWORK_ACCESS` | The isolated execution boundary denied an outbound network attempt. |
| `DENIED_SANDBOX_CREDENTIAL_ACCESS` | The isolated execution boundary denied access to a host secret, token, or credential. |
| `DENIED_SANDBOX_FILESYSTEM_ACCESS` | The isolated execution boundary denied access to host or unrelated-repository filesystem state outside the bounded work copy. |
| `DENIED_SANDBOX_RESOURCE_EXHAUSTION` | A bounded resource/time ceiling was exceeded and the run was terminated. |
| `DENIED_SANDBOX_UNAVAILABLE_PRIMITIVE` | A runtime-validation request was denied because the required execution boundary could not be established at all — recorded `unavailable` per that policy's "Outcome contract." This is the taxonomy entry for "runtime-validation request denied because the execution boundary could not be established." |
| `DENIED_GIT_UNSAFE_CONFIG` | A repository-declared command's Git configuration was unsafe to honor. |
| `DENIED_GIT_PATH_ESCAPE` | A command or checkout step attempted to escape the bounded work copy via a path. |

### Agent spawn / delegation (`shared/policies/agent-delegation.md`)

| `event_type` | Fires when |
| --- | --- |
| `DENIED_SPAWN_UNAUTHORIZED` | A spawn was attempted while `spawn_agent` is absent for this invocation (default), or by an agent that itself never holds it (e.g. a default-topology worker — `agent-delegation.md`, "Read-only worker capability set"). |
| `DENIED_SPAWN_BUDGET_EXCEEDED` | `max_agents_per_invocation` was reached and a further spawn was refused. |
| `DENIED_SPAWN_DEPTH_EXCEEDED` | `max_spawn_depth` was reached and a further spawn was refused. |
| `DENIED_DELEGATION_AUTHORITY_ESCALATION` | A child requested a capability or delegation set outside `parent_capabilities ∩ explicitly_delegated_capabilities`. |
| `DENIED_DELEGATION_REPLAY` | A child attempted to invoke a capability using its parent's (or a sibling's) authorization, or an inherited/forwarded code-mutation or review-action authorization was presented across an agent boundary (`AUTH-013`). |

### GitHub review-action mutation (`skills/github-pr-review/policies/review-action-authorization.md`)

Newly defined by this issue — this domain had no event representation
before #299. `github-pr-review`'s formal `APPROVE` / `REQUEST_CHANGES`
mutation is a **separate authority domain** from source/Git mutation
above (see that policy, "This policy governs a different authority
domain"); its denial events are therefore their own, non-overlapping
names rather than reused `DENIED_MUTATION_*` values.

| `event_type` | Fires when |
| --- | --- |
| `DENIED_REVIEW_ACTION_SELF_REVIEW` | A formal `APPROVE` / `REQUEST_CHANGES` event was withheld because the reviewer is the PR author or shares the author's controlling authority — absolute, never authorizable (`AUTH-014`, "Self-review is allowed; self-approval is not"). |
| `DENIED_REVIEW_ACTION_UNAUTHORIZED` | The desired event was withheld because the publication mode is not `ACTIVE`, or `ACTIVE` reviewer independence or GitHub event permission could not be established — reported human-side as `WITHHELD (<reason>)`. |
| `DENIED_REVIEW_ACTION_STALE_HEAD` | The desired event was withheld because the current PR HEAD advanced past the reviewed HEAD during "HEAD revalidation" or the final compare-and-set re-confirmation immediately before submission. |

`NOT_APPLICABLE` remains the sentinel — defined by the threat-model
catalog, not this document — for a scenario whose safe outcome is not
itself a capability denial (a reasoning-discipline scenario, a
decision-semantics correctness property, or a genuine
platform-unavailability outcome unrelated to any of the above).

## 6. Fields the issue's scope asked for that map onto existing names

Several items in the issue's scope list are represented by an existing
`event_type` plus a distinguishing field value, rather than by a new
name, to keep the taxonomy from fragmenting by capability:

- "code write denied because `APPLY_PATCH` capability is absent" →
  `DENIED_MUTATION_CAPABILITY_ABSENT`, `requested_capability: APPLY_PATCH`.
- "patch application denied because user authorization is absent" →
  `DENIED_MUTATION_UNAUTHORIZED`, `requested_capability: APPLY_PATCH`.
- "commit denied because `COMMIT` authorization is absent" →
  `DENIED_MUTATION_CAPABILITY_ABSENT`, `requested_capability: COMMIT`
  (`COMMIT` is absent-by-default exactly like the others in the closed
  set — see `mutation-authority.md`, "COMMIT").
- "push denied because `PUSH` authorization is absent" →
  `DENIED_MUTATION_CAPABILITY_ABSENT`, `requested_capability: PUSH`.
- "reuse of apply authorization for commit or push denied" →
  `DENIED_MUTATION_UNAUTHORIZED` (an `APPLY_PATCH` authorization is never
  accepted as `COMMIT` or `PUSH` authorization — no authorization
  actually covers the attempt).
- "authorization scope mismatch (repo / PR / HEAD / action /
  invocation)" → `DENIED_MUTATION_UNAUTHORIZED` /
  `DENIED_MUTATION_STALE_APPROVAL` for source mutation (carrying the
  mismatched `repository` / `working_tree_base` / `invocation_id` in the
  event fields) and `DENIED_REVIEW_ACTION_STALE_HEAD` for the GitHub
  domain — a scope mismatch is evidence carried in the event's fields,
  not a distinct event family.
- "GitHub mutation denied because the required capability is absent" →
  `DENIED_REVIEW_ACTION_UNAUTHORIZED` (this Skill never holds an
  `APPROVE` / `REQUEST_CHANGES` capability outside the `ACTIVE` +
  independence + permission conditions; there is no separate "absent"
  state to distinguish for this domain, unlike source mutation's
  five-member pipeline).
- "unavailable capability invocation (merge, branch deletion, repository
  write, deployment, or other authority intentionally not exposed)" →
  `DENIED_MUTATION_CAPABILITY_ABSENT` (`AUTH-015`; this also covers the
  GitHub-side equivalent — "This Skill never merges automatically, never
  deletes branches" per `review-output.md`).

## 7. Traceability back to the threat-model catalog

For every `AUTH-###` / `SBOX-###` / `DELEG-###` scenario in
[`../threat-model/catalog/`](../threat-model/catalog/README.md) whose
`expected_safe_outcome` is itself a capability denial, its
`expected_security_event` field now names a **final** entry from §5
above rather than a provisional placeholder. `AUTH-014` — the one
scenario the catalog explicitly flagged as blocked on this issue ("#299
does not yet define an event class for a withheld self-review action")
— is updated to `DENIED_REVIEW_ACTION_SELF_REVIEW`.

This document does not itself modify `enforcement_owner`,
`enforcement_point`, `benchmark_reference`, or `regression_evidence` on
any scenario — those stay owned by #301/#302/#303/#305/#306/#307 exactly
as the catalog's own "Coverage-gap semantics" describes. Confirming an
`expected_security_event` name as final is independent of whether that
scenario's runtime enforcement has landed yet.

## 8. Non-goals

- Emitting, transporting, storing, retrying, or querying a real event —
  owned by [#301](https://github.com/amirbena/code-review-skill/issues/301) /
  [#302](https://github.com/amirbena/code-review-skill/issues/302) /
  [#303](https://github.com/amirbena/code-review-skill/issues/303) and
  benchmarked by
  [#308](https://github.com/amirbena/code-review-skill/issues/308). This
  document defines the vocabulary and schema those issues report
  against; it ships no emitter, sink, or query surface, and no code in
  this repository constructs an instance of this schema today.
- Redefining or weakening any capability boundary, gate, or authorization
  rule — every boundary this taxonomy reports on is owned in full by the
  policy named in §5's table headers.
- Changing review findings, severity, suppression, review depth, or the
  mechanical decision — see §2.
- A second, competing event vocabulary — `scripts/security/validate_threat_model.py`'s
  `PROVISIONAL_EVENT_CLASSES` is the single machine-checkable mirror of
  §5; nothing else validates or declares this vocabulary independently.
- Relating to [#182](https://github.com/amirbena/code-review-skill/issues/182)
  (execution telemetry) or
  [#131](https://github.com/amirbena/code-review-skill/issues/131)
  (analytics) — see §1.
