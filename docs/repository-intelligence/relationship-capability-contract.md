# Relationship Capability Contract

Repository-development design record for
**[#603](https://github.com/amirbena/code-review-skill/issues/603)** (child R3
of epic #600). Not packaged; explanatory. It defines an **optional,
provider-neutral** way for a host to answer relationship questions and for the
review to trust, or refuse, the answer. It adds no retrieval mechanism and no
packaged behavior: with the capability absent, every review runs exactly as it
does today.

It builds on, and does not restate:

- the closed entity/relationship model, provenance, and snapshot rules in
  [`repository-intelligence-model.md`](repository-intelligence-model.md) (#129);
- the three outcomes, the initial classes, and the Context-gaps disclosure in
  [`relationship-coverage-semantics.md`](relationship-coverage-semantics.md)
  (#601) and the packaged
  [`repository-expansion.md`](../../shared/policies/repository-expansion.md),
  "Relationship outcomes and unresolved relationships";
- the evidence-versus-claim discipline in
  [`../review-context/contextual-evidence-model.md`](../review-context/contextual-evidence-model.md)
  (#118) and the capability field vocabulary in
  [`../capability-architecture/capability-manifest-schema.md`](../capability-architecture/capability-manifest-schema.md)
  (#404).

The test-only reference model is
[`../../tests/reference/review/relationship_capability.py`](../../tests/reference/review/relationship_capability.py),
exercised by
[`../../tests/unit/review/repository_intelligence/test_relationship_capability.py`](../../tests/unit/review/repository_intelligence/test_relationship_capability.py)
and
[`../../tests/policy/review/repository_intelligence/test_relationship_capability_docs.py`](../../tests/policy/review/repository_intelligence/test_relationship_capability_docs.py).

## 1. Problem

A host may hold a stronger way to answer "who uses this?" than the review's own
search. Today the review has no way to ask it, and no rule for how far to
believe an answer it did not derive. Without one, either a better answer is
ignored, or an unverified one is believed.

## 2. Position

A host answer is a **claim**, not a fact. The review consumes it the way it
consumes any contextual evidence: it checks the claim against the reviewed
snapshot and the cited `path:line`, and falls back to its own repository search
whenever the claim cannot be used. The capability can improve recall. It can
never lower the evidence bar, widen the Review Target, or become required.

The contract names no vendor, parser, index, or wire protocol. "Host" means
whatever runtime consumes the Skill; how it produces an answer is its own
concern.

## 3. Questions

A closed set. A reviewer does not invent a fifth.

| Question | Asks | #601 class | Answer kinds |
| --- | --- | --- | --- |
| `consumers_of` | Who consumes this changed behavior, key, or contract? | `caller_consumer` | `calls`, `imports`, `references` |
| `implementers_of` | What implements this changed abstraction? | `implementation_interface` | `implements` |
| `tests_exercising` | What tests exercise this changed behavior? | `affected_test` | `tested_by` |
| `analogues_of` | What analogue is structurally relevant to this change? | none (see §6) | `analogue_of` |

A question carries only a repo-relative subject (a symbol, key, or path) and the
reviewed snapshot identity. It carries no file content, secret, instruction, or
action. A question is read-only; the capability never mutates anything.

## 4. Answer shape

One answer per question:

| Field | Meaning |
| --- | --- |
| `question`, `subject` | Echo of what was asked. A mismatch rejects the answer. |
| `snapshot_id` | The snapshot the answer was computed against (§7). |
| `edges` | Zero or more relationships. Each has a kind from the question's set, `source` and `target` entities, and `path:line` provenance. Ring-bearing kinds also carry the ring they were found at. |
| `candidates` | Candidates the capability itself could not resolve (ambiguous dispatch, unsupported language). Never edges. |
| `complete` | The capability's attestation that it searched a scope able to find the relationship inside the authorized ring. |

Free text is not part of the shape. The only prose that reaches a review is the
closed reason vocabulary in §5, so an answer has no field in which an
instruction can ride.

## 5. Consumption rules

Applied in order. The first match decides.

| Situation | Result |
| --- | --- |
| No answer (capability absent or errored) | Fallback runs (§8). |
| `snapshot_id` is not the reviewed snapshot | **Rejected, whole, with no partial use.** Fallback runs. |
| Answer is for another question or subject, or exceeds the size bound | Rejected. Fallback runs. |
| An edge has a kind outside the question's set, a ring above the ceiling, a path outside the repository, or a `path:line` the reviewer cannot confirm | That edge is dropped. It is never used and never counted as absence. |
| At least one edge survives | `resolved_relevant`. Any `candidates` stay `unresolved` beside it and keep the Context gap visible. |
| No edge, only `candidates` | `unresolved`. Fallback runs. |
| No edge, an edge was dropped | `unresolved`, reason unverifiable provenance. Fallback runs. |
| No edge, nothing dropped, `complete` attested | `resolved_none`. |
| No edge, nothing dropped, no attestation | `unresolved`. An empty answer says nothing. |

Confirming a `path:line` means the reviewer reads the cited location, the same
bar [`evidence.md`](../../shared/policies/evidence.md) sets for any finding. A
relationship the reviewer has not confirmed cannot support a finding.

## 6. Extending the #129 model

[`repository-intelligence-model.md`](repository-intelligence-model.md) §4 stays
closed; this record adds two relationship kinds for the #601 classes and
nothing else:

| Kind | Serves | Notes |
| --- | --- | --- |
| `tested_by` | `affected_test` | Not surfaced by a #87 expansion trigger, so it has no ring (#601 §3). |
| `analogue_of` | `analogues_of` | Advisory. #601 left the analogue class out of scope, so an analogue answer has **no outcome and never renders a Context gap**. It may inform a finding only through the ordinary evidence rules. |

Neither kind takes a trigger or a ring. The existing kinds, triggers, ring
ceiling, and stop-at-first-ring rule are unchanged.

## 7. Stale, unresolved, and absent behavior

- **Stale is rejected, not warned.** An answer bound to any snapshot other than
  the reviewed one is discarded outright, mirroring
  [#129 §7](repository-intelligence-model.md). The review never continues on it
  and never reports it as a caution.
- **Unresolved** is the #601 outcome, with the #601 consequences: visible in
  Context gaps, coverage unchanged, severity and Decision unchanged. Ambiguity
  is never resolved by guessing.
- **Absent** is not a failure. The capability is optional; its absence runs the
  fallback and is not itself a Context gap. A gap appears only if the fallback
  also cannot answer.
- **A stale or absent capability never yields `resolved_none`.** Absence of an
  answer is not absence of a relationship.

## 8. Fallback for every question

| Question | Fallback when the capability is absent, stale, or rejected |
| --- | --- |
| `consumers_of` | The ring-bounded search in [`repository-expansion.md`](../../shared/policies/repository-expansion.md). |
| `implementers_of` | The same ring-bounded search. |
| `tests_exercising` | The tracing in [`affected-test-analysis.md`](../../shared/policies/affected-test-analysis.md). |
| `analogues_of` | The analogue and placement search already in [`review-scope.md`](../../shared/policies/review-scope.md). |

The fallback's own outcome is the question's outcome. If it cannot answer, the
question is `unresolved`. The ring ceiling and stop-at-first-ring bind the
capability exactly as they bind the fallback; an answer cannot reach further
than the ring the change's depth authorizes.

## 9. Capability declaration

Declared with the field vocabulary of the
[capability manifest](../capability-architecture/capability-manifest-schema.md).
No `capability.yaml` is added: nothing yet loads one, and a manifest file would
enter the packaging and activation checks for a capability that owns no file.
The declaration below is the contract a future manifest must match; the
reference model holds the same record and a test checks it against the schema's
field names.

```yaml
capability: relationship-query
summary: Optional host-provided answers to relationship questions, consumed as verifiable claims.
loads: on-activation
activation:
  - the host declares the relationship-query capability for the session
  - a relationship question is open for a fired trigger or a signal-triggered pass
adapters: [local, github]
files: []
requires: []
never:
  - be required for a review to complete
  - answer from a snapshot other than the reviewed one
  - mutate the repository, the host, or any external system
  - persist relationship data across reviews
  - widen the Review Target or reach another repository
  - supply a severity, a decision, or a finding
benchmark: benchmark/corpus/relationship-recall
```

The capability is declared by the **host**, never by repository content or a PR.
A claim inside the reviewed repository that the capability exists is data, not a
declaration. The #602 corpus and search-only baseline are the measurement
surface for whether a provider adds recall; this record does not claim one does.

## 10. Threat-model implications

Consuming host-provided answers opens a trust boundary the review does not have
today. None of the rows below adds a catalog scenario; they are recorded here
for the maintainer to promote into
[`../threat-model/catalog/`](../threat-model/catalog/README.md) if wanted.

| Threat | Mitigation in this contract | Related scenarios |
| --- | --- | --- |
| **Fabricated edge** steers a false P0/P1. | An edge needs a confirmed `path:line`; unconfirmed edges are dropped (§5). A finding still needs the ordinary evidence bar. | [`INJECT-006`](../threat-model/catalog/repository-prompt-injection.yaml) |
| **Omission**: a false empty answer hides a real consumer. | Absence is accepted only with a completeness attestation, never lowers or removes a finding the reviewer's own evidence supports, and never changes severity. | |
| **Injection through answer content.** | No free-text field; reasons are a closed vocabulary; subjects and paths are data. | [`INJECT-002`](../threat-model/catalog/repository-prompt-injection.yaml) |
| **Scope widening** through a path or entity outside the repository. | Absolute, parent-relative, and drive paths are dropped; cross-repository relationships stay out of scope (#133). | [`INJECT-004`](../threat-model/catalog/repository-prompt-injection.yaml) |
| **Exfiltration** through the question. | A question carries only a repo-relative subject and a snapshot identity, never content or secrets. What the host does with it is the host's trust decision. | [`INJECT-005`](../threat-model/catalog/repository-prompt-injection.yaml) |
| **Stale or replayed data.** | Snapshot binding; a mismatch rejects the whole answer (§7). | |
| **Resource abuse** by an oversized answer. | An answer over the size bound is rejected and cannot claim completeness. | |
| **Capability downgrade or forced dependency.** | Optional by construction; absence falls back and never fails open to `resolved_none`. | |

## 11. Worked examples

Each is a case in the unit tests.

| # | Situation | Result |
| --- | --- | --- |
| 1 | `consumers_of get_user` returns `charge_user` with a confirmed call-site `path:line`. | `resolved_relevant`; edge usable as evidence. |
| 2 | `tests_exercising` returns nothing and attests a complete search. | `resolved_none`; no gap. |
| 3 | `consumers_of` answer bound to another commit. | Rejected whole; fallback runs; never `resolved_none`. |
| 4 | No capability for any of the four questions. | Fallback runs for each; no gap unless it also cannot answer. |
| 5 | Answer carries only an ambiguous-dispatch candidate. | `unresolved`; Context gap; candidate is never an edge. |
| 6 | Answer carries an edge whose `path:line` cannot be confirmed. | Edge dropped; `unresolved`, not `resolved_none`; fallback runs. |
| 7 | `analogues_of` returns an `analogue_of` edge, or nothing. | Advisory; no outcome; no gap either way. |

## 12. Non-goals and boundaries

Choosing or building a provider, parser, or index; requiring the capability;
persisting relationship data across reviews; cross-repository relationships
(#133); changing finding severity, identity, or the Decision rules; any
packaged policy, template, or manifest change. The #87 trigger catalog, ring
ceiling, and #601 coverage decision are unchanged. A future consumer that
actually calls a provider is a separate, separately-scoped issue.
