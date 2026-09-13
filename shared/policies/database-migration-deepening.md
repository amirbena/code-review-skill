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
read by the change — whatever storage model the evidence establishes:
relational tables, document collections, key-value/wide-column items, or
anything else — whether read/write compatibility with existing stored
data and existing readers/writers is preserved — within that base pass's
own bounded investigation. What it cannot always afford on every change is
*exhaustive* tracing: whether a destructive or availability-affecting
change to a stored representation is safe to apply online against a
large, actively written table, collection, or partition; whether a
backfill's own consistency and atomicity behavior — a SQL migration's
transaction and locks, a DynamoDB backfill job's conditional writes, a
MongoDB field-migration script's per-document updates — is sound; whether
an expand/contract sequence actually keeps old and new application
versions coexisting correctly across every deploy stage; whether a
rollback of the migration or the application code alone would leave the
system in a consistent state; or whether a large data movement stays
within the consistency and throughput bounds the surrounding system can
tolerate. This capability is that deeper pass, engaged only when the
evidence already gathered shows it is warranted, reasoned about on
whatever storage model's actual primitives the evidence establishes
rather than assumed to be relational.

## Activation

Engages only when both hold:

1. [`review-scope.md`](review-scope.md)'s base pass has already
   identified a materially implicated **Data / persistence** dimension for
   the current change; and
2. the evidence gathered by that base pass — not the file type, path,
   migration-tool or ORM/ODM name, SDK/driver call, `.sql` extension, or a
   keyword in a name — indicates the change's full correctness cannot be
   established within base reasoning's own bounded investigation: a
   stored representation's evolution is applied against an item
   population, table, collection, or partition whose size or write volume
   makes the storage model's own locking, rewrite, or throttling behavior
   material; a field, column, or attribute's presence, type, or
   uniqueness/key constraint is tightened or narrowed in a way that
   requires existing stored items to be reconciled; a backfill or large
   data movement is involved, regardless of whether it runs as a
   migration script, a DynamoDB backfill job, or a MongoDB field-migration
   script; more than one application version must read or write the
   stored representation across the rollout window; rollback of the
   migration or the deploying application depends on an assumption the
   base pass could not confirm; or the storage model's own
   consistency/atomicity primitives — a SQL migration's transactional
   boundaries, a DynamoDB item's conditional-write/transaction semantics,
   a MongoDB operation's per-document or multi-document atomicity —
   determine whether a partial failure leaves the stored data in an
   inconsistent state.

A change that touches a migrations directory, a file whose name suggests
schema relevance, a specific migration/ORM/ODM framework or tool name, or
a NoSQL SDK/driver call does not by itself satisfy condition 2 — per
[`specialist-depth.md`](specialist-depth.md), those are signals, never
independently sufficient, whatever the storage model: a `.sql` file, a
Django/Alembic/Flyway migration, a `boto3`/DynamoDB SDK call, or a
`pymongo`/Mongoose call are each evidence only, never independently
sufficient for activation. Conversely, a change with no file
conventionally associated with migrations can still satisfy both
conditions when its semantic evidence shows a persisted-state evolution or
rollout-coexistence concern (see worked examples below), and ordinary use
of a NoSQL store — a query, a correctness fix scoped to a single
operation, routine CRUD — does not by itself satisfy condition 2 either
(see the "Does not engage" worked examples below).

## Concern areas

Within an activated data/persistence concern, this capability deepens
investigation of:

- **Destructive and online migrations** — whether an evolution of a
  stored representation that drops, renames, or narrows a field is safe
  to apply while it is live and actively read or written, and whether the
  change is reversible or the diff's own evidence shows the loss is
  deliberate and accounted for. Relational example: dropping a SQL
  column or table. Non-relational examples: removing a DynamoDB attribute
  or GSI a live access pattern still reads, or narrowing a MongoDB
  document field's shape or type.
- **Backfills** — whether populating existing stored items/rows for a new
  or changed field runs within the consistency and throughput bounds the
  surrounding item population's size and write volume can tolerate, and
  whether it is idempotent/resumable if interrupted partway through —
  regardless of whether that happens via a relational migration script, a
  DynamoDB backfill job, or a MongoDB field-migration script.
- **Nullable-to-non-null transitions**, generalized to any field or
  attribute's presence-or-shape guarantee tightening — whether existing
  stored items/rows are actually guaranteed to satisfy the tightened
  guarantee before or at the point it is enforced, and what happens to an
  item written concurrently with the transition. This applies equally to
  a SQL `NOT NULL` constraint, a DynamoDB attribute an access pattern now
  assumes is always present, or a MongoDB field an application now
  assumes is always set and correctly shaped.
