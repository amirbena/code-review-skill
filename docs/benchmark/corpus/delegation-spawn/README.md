# Agent-Spawn / Delegated-Authority Benchmark Corpus

Repository-development artifact for GitHub Issue
[#307](https://github.com/amirbena/code-review-skill/issues/307), a
durable adversarial benchmark corpus proving the agent-spawn and
delegated-authority boundary
[#303](https://github.com/amirbena/code-review-skill/issues/303) built
cannot regress unnoticed: capability widening, recursive spawning,
authorization inheritance/replay, sibling collusion, and confused-deputy
routing must all stay denied across normal, nested, and adversarial
execution paths.

## Why this is not a `benchmark-case/v1` corpus

Unlike the corpora under [`../`](../README.md) (each a self-contained
inline patch plus expected findings), this boundary's inputs and
expectations are not a diff and a set of review findings — they are a
capability grant, a spawn-depth/agent-count budget, and a structural
allow/deny result. [`fixture-format.md`](../../fixture-format.md)'s
`expected` block has no field for any of that. Rather than stretch that
closed schema, this corpus follows the same test-only, data-driven
reference-fixture pattern
[`../reviewer-brief/README.md`](../reviewer-brief/README.md) already
established for a domain the schema does not fit:

- [`../../../../tests/reference/benchmark/delegation_fixtures.py`](../../../../tests/reference/benchmark/delegation_fixtures.py) —
  one `DelegationCase` per required outcome shape, each a zero-argument
  `run()` closure that exercises the *single* reference model,
  [`../../../../tests/reference/review/agent_delegation.py`](../../../../tests/reference/review/agent_delegation.py)
  (composing with
  [`review_action_authorization.py`](../../../../tests/reference/review/review_action_authorization.py)
  for provenance/scope), plus the declarative metadata #307 requires:
  parent capability set, explicit delegated capability set, requested
  child capability, spawn depth, invocation agent-count budget, expected
  allow/deny result, linked `DELEG-###`/`DOS-###` threat-scenario id(s),
  and (for a denied case) the provisional denial classification.
- [`../../../../tests/unit/benchmark/test_delegation_spawn_corpus.py`](../../../../tests/unit/benchmark/test_delegation_spawn_corpus.py) —
  runs every case's `run()` and asserts its actual outcome matches the
  declared expectation, plus corpus-completeness checks (every required
  category, every catalog `DELEG-###`/tagged `DOS-###` id, every
  requirement tag), the malformed-fixture rejection suite, and two
  deeper whole-sequence tests (churn, recursion) a single allowed/denied
  fixture cannot capture alone.

This corpus is **not** a duplicate of
[`../../../../tests/unit/review/delegation/test_agent_delegation_authorization.py`](../../../../tests/unit/review/delegation/test_agent_delegation_authorization.py),
which #303 already landed as hand-written regression tests, one per
`DELEG-###` scenario, against the same reference model. That suite is
*why* the boundary holds; this corpus is the declarative, metadata-bearing
**benchmark** layer #307 asks for — every case carries its expectation as
structured *data*, validated independently of execution, so future
tooling ([#310](https://github.com/amirbena/code-review-skill/issues/310))
can select or introspect the corpus by category or threat-scenario id
without re-deriving it from test method names. Both layers call into the
same single implementation; neither ever forks it.

## Evaluation style

Every comparison in this corpus is a **deterministic structural
assertion** — allowed/denied, effective granted capabilities, agent
count, spawn depth, ledger consumption state — never an LLM/rubric score.
This corpus is disjoint from the finding-precision/recall/severity
metrics ([#41](https://github.com/amirbena/code-review-skill/issues/41))
and the Reviewer Brief semantic-quality corpus
([#309](https://github.com/amirbena/code-review-skill/issues/309)): it
never touches a finding, a severity, or review prose, and it never scores
review *quality* — only capability-boundary correctness.

## Categories and required outcome shapes

| Category | Required shapes |
| --- | --- |
| `spawn_capability` | no `spawn_agent` → denied (`DELEG-001`); valid capability → bounded spawn succeeds |
| `invocation_budget` | exceeding `max_agents_per_invocation` → denied (`DELEG-002`); within budget → allowed; spawn/kill/spawn churn cannot reset accounting (`DELEG-004`); recursive spawning cannot build an unbounded tree (`DELEG-004`/`DOS-006`); excessive parallel fan-out is bounded (`DOS-007`) |
| `spawn_depth` | nested spawn within `max_spawn_depth` → allowed; exceeding it → denied (`DELEG-003`) |
| `capability_subset` | delegating a capability the parent lacks → denied (`DELEG-005`); child requesting a capability outside explicit delegation → denied (`DELEG-006`); valid subset delegation → allowed |
| `authorization_non_transfer` | child cannot inherit/copy mutation authorization or formal review-action authorization (`DELEG-007`); replay/forwarding across agents → denied; a genuinely, independently issued single-use authorization still succeeds once |
| `sibling_reconstruction` | siblings cannot reconstruct authority from shared orchestration state/metadata — combination is intersection-only, never union (`DELEG-008`) |
| `confused_deputy` | an alternate identity/token/bot/subprocess/tool-surface channel never manufactures a capability the acting agent lacks (`DELEG-009`); only a genuinely independent, trusted channel ever counts |
| `read_only_worker` | an ordinary parallel worker cannot publish, mutate, run runtime validation, take a formal review action, or spawn again (`DELEG-010`); its in-grant analysis capability still works |
| `budget_exhaustion` | exhaustion stops safely — no widening of the configured limit, no silent extra workers, no accounting reset (`DELEG-011`); below the limit, spawning is unaffected |

Every case's category, covered requirement tags, and linked
`DELEG-###`/`DOS-###` threat-scenario id(s) live in its
`DelegationCase` definition in `delegation_fixtures.py` — this table is a
map, not a second source of truth.

## Denial classification / #299 extension point

Each denied case's `expected_security_event` cites one of the
denial-classification strings the single reference model already defines
(`ad.DENIED_SPAWN_UNAUTHORIZED`, `ad.DENIED_SPAWN_BUDGET_EXCEEDED`,
`ad.DENIED_SPAWN_DEPTH_EXCEEDED`,
`ad.DENIED_DELEGATION_AUTHORITY_ESCALATION`,
`ad.DENIED_DELEGATION_REPLAY`) — the same vocabulary
`docs/threat-model/catalog/spawn-delegation.yaml` and
`scripts/security/validate_threat_model.py`'s
`PROVISIONAL_EVENT_CLASSES` declare.
[#299](https://github.com/amirbena/code-review-skill/issues/299) (the
real, authoritative security-event taxonomy,
`docs/security-events/security-event-model.md`) has now landed and
confirmed these five names as final: every denied `CaseOutcome.security_event`
was already populated from this closed set, so no fixture restructuring
or string rename was required.

## Threat-scenario traceability

This corpus covers every `DELEG-###` scenario in
[`../../../threat-model/catalog/spawn-delegation.yaml`](../../../threat-model/catalog/spawn-delegation.yaml)
(11 scenarios, issue [#300](https://github.com/amirbena/code-review-skill/issues/300))
plus the two `resource-abuse.yaml` scenarios that declare
`benchmark_family: delegation/#307` (`DOS-006`, `DOS-007`). Those catalog
entries' `benchmark_reference` field, previously `COVERAGE_GAP`, now
points at this corpus. `test_delegation_spawn_corpus.py` cross-checks its
own required-id set against the live catalog file so a future catalog
edit is caught here, not silently drifted from.

## Focused selection

Run this corpus independently of the rest of the benchmark suite:

```bash
python3 -m unittest tests.unit.benchmark.test_delegation_spawn_corpus
```

exactly like every other `test_*_corpus.py` module under
[`../../../../tests/unit/benchmark/`](../../../../tests/unit/benchmark/)
(e.g. `test_security_deepening_corpus.py`) — no other benchmark case
needs to run first.

## Corpus validation

`delegation_fixtures.validate_case` / `validate_corpus` reject a
malformed fixture: an unrecognized category, a non-`Capability` element
in a capability set, a negative depth/count, an out-of-range budget, an
invalid `expected_result` token, a denied case missing (or citing an
unrecognized) denial classification, an allowed case that still carries
one, or a threat-scenario id that does not match `<DELEG|DOS>-<3 digits>`.
`MalformedFixtureRejectionTests` in the unit-test module exercises every
one of these against deliberately broken fixtures built from
`dataclasses.replace` over a real, passing case. The validator
deliberately encodes no runtime implementation internals (no
`InvocationBudget`/`AgentNode` wiring) — it is a clean data schema, per
#307's own constraint.
