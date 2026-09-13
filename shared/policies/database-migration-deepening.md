# Shared Policy — Database / Migration Deepening Capability

Applies identically to `local-code-review` and `github-pr-review`, in every
invocation mode. It is a **domain-specific deepening capability** under
[`specialist-depth.md`](specialist-depth.md)'s composition contract: bounded,
evidence-driven investigation of a schema-evolution/migration concern once
base review has already identified, per
[`review-scope.md`](review-scope.md)'s "Data / persistence" dimension, that
a change materially implicates one.

This capability never decides whether a schema-evolution/migration concern
is considered at all — that is base reasoning's unconditional obligation,
owned by [`review-scope.md`](review-scope.md) (per #211) and never
redefined here. It answers only the next question, per
[`specialist-depth.md`](specialist-depth.md): given a data/persistence
concern base reasoning already identified, does the available evidence
justify tracing it further than base reasoning's own bounded pass affords.

## The gap this closes

Base persistence reasoning ("Data / persistence" in
[`review-scope.md`](review-scope.md)) already asks, for a schema,
migration, stored representation, or the durable shape of data written or
read by the change, whether read/write compatibility with existing stored
data and existing readers/writers is preserved — within that base pass's
own bounded investigation. What it cannot always afford on every change is
*exhaustive* tracing: whether a migration is safe to apply online against a
large, actively written table, whether a backfill's own transactional and
locking behavior is sound, whether an expand/contract sequence actually
keeps old and new application versions coexisting correctly across every
deploy stage, whether a rollback of the migration or the application code
alone would leave the system in a consistent state, or whether a large data
movement stays within the transactional and locking bounds the surrounding
system can tolerate. This capability is that deeper pass, engaged only when
the evidence already gathered shows it is warranted.

## Activation

Engages only when both hold:

1. [`review-scope.md`](review-scope.md)'s base pass has already
   identified a materially implicated **Data / persistence** dimension for
   the current change; and
2. the evidence gathered by that base pass — not the file type, path,
   migration-tool name, or a keyword in a name — indicates the change's
   full correctness cannot be established within base reasoning's own
   bounded investigation: the migration is applied against a table whose
   size or write volume makes locking/rewrite behavior material, a column
   or constraint transition (nullable-to-non-null, type change, new
   uniqueness/foreign-key constraint) requires existing rows to be
   reconciled, a backfill or large data movement is involved, more than
   one application version must read or write the schema across the
   rollout window, rollback of the migration or the deploying application
   depends on an assumption the base pass could not confirm, or the
   migration's transactional boundaries determine whether a partial
   failure leaves the schema or data in an inconsistent state.

A change that touches a migrations directory, a file whose name suggests
schema relevance, or a specific migration framework does not by itself
satisfy condition 2 — per [`specialist-depth.md`](specialist-depth.md),
those are signals, never independently sufficient. Conversely, a change
with no file conventionally associated with migrations can still satisfy
both conditions when its semantic evidence shows a persisted-state
evolution or rollout-coexistence concern (see worked examples below).

## Concern areas

Within an activated data/persistence concern, this capability deepens
investigation of:

- **Destructive and online migrations** — whether a migration that drops,
  renames, or narrows a column/table/constraint is safe to apply while the
  table is live and written to, and whether the change is reversible or
  the diff's own evidence shows the loss is deliberate and accounted for.
- **Backfills** — whether a backfill that populates existing rows for a
  new or changed column runs within transactional and locking bounds the
  surrounding table's size and write volume can tolerate, and whether it
  is idempotent/resumable if interrupted partway through.
- **Nullable-to-non-null transitions** — whether existing rows are
  actually guaranteed to satisfy the new constraint before or at the point
  it is enforced, and what happens to a row written concurrently with the
  transition.
- **Expand/contract sequencing** — whether a schema change that must be
  deployed in stages (add the new shape, migrate/dual-write, remove the
  old shape) is actually sequenced so that no stage requires application
  code that does not yet exist, or removes something a still-running
  application version still depends on.
- **Old/new application coexistence** — whether the schema, at every point
  in the rollout window, remains simultaneously valid for both the
  previous and the new application version that can be running against
  it, not only the version the diff was written against.
- **Rollback safety** — whether rolling back the migration alone, the
  application alone, or both together leaves the system in a state that
  is consistent and does not silently lose or corrupt data written under
  the new shape.
- **Locking and table rewrites** — whether a schema operation requires a
  lock or full table rewrite whose duration or blocking behavior is
  material given the table's actual size and concurrent access pattern.
- **Large data movement** — whether a migration or accompanying script
  that moves, copies, or transforms a materially large volume of data is
  batched, bounded, and resumable, rather than a single unbounded
  operation.
- **Transactional boundaries** — whether the migration's own
  transaction(s) group related schema/data changes correctly, and whether
  a failure partway through leaves a partially-applied, inconsistent
  state rather than cleanly rolling back or resuming.
- **Other schema-evolution/migration-adjacent concerns** the activated
  concern's own evidence surfaces, reasoned about with the same evidence
  bar as the areas above — this list is representative of the
  capability's scope, not an exhaustive checklist run unconditionally on
  every activation.

## Unrecognized tooling or dialect

When the migration tooling or database dialect involved is not one this
capability can reason about with confidence from the evidence available —
an unfamiliar migration framework, a vendored/generated migration, or SQL
whose dialect-specific locking and transactional behavior cannot be
established from the diff and surrounding repository context — this
capability does not speculate about that tool's or dialect's specific
locking, online-DDL, or transactional guarantees. It reports only what the
available evidence actually supports, or, where no concrete evidence
supports a finding, it produces no finding for that concern rather than an
invented one. This mirrors "insufficient evidence" remaining a valid
terminal outcome under "Cascading activation" below.

## Cascading activation: bounded by the existing expansion contract

Tracing a rollout stage, a coexistence assumption, or a large data
movement's downstream effect reuses
[`specialist-depth.md`](specialist-depth.md)'s cascading-activation model,
which in turn reuses
[`repository-expansion.md`](repository-expansion.md)'s fixed trigger/ring/
ceiling procedure and
[`review-stopping-criteria.md`](review-stopping-criteria.md)'s stop
conditions — never a separate, unbounded audit of every migration or table
in the repository. "Insufficient evidence" remains a valid terminal outcome
for a traced path, exactly as it is for base reasoning.

## Findings: ordinary findings, labeled

A finding this capability contributes is an ordinary finding: the same
severity derivation ([`severity.md`](severity.md)), the same evidence bar
([`evidence.md`](evidence.md)), the same identity/deduplication rules, and
the same remediation-scope-boundary reasoning
([`remediation-scope-boundary.md`](remediation-scope-boundary.md)) as any
other finding. It additionally carries the optional `capability` provenance
field, valued `database-migration-deepening`, per
[`finding.md`](../templates/finding.md), "Capability provenance" — never a
severity input, never a second schema. Concrete evidence must be tied to
the actual migration, rollout stage, or data movement the capability
traced; generic database style advice with no traced schema-evolution risk
in this change does not meet the evidence bar and is not reported.

## Worked examples

- **Engages — online migration against a live table.** A migration adds a
  `NOT NULL` column to a table with high write volume and no default
  value. Base reasoning identifies the schema change. Evidence shows
  existing rows will not satisfy the new constraint and no backfill step
  exists in the diff. This capability traces the rollout and reports the
  missing backfill/default as the defect that will make the migration fail
  or block writes when applied.
- **Engages — old/new application coexistence.** A column is renamed in
  one migration, and the application code in the same change reads only
  the new name. Base reasoning flags the schema/stored-representation
  change. This capability traces whether a previous application version
  still running during a rolling deploy would fail against the renamed
  column, and reports the missing expand/contract staging.
- **Does not engage — bounded base reasoning already suffices.** A new,
  nullable column with no default is added to a table, with no backfill,
  no constraint, and a single application version reading it. Base
  reasoning confirms read/write compatibility holds within its own bounded
  investigation; no further tracing is warranted, and this capability does
  not engage.
- **Misleading superficial signal.** A file under `migrations/` changes
  only a comment or a migration's descriptive name, with no change to the
  schema operation, data movement, or transactional behavior it performs.
  File location alone does not activate this capability; base reasoning
  finds no material schema-evolution signal, and this capability does not
  engage.
- **Implication without the expected file/path.** Application code in an
  unrelated module changes the shape of a value serialized into a JSON
  column or cache entry that is treated as a durable, shared format across
  services — no file conventionally associated with "migration" or
  "schema" is touched. Semantic evidence of the persisted-state evolution
  still activates base reasoning and, given the coexistence ambiguity,
  this capability.
- **Unrecognized tooling — fails safe.** A migration is expressed through
  an in-house or unfamiliar schema-management tool whose locking and
  online-DDL behavior cannot be established from the diff or repository
  context. This capability does not assert that the operation is safe or
  unsafe online; it reports only what the available evidence actually
  supports, or nothing for that concern.
- **Depth vs. remediation scope.** Tracing a backfill's transactional
  boundaries surfaces a legitimate architectural P2: the backfill would
  ideally be extracted into a resumable, batched background job rather
  than run inline in the migration. The finding is reported at its
  evidenced severity; [`remediation-scope-boundary.md`](remediation-scope-boundary.md),
  not the depth of this capability's analysis, governs whether that
  broader rework is required now or surfaced as a `Follow-up`.

## Non-goals and ownership boundary

- **No migration execution or database connection.** This capability
  performs the same kind of evidence-based code reasoning as the rest of
  review — it does not execute a migration, connect to a database, or
  invoke a migration tool's dry-run/plan mode.
- **Not a generic ORM/query style linter.** It never runs an unconditional
  checklist of ORM or query style preferences unrelated to
  schema-evolution or migration risk; it deepens investigation of a
  data/persistence concern base reasoning already identified as
  materially implicated by the current change, nothing broader.
- **Migration-file presence alone is not sufficient.** A changed migration
  file does not by itself trigger maximum-depth analysis; activation
  requires the base pass's own evidence of material schema-evolution or
  migration risk, per "Activation" above.
- **Does not redefine base data/persistence detection.** Whether a change
  implicates a data/persistence concern at all remains
  [`review-scope.md`](review-scope.md)'s unconditional obligation (per
  #211); this capability does not become the mechanism that decides that,
  and that detection does not start existing only once this capability
  engages.
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
