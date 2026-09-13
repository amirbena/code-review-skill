# Shared Policy — Distributed Systems Deepening Capability

Applies identically to `local-code-review` and `github-pr-review`, in every
invocation mode. It is a **domain-specific deepening capability** under
[`specialist-depth.md`](specialist-depth.md)'s composition contract: bounded,
evidence-driven investigation of a concurrency/distributed-system concern
once base review has already identified, per
[`review-scope.md`](review-scope.md)'s "Concurrency / distributed-system
semantics" dimension, that a change materially implicates one.

This capability never decides whether a concurrency/distributed-system
concern is considered at all — that is base reasoning's unconditional
obligation, owned by [`review-scope.md`](review-scope.md) (per #211) and
never redefined here. It answers only the next question, per
[`specialist-depth.md`](specialist-depth.md): given a concurrency/
distributed-system concern base reasoning already identified, does the
available evidence justify tracing it further than base reasoning's own
bounded pass affords.

## The gap this closes

Base concurrency reasoning ("Concurrency / distributed-system semantics" in
[`review-scope.md`](review-scope.md)) already asks, for shared mutable
state read and later acted on or a message that can be delivered more than
once or out of order, whether two concurrent executions could interleave
in a way that violates an invariant the code assumes holds — within that
base pass's own bounded investigation. What it cannot always afford on
every change is *exhaustive* tracing: every interleaving a piece of shared
state admits, how a retry interacts with work already performed, whether
an idempotency boundary actually holds at every entry point that can
trigger it, who owns coordination of a shared resource across components,
or how the system behaves when only part of a multi-step operation
completes. This capability is that deeper pass, engaged only when the
evidence already gathered shows it is warranted.

## Activation

Engages only when both hold:

1. [`review-scope.md`](review-scope.md)'s base pass has already
   identified a materially implicated **Concurrency / distributed-system
   semantics** dimension (or a concurrency/ordering-guarantee trigger
   under "Architectural placement and execution-lifecycle fidelity", or a
   retry/redelivery trigger under "Failure state, retry safety, and
   recovery") for the current change; and
2. the evidence gathered by that base pass — not the file type, path,
   framework, or a keyword in a name — indicates the concern's full
   correctness cannot be established within base reasoning's own bounded
   investigation: more than one plausible interleaving of the shared
   state exists, a retryable operation's interaction with prior attempts
   is not yet traced, an idempotency check's coverage of every entry
   point that can trigger the operation is unconfirmed, coordination of a
   shared resource spans more than one component or owner, or the
   correctness of a multi-step operation under partial failure depends on
   an assumption the base pass could not confirm within its own ring.

A change that touches a queue consumer, a lock/mutex, or a file whose name
suggests concurrency relevance does not by itself satisfy condition 2 —
per [`specialist-depth.md`](specialist-depth.md), those are signals, never
independently sufficient. Conversely, a change with no file conventionally
associated with concurrency or messaging can still satisfy both
conditions when its semantic evidence shows a shared-state or
retryable-delivery concern (see worked examples below).

## Concern areas

Within an activated concurrency/distributed-system concern, this
capability deepens investigation of:

- **Ordering guarantees** — whether an operation's correctness depends on
  events, messages, or writes arriving or applying in a particular order,
  and whether that order is actually guaranteed by the transport, queue,
  or storage layer involved, or only assumed.
- **Retry interaction** — how a retried operation interacts with the
  effects of a prior attempt that may have partially or fully succeeded,
  not merely whether a retry exists; builds on, and does not duplicate,
  [`review-scope.md`](review-scope.md)'s "Failure state, retry safety, and
  recovery" base reasoning.
- **Idempotency boundaries** — whether an idempotency key, dedup check, or
  exactly-once assumption actually holds at every entry point that can
  trigger the operation, or only at the one the diff directly touches.
- **Concurrent interleavings** — every plausible interleaving of two or
  more executions over the same shared mutable state that could violate
  an invariant the code assumes holds, bounded per "Cascading activation"
  below.
- **Ownership/coordination assumptions** — which component, process, or
  lock is assumed to own coordination of a shared resource, and whether
  that assumption still holds given every caller/component that can
  reach the resource.
- **Partial failure** — whether a multi-step operation leaves the system
  in a consistent, recoverable state when it fails or is interrupted
  partway through, rather than only reasoning about full success or full
  failure.
- **Other concurrency/distributed-system-adjacent concerns** the
  activated concern's own evidence surfaces, reasoned about with the same
  evidence bar as the areas above — this list is representative of the
  capability's scope, not an exhaustive checklist run unconditionally on
  every activation.

## Cascading activation: bounded by the existing expansion contract

Tracing an interleaving, a retry interaction, or a coordination chain
across components reuses
[`specialist-depth.md`](specialist-depth.md)'s cascading-activation model,
which in turn reuses
[`repository-expansion.md`](repository-expansion.md)'s fixed trigger/ring/
ceiling procedure and
[`review-stopping-criteria.md`](review-stopping-criteria.md)'s stop
conditions — never a separate, unbounded audit of every caller in the
repository. "Insufficient evidence" remains a valid terminal outcome for
a traced path, exactly as it is for base reasoning.

## Findings: ordinary findings, labeled

A finding this capability contributes is an ordinary finding: the same
severity derivation ([`severity.md`](severity.md)), the same evidence bar
([`evidence.md`](evidence.md)), the same identity/deduplication rules, and
the same remediation-scope-boundary reasoning
([`remediation-scope-boundary.md`](remediation-scope-boundary.md)) as any
other finding. It additionally carries the optional `capability` provenance
field, valued `distributed-systems-deepening`, per
[`finding.md`](../templates/finding.md), "Capability provenance" — never a
severity input, never a second schema. Concrete evidence must be tied to
the actual interleaving, retry path, or coordination flow the capability
traced; generic distributed-systems advice with no traced flow in this
change does not meet the evidence bar and is not reported.

## Worked examples

- **Engages — retry interaction.** A payment-capture handler is invoked by
  an at-least-once message queue. Base reasoning identifies the
  retryable-delivery concern. Evidence shows a second, existing caller
  also invokes the same capture path directly during a synchronous
  checkout flow, without going through the queue's dedup key. This
  capability traces both paths and reports the synchronous caller as the
  one that can double-capture on redelivery — the actual defect, not the
  new queue consumer that prompted the review.
- **Engages — concurrent interleaving.** An inventory count is read,
  compared against a requested quantity, and decremented in a separate
  write. Base reasoning flags the shared-state read→decide→write pattern.
  This capability traces whether more than one request handler can reach
  the same count concurrently and, if so, whether the read-decide-write
  sequence is protected by a transaction, lock, or atomic operation, or
  only appears safe because of request volume assumptions.
- **Does not engage — bounded base reasoning already suffices.** A
  counter increment is rewritten to use the database's native atomic
  increment operation, with a single caller and no other writer of the
  same row. Base reasoning confirms the invariant holds within its own
  bounded investigation; no further tracing is warranted, and this
  capability does not engage.
- **Misleading superficial signal.** A file named `queue_consumer.py`
  changes only a log message and a metric tag, with no change to
  message handling, retry behavior, or shared state. File name alone
  does not activate this capability; base reasoning finds no material
  concurrency/distributed-system signal, and this capability does not
  engage.
- **Implication without the expected file/path.** Application code in an
  unrelated module begins caching a value in a process-local variable
  that a different, already-scaled-out component reads under the
  assumption it is authoritative — no file conventionally associated
  with "queue," "lock," or "concurrency" is touched. Semantic evidence of
  the shared-state concern still activates base reasoning and, given the
  cross-component interleaving ambiguity, this capability.
- **Depth vs. remediation scope.** Tracing a coordination assumption
  surfaces a legitimate architectural P2: the resource would ideally be
  owned by a single coordinating service rather than negotiated ad hoc by
  each caller. The finding is reported at its evidenced severity;
  [`remediation-scope-boundary.md`](remediation-scope-boundary.md), not
  the depth of this capability's analysis, governs whether that broader
  redesign is required now or surfaced as a `Follow-up`.

## Non-goals and ownership boundary

- **No formal verification or trace analysis.** This capability performs
  the same kind of evidence-based code reasoning as the rest of review —
  it does not invoke, wrap, or depend on a model checker, formal
  verification tool, or distributed trace analyzer.
- **Not a generic checklist over every shared-state operation or message
  handler.** It never runs an unconditional maximum-depth analysis of
  every shared-state read/write or every message handler in the
  repository; it deepens investigation of a concern base reasoning
  already identified as materially implicated by the current change,
  nothing broader.
- **Does not redefine base concurrency/distributed-system detection.**
  Whether a change implicates a concurrency/distributed-system concern at
  all remains [`review-scope.md`](review-scope.md)'s unconditional
  obligation (per #211); this capability does not become the mechanism
  that decides that, and that detection does not start existing only
  once this capability engages.
- **Does not redefine composition, cascading, or remediation-scope
  semantics.** Those remain owned by
  [`specialist-depth.md`](specialist-depth.md),
  [`repository-expansion.md`](repository-expansion.md) /
  [`review-stopping-criteria.md`](review-stopping-criteria.md), and
  [`remediation-scope-boundary.md`](remediation-scope-boundary.md)
  respectively.
- **No new finding/severity/evidence schema.** The `capability`
  provenance field is the only addition, and it is never a severity
  input — see [`finding.md`](../templates/finding.md), "Capability
  provenance."