- **Expand/contract sequencing** and **Old/new application coexistence**
  — whether a staged representation change (a new SQL column, a new
  DynamoDB GSI, a new MongoDB document shape) that must be deployed in
  stages (add the new shape, dual-read/dual-write or migrate, remove the
  old shape) is actually sequenced so that no stage requires application
  code that does not yet exist, or removes something a still-running
  application version still depends on — and whether the stored
  representation, at every point in the rollout window, remains
  simultaneously valid for both the previous and the new application
  version that can be running against it, not only the version the diff
  was written against.
- **Rollback safety** — whether rolling back the migration/evolution
  alone, the application alone, or both together leaves the system in a
  state that is consistent and does not silently lose or corrupt data
  written under the new shape.
- **Locking and table rewrites** and **Transactional boundaries**,
  generalized to a storage model's own locking, rewrite, and
  atomicity/consistency primitives — whether a storage operation requires
  a lock, full table/collection rewrite, or transaction whose duration,
  blocking behavior, or atomicity scope is material given the item
  population's actual size and concurrent access pattern, and whether a
  failure partway through a grouped change leaves the stored data
  partially applied and inconsistent rather than cleanly rolled back or
  resumed. Locking and table rewrites and transactional boundaries in
  their literal SQL sense **apply only where the evidence actually
  establishes a storage model with those properties** (e.g. a
  transactional SQL database). A storage model without SQL-style
  transactions or table-level locks — for example DynamoDB, whose
  correctness instead rests on per-item conditional writes and its own
  transaction/transact-write-item semantics — is reasoned about on its
  own consistency/atomicity primitives, never assumed to have locking or
  transactional guarantees it does not provide.
- **Large data movement** — whether a migration or accompanying script
  that moves, copies, or transforms a materially large volume of data is
  batched, bounded, and resumable, rather than a single unbounded
  operation, whatever the storage model.
- **Other persistence-evolution/migration-adjacent concerns** the
  activated concern's own evidence surfaces, reasoned about with the same
  evidence bar as the areas above and on whatever storage model's actual
  primitives the evidence establishes — this list is representative of
  the capability's scope, not an exhaustive checklist run unconditionally
  on every activation, and never a reason to assume relational semantics
  a non-relational store does not have.

## Unrecognized tooling or storage technology

When the migration tooling, ORM/ODM, or storage technology involved is not
one this capability can reason about with confidence from the evidence
available — an unfamiliar migration framework, a vendored/generated
migration, SQL whose dialect-specific locking and transactional behavior
cannot be established from the diff and surrounding repository context, or
a non-relational storage system whose consistency, atomicity, or
indexing/access-path guarantees cannot be established from the evidence —
this capability does not speculate about that tool's or storage system's
specific locking, online-DDL, transactional, or consistency guarantees. It
reports only what the available evidence actually supports, or, where no
concrete evidence supports a finding, it produces no finding for that
concern rather than an invented one. This mirrors "insufficient evidence"
remaining a valid terminal outcome under "Cascading activation" below.

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
- **Engages — MongoDB document-shape evolution.** A field is renamed and
  restructured in a MongoDB collection's document shape, and the
  application code in the same change reads and writes only the new
  shape. Base reasoning flags the stored-representation change under
  "Data / persistence." This capability traces whether documents already
  persisted under the old shape, or a still-running previous application
  version writing that old shape during a rolling deploy, are actually
  handled — mirroring the existing SQL column-rename worked example above
  — and reports the missing coexistence handling for old-shape documents
  as the defect.
- **Engages — DynamoDB GSI/access-pattern evolution.** A new Global
  Secondary Index is added to support a new access pattern, and the
  application code that serves that pattern reads only the new index.
  Base reasoning flags the stored-representation change. Existing items
  do not carry the new index's key attributes, so they will not appear
  in the new GSI until backfilled, and no backfill step or dual-read
  fallback exists in the diff. This capability traces the gap and
  reports that queries against the new access pattern will silently miss
  every item written before the index was added.
- **Does not engage — ordinary NoSQL correctness, no data-model
  evolution.** A DynamoDB update uses a conditional write
  (`ConditionExpression`) to guard against a race, and the change fixes a
  bug where the condition was missing an optimistic-lock check on a
  version attribute — no attribute, index, or document shape is added,
  removed, or changed, and no backfill or coexistence question is raised.
  This is an ordinary persistence-correctness concern DynamoDB happens to
  be involved in; it remains with base reasoning under
  [`review-scope.md`](review-scope.md), Activation condition 2 is not
  satisfied, and this capability does not engage. Using a NoSQL store is
  not, by itself, activation evidence.
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
- **Not a generic ORM/ODM/query style linter, for any storage model.** It
  never runs an unconditional checklist of ORM, ODM, or query/access-
  pattern style preferences unrelated to persistence evolution or
  migration risk — relational or otherwise; it deepens investigation of a
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
