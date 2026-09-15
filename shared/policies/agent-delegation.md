# Shared Policy — Agent Delegation Boundary

Applies to any Code Review Agent Skill in this repository. Defines the
**capability boundary** for spawning and delegating to additional agents
during a review: `spawn_agent` as an explicit, absent-by-default
capability; hard invocation-level budgets on agent count and spawn depth;
the delegation-intersection rule that bounds what a child may ever hold;
and the confused-deputy protections that stop authority from being
manufactured instead of granted. Runtime-specific capability *detection*
(which mechanism a given runtime exposes) is owned by
[`parallel-review.md`](parallel-review.md), which this policy composes
with — it does not redefine when parallel review is worthwhile, the
worker input/output shape, or aggregation; it defines what a spawned
worker is **allowed to hold and do** once execution-policy has decided to
use one.

This is the canonical *enforcement* source for issue #303 (agent-spawn /
delegation), scoped by the threat model in this repository's
`docs/threat-model/threat-model.md` and its `DELEG-###` scenarios in
`docs/threat-model/catalog/spawn-delegation.yaml` (repository-development
docs, not part of either packaged Skill). It does not implement mutation execution (owned by
`github-pr-review`'s `review-action-authorization.md`
and the mutation-authority threat domain, `AUTH-###`, issue #301) or
runtime sandboxing (issue #302). It does not change review reasoning,
severity, verdict semantics, or publication UX.

## Core invariant

```text
child_authority  ⊆  parent_authority  ∩  explicit_delegation
```

Delegation can only narrow authority, never create it. A child's
effective capability set is always a subset of what its parent actually
holds, further narrowed to whatever the parent explicitly delegated. No
mechanism described below — a capability request, shared orchestration
state, an alternate identity, or budget exhaustion — may widen this.

## `spawn_agent` is an explicit capability

`spawn_agent` is a named capability like any other (see
[`review-ownership.md`](review-ownership.md) and
`github-pr-review`'s `review-action-authorization.md`
for the sibling capability boundaries this one composes with). By
default:

```text
spawn_agent = absent
```

An invocation holds `spawn_agent` only when the execution-policy decision
in [`parallel-review.md`](parallel-review.md) ("Execution-policy
decision") has actually selected parallel review for materially
independent dimensions. A reviewer that never needs parallel workers
never acquires it — there is no ambient or default-on spawn capability.

## Default topology stays shallow

```text
review owner
   ├── read-only worker
   ├── read-only worker
   └── read-only worker
```

One level, workers with no further `spawn_agent` capability of their own.
A worker never spawns a worker of its own by default — see "Read-only
worker capability set" below. A deeper or wider topology requires an
explicitly justified path (a review dimension that itself decomposes into
independent sub-analyses too large for one worker) and remains subject to
every budget and depth limit below; it is never the default shape.

## Hard invocation-level budgets

Two limits apply per invocation, configured once at the review owner and
never raised mid-invocation:

- **`max_agents_per_invocation`** — the maximum number of agents (workers
  and any of their own children) that may exist across the **whole**
  agent tree for this invocation, root included.
- **`max_spawn_depth`** — the maximum depth of the agent tree measured
  from the review owner (depth 0) to the deepest descendant. The default
  shallow topology above is depth 1.

### One canonical accounting model, tree-wide

Both budgets are counted against **one shared pool for the entire
invocation**, not a fresh independent allowance handed to each parent.

```text
WRONG:  each parent gets its own max_agents_per_invocation
         → nested spawning multiplies the effective total
RIGHT:  one invocation-level counter, decremented by every spawn
         anywhere in the tree, regardless of which node spawns it
```

A node three levels deep that spawns a child decrements the same counter
the review owner's own first spawn decremented. Recursive or nested
spawning can reach the depth limit or the count limit faster, but it can
never evade either by spawning through an intermediate node — depth and
count are properties of the one tree, not of any single parent's local
view of it.

### Budget exhaustion fails closed

When either budget is reached, further spawn requests are refused —
never silently widened, never granted "just this once" because work
remains, and never resolved by increasing the configured limit
mid-invocation. Work already in flight on already-spawned agents
completes normally; the review that cannot spawn a required worker
degrades the same way any other missing required dimension does (see
[`parallel-review.md`](parallel-review.md), "Failure handling" —
`REVIEW INCOMPLETE`, never `REVIEW CLEAN`), not by silently accepting
sequential execution as a downgrade in coverage without reporting it.

## Delegation rule

Every child receives an **explicit** capability set at spawn time —
never an implicit inheritance of "whatever the parent can do."

```text
effective_child_capabilities
    =  parent_capabilities
       ∩  explicitly_delegated_capabilities
       ∩  runtime_policy
```

All three terms narrow; none can add. A parent cannot delegate a
capability it does not itself hold (rejected — see "Confused-deputy
protection" below), and naming a capability in a delegation request is
never sufficient by itself: the capability must also be present in the
parent's own held set and permitted by runtime policy. Copying the
parent's state, token, or orchestration metadata onto a child is never
equivalent to, or a substitute for, an explicit delegation grant — a
child that merely has visibility into parent state does not thereby
acquire any capability from it.

If a child legitimately requires stronger authority than its parent can
delegate, that requires a **separately issued** runtime capability
granted through the same channel the parent's own capabilities came from
— never manufactured by the spawn relationship itself.

### Mutation and formal review-action authorization are non-transferable

Code-mutation authorization and formal review-action authorization
(`APPROVE` / `REQUEST_CHANGES` per
`github-pr-review`'s `review-action-authorization.md`)
are **never** delegated by default and are not part of the ordinary
capability-intersection path above. A child does not inherit, and cannot
be granted by copying parent state, either authorization. This repository
deliberately reuses the single-use, narrowly-scoped authorization model
already defined for GitHub mutation
(`github-pr-review`'s `review-action-authorization.md`,
"Authorization scope (no replay)") rather than inventing a second
token/accounting system: any authorization that model recognizes stays
bound to the exact invocation, repo, PR, reviewed HEAD, and single
permitted action it was issued for, and that binding does not loosen or
generalize just because the invocation spawned children. A single-use
authorization must not be inherited, copied, forwarded, replayed,
reconstructed from orchestration state, or shared between siblings — by
a parent to a child, or between children of the same parent.

## Confused-deputy protection

Capability checks bind to the **acting agent's own granted identity**,
never to whatever identity, tool, subprocess, or credential it happens to
invoke through. This extends the identity-binding principle
`github-pr-review`'s `review-action-authorization.md`
already applies to reviewer independence (an alternate account, token,
bot, service account, GitHub App identity, nested agent, or spawned
process controlled by the same authority is still that authority, never
a new one) to the agent-spawn runtime specifically:

- An agent cannot acquire a capability by acting through a bot, an
  alternate account, a subprocess, a different tool, or orchestration
  metadata it can influence — the check is always against what *that
  agent* was actually granted, not what the surface it acted through
  happens to expose.
- Sibling agents cannot combine their individually-granted capabilities,
  via shared state, shared orchestration metadata, or any other visible
  channel, into a capability neither held individually. Capabilities are
  fixed at spawn time per agent; no read of shared state changes what an
  agent is authorized to do.
- A nested agent cannot manufacture authority through its own prompt
  text or generated metadata — exactly as prompt text, generated
  instructions, and nested-agent/sub-agent/spawned-process channels
  already can never establish mutation authorization
  (`github-pr-review`'s `review-action-authorization.md`,
  "What can never establish it").

## Read-only worker capability set

A worker spawned under the default shallow topology
([`parallel-review.md`](parallel-review.md), "Worker contract") holds
exactly the analysis capability it needs and none of the following,
unless a separately justified path explicitly delegates them:

- **publication** — a worker never publishes findings, a summary, or any
  machine-readable status; only the aggregating review owner does, once
  ([`parallel-review.md`](parallel-review.md), "Centralized aggregation"
  and "Boundaries").
- **runtime validation execution** — a worker never runs repository
  validation commands on its own authority; that stays owned by
  [`runtime-validation.md`](runtime-validation.md) at the point the
  policy already grants it.
- **code mutation** — a worker never edits, patches, or otherwise
  mutates the reviewed repository.
- **formal review-action authorization** — a worker never holds, and
  cannot be delegated, `APPROVE` / `REQUEST_CHANGES` authority (see
  "Mutation and formal review-action authorization are non-transferable"
  above).
- **further `spawn_agent`** — a worker does not itself hold
  `spawn_agent` under the default topology; it returns candidate findings
  to its parent instead of spawning its own children.

An out-of-grant action attempted by a worker is refused; the worker's
in-grant analysis output is still collected normally — a denied action on
one capability does not discard the worker's otherwise-valid findings.

## Reporting an event

A refused spawn or delegation attempt is reported, not swallowed. The
event-class vocabulary (repository-development design record, named here
rather than linked because it is not a packaged resource:
`docs/security-events/security-event-model.md`, Issue #299) names the
reason:

- `DENIED_SPAWN_UNAUTHORIZED` — `spawn_agent` is absent for this
  invocation or for the acting agent (the default; a default-topology
  worker never holds it — "Read-only worker capability set" above).
- `DENIED_SPAWN_BUDGET_EXCEEDED` — `max_agents_per_invocation` was
  reached.
- `DENIED_SPAWN_DEPTH_EXCEEDED` — `max_spawn_depth` was reached.
- `DENIED_DELEGATION_AUTHORITY_ESCALATION` — a child requested a
  capability or delegation set outside
  `parent_capabilities ∩ explicitly_delegated_capabilities`.
- `DENIED_DELEGATION_REPLAY` — a child attempted to invoke a capability
  using its parent's or a sibling's authorization, or an inherited/
  forwarded mutation or formal review-action authorization was presented
  across the spawn boundary ("Mutation and formal review-action
  authorization are non-transferable" above).

Every event additionally carries the closed-set `classification` #299
defines — `expected_denial` (no spawn or delegation was ever attempted;
execution simply stayed within its granted set) or
`boundary_violation_attempt` (a concrete spawn or capability invocation
was actually attempted against a set that could never have satisfied it)
— derived from runtime evidence, never from inferred intent. Recording
this event never widens, narrows, or substitutes for the capability
boundary above.

## Composition with existing guarantees

This policy is additive. It never relaxes
[`parallel-review.md`](parallel-review.md)'s existing worker contract
(bounded normalized input, structured-findings-only output, no
cross-worker visibility, centralized aggregation), the self-review
mutation boundary or reviewer-independence rules in
`github-pr-review`'s `review-action-authorization.md`,
or review ownership in
[`review-ownership.md`](review-ownership.md). Where any of those already
denies an action, this policy's capability gate is an additional,
independent reason for the same denial — never a path around it.

## Non-goals

- Implementing code-mutation execution — owned by issue #301 and
  `github-pr-review`'s `review-action-authorization.md`.
- Implementing runtime sandboxing — owned by issue #302.
- Selecting *when* parallel review is worthwhile, the worker
  input/output shape, or aggregation — owned by
  [`parallel-review.md`](parallel-review.md).
- Redefining review reasoning, severity, verdict semantics, or
  publication UX.
- Broadening agent use beyond the workflows already justified by
  [`parallel-review.md`](parallel-review.md).
