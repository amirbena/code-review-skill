# Shared Policy — Specialist-Depth Composition

Applies identically to `local-code-review` and `github-pr-review`, in every
invocation mode. It owns the composition contract for **domain-specific
deepening capabilities** — how a reviewer decides, for a dimension
["Semantic change-implication reasoning"](review-scope.md#semantic-change-implication-reasoning)
has already identified as materially implicated, whether the evidence
gathered justifies going further with domain-specific reasoning, and how
0..N such deepenings compose into one review.

This is the domain-specific-deepening sub-domain of
[`review-scope.md`](review-scope.md), which owns base review scope and
routes here. It builds on the base per-dimension obligation that section
defines and never redefines it; it reuses
[`repository-expansion.md`](repository-expansion.md)'s bounded-expansion
and stop-condition contract for cascading activation rather than defining
a second one; and it reuses
[`remediation-scope-boundary.md`](remediation-scope-boundary.md)'s
remediation-required / remediation-scope-boundary reasoning rather than
letting review depth alone expand it. It introduces no second scope model,
no second evidence standard, and no new finding/severity/evidence schema.

## The gap this closes

Base semantic reasoning ([`review-scope.md`](review-scope.md)) already
performs the minimum bounded reasoning for every materially implicated
dimension on every review, unconditionally — no risk domain is opt-in.
What it leaves open is depth: some implicated concerns are fully resolved
by that bounded reasoning, and some genuinely need domain expertise to
reason correctly — an online schema migration's backfill/coexistence
risk, a query's cardinality behavior under real data volume, a
distributed-system's failure-mode interaction. Without an explicit
contract for *when* that deeper reasoning is warranted and *how* it
composes, either every implicated dimension gets shallow treatment
regardless of stakes, or deepening becomes an ad hoc, file-type-routed
switch that runs even when nothing warrants it (or fails to run when
something does, because the file type didn't match). This policy makes
that judgment explicit, evidence-driven, and composable instead of
reviewer-by-reviewer.

## Terminology

Use **domain-specific deepening capability**, **specialist-depth
capability**, or **adaptive deepening**. Do not use "selectable profile,"
"selected profile," or "reviewer persona" — the model is not a persona
system: there is no user-facing selector, no persistent activation state,
and no independent reviewer verdict per capability. Use "profile" only
when referring to a historical name or an existing path that still
literally uses the term.

## What this is not

This policy defines a reasoning/composition contract, not a runtime
plugin engine. It does not require, and implementation must not add
without the current architecture demonstrably needing it:

- a generic plugin registry;
- a deterministic file/path → specialist router;
- an external orchestration service;
- a new agent per domain;
- persistent activation state;
- a user-facing specialist selector.

The host reviewer performs the deeper reasoning itself, according to this
capability contract.

## Activation: evidence-driven, never routed

File type, path, framework, language, and dependency name are signals
only. None is independently sufficient to require or suppress
domain-specific deepening — the same rule "Evidence is semantic, not
structural" already applies to base-dimension activation, applied one
level deeper here.

Worked contrast:

- `*.sql` is not equivalent to "run database specialist depth." A
  schema/persisted-state change first feeds base persistence reasoning
  (["Semantic change-implication reasoning"](review-scope.md)); only when
  that reasoning's own evidence shows meaningful rollout, backfill, or
  coexistence complexity does database deepening become warranted.
- Conversely, database implications can arise from application code that
  touches no `.sql` file and no migration directory at all — an
  in-memory cache whose entry shape changes, an ORM model whose
  serialized representation changes, a queue message whose persisted
  schema changes. Semantic evidence of a persisted-state implication
  triggers the same deepening decision regardless of file type.

## Conditional loading: fail-closed

This capability — this file and the four domain deepening policies it
composes — loads only once the activation predicate above has already
been decided; it is never opened as a precondition to deciding it. The
predicate is decidable entirely from material
[`review-scope.md`](review-scope.md)'s base pass already produces while
resident — a dimension "Semantic change-implication reasoning" has
materially implicated, plus that dimension's own base-pass evidence
indicating deeper reasoning is warranted, per that dimension's stated
depth-owner trigger — so evaluating it never requires opening this file
or any of the four deepening policies.

Loading is fail-closed: if evaluating the predicate is unclear,
incomplete, or fails for any reason, this capability (and the applicable
deepening policy) loads anyway. Ambiguity resolves to load, never to
skip — the same convention already governing
`review-action-authorization.md` ("Ambiguity fails closed to
`PASSIVE`") and [`runtime-validation.md`](runtime-validation.md) (no
verified isolation ⇒ `unavailable`). A capability boundary that a failed
or ambiguous predicate evaluation could silently bypass is the one
catastrophic-if-wrong outcome this contract exists to prevent; this
file's activation predicate must never be able to produce that outcome.

Not loading this capability never gates, narrows, or substitutes for the
base per-dimension obligation
["Semantic change-implication reasoning"](review-scope.md#semantic-change-implication-reasoning)
performs unconditionally — that pass always runs regardless of whether
this file is ever opened. Conditional loading changes only when this
file and its composed deepening policies are consulted, never whether a
dimension is considered.

This conditional-loading contract is scoped to this capability alone; it
does not define, and must not be read as defining, a general
loading/routing mechanism for any other capability in this repository.

## Composition: 0..N capabilities, one review

A review may require zero, one, or several domain-specific deepening
capabilities. When more than one materially implicated dimension warrants
deepening, the relevant capabilities compose into **one** review — they
never produce independent reviewer verdicts, independent severity scales,
or independent output schemas. Every finding a capability contributes
still passes through the same shared finding, evidence, severity,
decision-derivation, and remediation-scope-boundary contracts as any
other finding, and remains identifiable as ordinary review output — not
as a separate persona's report.

### Capability-contributed findings are labeled, not re-schemed

A finding a domain-specific deepening capability contributes is an
**ordinary finding** — same fields, same severity derivation, same
evidence bar, same identity/deduplication rules. The one thing it
additionally carries is attribution: the optional `capability` provenance
field on the shared finding contract (see
[`finding.md`](../templates/finding.md), "Capability provenance"), naming
which capability's deeper reasoning contributed to it. Like `contextual
evidence` and `runtime validation`, it is a provenance annotation only —
it never calculates, raises, lowers, or overrides severity, and never
changes a finding's identity, deduplication, or the decision derivation.
It is absent on a finding base reasoning alone already fully supports. A
capability that finds nothing beyond what base reasoning already
established contributes no additional finding merely to prove it ran.

## Cascading activation: bounded by the existing expansion contract

A deepening pass may itself surface evidence that materially implicates a
further dimension (e.g., database deepening uncovers a query fan-out
whose cardinality raises a performance concern). That further dimension
may then warrant its own deepening — but this is evidence-driven
continuation of the same bounded-expansion model, not a second expansion
mechanism and not recursive "specialist calls specialist" machinery.
Cascading deepening reuses
[`repository-expansion.md`](repository-expansion.md)'s fixed
trigger/ring/ceiling procedure and
[`review-stopping-criteria.md`](review-stopping-criteria.md)'s coverage
and stop conditions exactly as the base review does elsewhere; it
introduces no new ceiling, no new trigger catalog, and no way to bypass
those stop conditions.

## Orthogonality to remediation scope

Deeper domain-specific reasoning may strengthen a finding's evidence,
surface additional findings, or justify a different severity for a
finding within its domain. The fact that reasoning went deeper must
never, by itself, expand what the current task/PR is required to remediate.
Whether remediation is required at all, and how much of it belongs inside
the current change's boundary versus separate follow-up work, remains
governed exclusively by
[`remediation-scope-boundary.md`](remediation-scope-boundary.md)'s
three-part reasoning sequence — unchanged and not restated here. A
capability may legitimately conclude, through that same contract/evidence
reasoning, that broader remediation is genuinely required; that
conclusion must come from the finding's own evidence and contract, never
from the depth or sophistication of the analysis that produced it. This
distinction matters in particular ahead of introducing database,
performance, security, and distributed-system deepening capabilities,
where deeper analysis routinely surfaces legitimate but architecturally
broad concerns.

## Explicit user focus: additive only

A user may request deeper focus in a named domain (for example, "focus
especially on database migration safety"). That request may raise depth
in that domain immediately. It must never:

- narrow the base review's per-dimension obligation;
- suppress other materially implicated dimensions the reviewer
  independently discovers;
- lower the evidence bar a finding must clear;
- change severity or remediation-scope-boundary semantics.

Explicit focus is an override on depth, not the activation mechanism —
without it, activation still proceeds from evidence alone, per the rule
above.

## Worked examples

- **Case A — no deepening.** A change materially implicates performance
  (a newly introduced per-request allocation), but base reasoning's
  bounded per-dimension pass fully resolves whether it stays within
  reasonable bounds at the volume the surrounding code is actually
  exercised with. No domain-specific deepening engages; the review
  remains complete at base depth.
- **Case B — one deepening capability.** A migration adds a `NOT NULL`
  column to a large, actively written table. Base persistence reasoning
  identifies the schema change; its own evidence (table size, write
  volume, absence of a default/backfill step) shows meaningful online
  rollout/backfill/coexistence risk. Database/migration deepening
  engages; its findings remain in the shared finding/severity model.
- **Case C — multiple capabilities.** The same persistence change also
  introduces a query whose evidence shows cardinality growing with the
  now-larger table. Both database and performance deepening may engage;
  they compose into one review, and neither suppresses or gates the
  other's findings.
- **Case D — misleading superficial signal.** A `.sql` file in the diff
  contains only test-fixture seed data with no production rollout path.
  File type alone does not force database deepening; base persistence
  reasoning finds no material rollout/backfill/coexistence signal, and
  deepening does not engage.
- **Case E — implication without the expected file type.** Application
  code changes the shape of values written into a cache or serialized
  into a queue message, with no `.sql` file or migration directory
  touched. Semantic evidence of a persisted-state implication still
  triggers base persistence reasoning and, if warranted by that
  evidence, database/persistence deepening — file type was never the
  gate.
- **Case F — cascading implication.** Database deepening on a schema
  change surfaces a query fan-out whose cardinality is now materially
  different. That evidence may warrant performance deepening as a
  second capability, bounded by
  [`repository-expansion.md`](repository-expansion.md)'s existing
  ring/ceiling procedure — not unbounded recursive specialist
  invocation.
- **Case G — depth vs. remediation scope.** Database deepening
  identifies a legitimate architectural P2: the migration strategy would
  ideally be reworked repository-wide. The finding remains valid and
  reported at its evidenced severity, but the deeper analysis that
  produced it does not by itself enlarge what the current change must
  fix — [`remediation-scope-boundary.md`](remediation-scope-boundary.md)
  still governs whether that broader work is required now or surfaced
  as a `Follow-up`.

## Non-goals and ownership boundary

- This policy never changes severity definitions, the mechanical blocking
  derivation, evidence standards, or finding identity/deduplication —
  those remain solely owned by [`severity.md`](severity.md),
  [`evidence.md`](evidence.md), and
  [`root-cause-consolidation.md`](root-cause-consolidation.md).
- This policy does not redefine
  [`review-scope.md`](review-scope.md)'s base per-dimension obligation:
  whether a dimension is considered at all is decided there,
  unconditionally, before this policy's activation question is ever
  asked.
- This policy does not redefine
  [`repository-expansion.md`](repository-expansion.md) or
  [`review-stopping-criteria.md`](review-stopping-criteria.md): cascading
  activation reuses their existing trigger catalog, ring procedure, and
  stop conditions rather than introducing a second expansion or stopping
  model.
- This policy does not redefine
  [`remediation-scope-boundary.md`](remediation-scope-boundary.md):
  review depth never substitutes for, widens, or shrinks that policy's
  three-part reasoning sequence.
- This policy does not implement individual domain capabilities (e.g.,
  database, performance, security, distributed-system deepening) — it
  defines the shared contract those capabilities compose under.
- No new user-facing invocation flag beyond the existing additive-only
  explicit-focus override. The activation decision is inferred from the
  finding's own evidence and repository context, the same way other
  review-scope judgments already are.
- Presentation options (`human_review_output` / `senior_mode` and related
  flags) may change how a capability's contribution is worded; they own
  none of this reasoning and never change which capabilities engage, per
  [`invocation-options.md`](invocation-options.md).
