# Shared Policy — Performance Deepening Capability

Applies identically to `local-code-review` and `github-pr-review`, in every
invocation mode. It is a **domain-specific deepening capability** under
[`specialist-depth.md`](specialist-depth.md)'s composition contract: bounded,
evidence-driven investigation of a performance/scale concern once base
review has already identified, per [`review-scope.md`](review-scope.md)'s
"Performance / scale" dimension, that a change materially implicates one.

This capability never decides whether a performance/scale concern is
considered at all — that is base reasoning's unconditional obligation, owned
by [`review-scope.md`](review-scope.md) (per #211) and never redefined
here. An obvious N+1, unbounded work, blocking I/O in a hot path, or
accidental complexity amplification is base reasoning's job on every
review, whether or not this capability engages, and that detection does not
start existing only once this capability engages. This capability answers
only the next question, per [`specialist-depth.md`](specialist-depth.md):
given a performance/scale concern base reasoning already identified, does
the available evidence justify tracing it further than base reasoning's own
bounded pass affords.

## The gap this closes

Base performance reasoning ("Performance / scale" in
[`review-scope.md`](review-scope.md)) already asks whether a change remains
correct and bounded at the volume the surrounding code is actually
exercised with, within that base pass's own bounded investigation. What it
cannot always afford on every change is *exhaustive* tracing: whether a
call issued once per iteration actually scales with a cardinality the
evidence shows is unbounded or materially large; whether a call path that
now runs inside a loop, request handler, or other repeated context was
previously amortized and no longer is; whether operations that could be
grouped into a single batched call are instead issued individually across
a data volume that makes the difference material; whether expensive work
was moved into, or already sits in, a hot path invoked per-request or
per-item rather than done once, cached, or hoisted out of the loop; whether
a change causes the number of queries or network calls issued to multiply
with input size rather than stay constant or grow sub-linearly; or whether
a change causes unbounded memory growth (an unbounded buffer, an
unbounded-growth cache, a retained reference that is never released) or
introduces contention that materially affects throughput or latency under
concurrent load. This capability is that deeper pass, engaged only when the
evidence already gathered shows it is warranted.

## Activation

Engages only when both hold:

1. [`review-scope.md`](review-scope.md)'s base pass has already identified
   a materially implicated **Performance / scale** dimension for the
   current change; and
2. the evidence gathered by that base pass — not the file name, directory,
   framework name, or a keyword such as "cache," "worker," "async," or
   "batch" appearing in an identifier — indicates the change's full cost
   behavior cannot be established within base reasoning's own bounded
   investigation: a call is made inside a loop or iteration whose bound is
   evidence-shown to be unbounded or to grow with a data volume the
   surrounding system actually exercises; a call path or resource
   acquisition that was previously amortized (once per request, once per
   batch) is now repeated per-item, or vice versa in a way whose safety is
   not evident; operations that could be batched are issued individually
   at a cardinality the evidence shows is material; work is placed in, or
   already sits in, a path invoked per-request or per-item whose cost the
   evidence shows increased; the number of queries or network calls the
   evidence shows a change issues is not evidently bounded independent of
   input size; or a buffer, cache, collection, or other retained resource
   the evidence shows a change grows is not evidently bounded or released.

A change that touches a file whose name, directory, or import suggests
performance relevance (a "perf," "cache," "batch," or "worker" name; a
profiling, caching, or async framework import) does not by itself satisfy
condition 2 — per [`specialist-depth.md`](specialist-depth.md), those are
signals, never independently sufficient. Conversely, a change with no file
conventionally associated with performance can still satisfy both
conditions when its semantic evidence shows a cardinality, call-path,
batching, hot-path-placement, amplification, or memory/concurrency-cost
concern (see worked examples below).

## Concern areas

Within an activated performance/scale concern, this capability deepens
investigation of:

- **Cardinality analysis** — whether an operation's cost is evidence-shown
  to scale with a data volume that is unbounded or grows materially beyond
  what the surrounding code's current callers exercise, including nested
  iteration whose combined cost is quadratic or worse in the sizes the
  evidence establishes.
- **Call-path behavior** — whether a change introduces, or already
  contains, a call to a database, remote service, or filesystem repeated
  once per element of an iteration (an N+1 pattern) rather than amortized
  across the iteration, traced along the actual call path the evidence
  establishes rather than assumed from a function's name.
- **Batching** — whether operations the evidence shows could be grouped
  into a single batched call are instead issued individually across a
  cardinality the evidence shows is material, and whether batching the
  change relies on is actually preserved rather than incidentally
  defeated (for example, a loop that now issues one call per item where a
  single batched call previously existed).
- **Hot-path placement** — whether work the evidence shows is expensive
  (serialization, computation, I/O, allocation) is placed in, or was
  already in and is now made more expensive by, a path invoked per-request
  or per-item, versus work that could be done once, cached, or hoisted
  outside the repeated path.
- **Query/network amplification** — whether a change causes the number of
  queries or network calls issued to multiply with input size (a fan-out
  per item, a retry pattern that compounds under load, pagination that
  re-issues a full scan per page) rather than stay constant or grow
  sub-linearly in the volume the evidence establishes.
- **Memory/concurrency implications** — whether a change causes unbounded
  memory growth (an unbounded buffer, an unbounded-growth cache, a
  retained reference or listener that is never released) or introduces
  contention (a shared lock, connection pool, or queue) whose effect on
  throughput or latency under concurrent load the evidence makes material.
  This concern area is about resource cost and throughput under load, not
  the correctness of a concurrent interleaving — whether two concurrent
  executions can violate an invariant is
  [`distributed-systems-deepening.md`](distributed-systems-deepening.md)'s
  question, not this capability's, and this capability does not re-trace
  it.
- **Other performance/scale-adjacent concerns** the activated concern's
  own evidence surfaces, reasoned about with the same evidence bar as the
  areas above — this list is representative of the capability's scope, not
  an exhaustive checklist run unconditionally on every activation.

## Missing call-graph or data-size context

When the call graph or data-volume context needed to establish whether a
call path, cardinality, or amplification concern is actually material
cannot be established from the diff and surrounding repository context —
the caller's actual invocation volume is not evident, a data source's size
is unknown, or an external system's request-handling behavior under the
traced load cannot be established from the evidence available — this
capability does not speculate about that volume, invocation count, or
downstream behavior. It reports only what the available evidence actually
supports, or, where no concrete evidence supports a finding, it produces no
finding for that concern rather than an invented one. This mirrors
"insufficient evidence" remaining a valid terminal outcome under "Cascading
activation" below.

## Cascading activation: bounded by the existing expansion contract

Tracing a call path to its actual invocation site, a cardinality to the
data volume that bounds it, or an amplification pattern to its downstream
effect reuses [`specialist-depth.md`](specialist-depth.md)'s
cascading-activation model, which in turn reuses
[`repository-expansion.md`](repository-expansion.md)'s fixed trigger/ring/
ceiling procedure and [`review-stopping-criteria.md`](review-stopping-criteria.md)'s
stop conditions — never a separate, unbounded audit of every call site or
loop in the repository. "Insufficient evidence" remains a valid terminal
outcome for a traced path, exactly as it is for base reasoning.

## Findings: ordinary findings, labeled

A finding this capability contributes is an ordinary finding: the same
severity derivation ([`severity.md`](severity.md)), the same evidence bar
([`evidence.md`](evidence.md)), the same identity/deduplication rules, and
the same remediation-scope-boundary reasoning
([`remediation-scope-boundary.md`](remediation-scope-boundary.md)) as any
other finding. It additionally carries the optional `capability` provenance
field, valued `performance-deepening`, per
[`finding.md`](../templates/finding.md), "Capability provenance" — never a
severity input, never a second schema. Concrete evidence must be tied to
the actual call path, cardinality, or amplification the capability traced;
generic "this could be slow" advice with no traced cost concern in this
change does not meet the evidence bar and is not reported.

## Worked examples

- **Engages — N+1 call path.** A change replaces a single query that
  fetched related records in one call with a loop that issues one query
  per parent record. Base reasoning identifies the added query inside a
  loop. Evidence shows the parent collection's size is not bounded by the
  current call sites. This capability traces the call path and reports the
  per-item query as the defect that will multiply database load with input
  size.
- **Engages — hot-path placement.** A per-request handler now
  re-parses a configuration file on every invocation instead of once at
  startup. Base reasoning identifies the added work in the request path.
  This capability traces the handler's invocation frequency from the
  evidence available and reports the repeated parse as unnecessary
  per-request cost that should be hoisted out of the hot path.
- **Does not engage — bounded base reasoning already suffices.** A loop
  iterates over a fixed, small, compile-time-bounded list of configuration
  entries and performs one call per entry. Base reasoning confirms the
  bound is fixed and small within its own bounded investigation; no
  further tracing is warranted, and this capability does not engage.
- **Misleading superficial signal.** A file named `PerformanceUtils.java`
  or `cache_helpers.py` changes only a comment or a constant's descriptive
  name, with no change to a call path, loop, or resource-acquisition
  behavior. File name alone does not activate this capability; base
  reasoning finds no material performance signal, and this capability does
  not engage.
- **Implication without the expected file/path.** Application code in an
  unrelated module changes a data-access helper so that a value
  previously read from an in-memory field is now fetched via a network
  call, with no file conventionally associated with "performance" or
  "cache" touched. Semantic evidence of the added per-call network
  round-trip still activates base reasoning and, given the call sites'
  iteration context, this capability.
- **Missing call-graph context — fails safe.** A shared helper function's
  call sites cannot be enumerated from the diff and repository context
  available (a dynamically dispatched or externally invoked entry point).
  This capability does not assert how many times the function is invoked
  per request; it reports only what the available evidence actually
  supports, or nothing for that concern.
- **Depth vs. remediation scope.** Tracing a call path surfaces a
  legitimate architectural P2: the fix would ideally introduce a batching
  API on the downstream service rather than call it once per item. The
  finding is reported at its evidenced severity;
  [`remediation-scope-boundary.md`](remediation-scope-boundary.md), not
  the depth of this capability's analysis, governs whether that broader
  rework is required now or surfaced as a `Follow-up`.

## Non-goals and ownership boundary

- **No benchmarking or profiling.** This capability performs the same
  kind of evidence-based code reasoning as the rest of review — it does
  not execute a benchmark, run a profiler, or measure actual runtime
  behavior against the target.
- **Not a generic optimization advisor.** It never runs an unconditional
  checklist of style or micro-optimization preferences unrelated to a
  traced cost concern; it deepens investigation of a performance/scale
  concern base reasoning already identified as materially implicated by
  the current change, nothing broader. It does not generate speculative
  performance advice.
- **Superficial filenames, framework names, and "performance-looking"
  code are not activation evidence.** A file's name or directory, a
  framework or library name, or code that superficially resembles a
  performance-sensitive pattern does not by itself trigger deep analysis;
  activation requires the base pass's own evidence of a material
  performance/scale concern, per "Activation" above.
- **Does not redefine base performance/scale detection.** Whether a
  change implicates a performance/scale concern at all remains
  [`review-scope.md`](review-scope.md)'s unconditional obligation (per
  #211); this capability does not become the mechanism that decides that,
  and ordinary performance reasoning — an obvious N+1, unbounded work,
  blocking I/O in a hot path, accidental complexity amplification —
  remains visible on every review whether or not this capability engages.
- **Does not redefine composition, cascading, or remediation-scope
  semantics.** Those remain owned by
  [`specialist-depth.md`](specialist-depth.md),
  [`repository-expansion.md`](repository-expansion.md) /
  [`review-stopping-criteria.md`](review-stopping-criteria.md), and
  [`remediation-scope-boundary.md`](remediation-scope-boundary.md)
  respectively.
- **Does not re-trace concurrent-interleaving correctness.** Whether two
  concurrent executions can interleave in a way that violates an
  invariant is [`distributed-systems-deepening.md`](distributed-systems-deepening.md)'s
  question; this capability's "Memory/concurrency implications" concern
  area is bounded to resource cost and throughput, not interleaving
  correctness.
- **No new finding/severity/evidence schema.** The `capability`
  provenance field is the only addition, and it is never a severity
  input — see [`finding.md`](../templates/finding.md), "Capability
  provenance."
