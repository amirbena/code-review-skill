# Database / Migration Deepening Regression Fixture Corpus

Repository-development artifact for GitHub Issue
[#186](https://github.com/amirbena/code-review-skill/issues/186), a
deterministic fixture corpus for the Database / Migration deepening
capability tracked by parent Issue
[#179](https://github.com/amirbena/code-review-skill/issues/179) and its
own parent, the adaptive specialist-depth composition contract
[#82](https://github.com/amirbena/code-review-skill/issues/82). This is a
**focused sub-corpus** of [`benchmark-case/v2`](../../../../runtime_platform/benchmark/fixture-format.md)
fixtures pinning representative Database / Migration deepening outcomes
as follow-up quality hardening — it validates domain correctness after
the capability exists and does not define, gate, or redesign it. The
capability itself is designed and packaged in
[`../../../../shared/policies/database-migration-deepening.md`](../../../../shared/policies/database-migration-deepening.md),
which this corpus's expectations must stay consistent with.

GitHub Issue [#279](https://github.com/amirbena/code-review-skill/issues/279)
extended this corpus with representative non-relational fixtures after
generalizing the capability's own wording to be storage-model agnostic
(see the capability doc's "Concern areas" and "Worked examples"); the six
original relational fixtures are unchanged in substance and remain the
corpus's relational instantiation, not its default.

Every case conforms to [`../../fixture-format.md`](../../../../runtime_platform/benchmark/fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of [`../`](../README.md)
and [`../../`](../../../../runtime_platform/benchmark/README.md) this is **not** packaged into either
Skill archive and no packaged Skill resource depends on it — it is
consumed only by this repository's own test suite, through the single
reference validator
[`../../../../runtime_platform/benchmark/reference/benchmark_fixture.py`](../../../../runtime_platform/benchmark/reference/benchmark_fixture.py)
(never a second one). The original six cases are each expressed as a
Django migration (`django.db.migrations`); the three cases #279 added
are expressed against DynamoDB (`boto3`) and MongoDB (`pymongo`) instead,
matching the storage model each case's own worked example pins.

## Selection principle

**One case per outcome shape** #186's (and #279's) scope requires, each
isolating that shape so a regression in any one is unambiguous. The nine
cases mirror
[`database-migration-deepening.md`](../../../../shared/policies/database-migration-deepening.md)'s
own worked examples, concern areas, and Activation section, and split
between "the capability engages and finds a real defect" and "the
capability correctly stays quiet":

- **Destructive migration** — a migration drops a column outright with
  no deprecation period, on a table the model's own docstring documents
  as live and actively written, while a sibling module still reads the
  dropped column. Flagged.
- **Unsafe online migration** — a migration builds a UNIQUE index
  without `CONCURRENTLY` against a table documented as large and under
  sustained write load, so the non-concurrent build's `ACCESS EXCLUSIVE`
  lock blocks all reads and writes for its duration. Flagged.
- **Nullable-to-non-null without backfill** — an existing nullable
  column is tightened to `NOT NULL` with no backfill step and no
  default, while the model's own docstring documents that rows predating
  the column were never populated. Flagged.
- **Expand/contract done safely** — a new column is added nullable, a
  batched/idempotent/resumable backfill migration follows it, `save()`
  already dual-writes both columns, and the old column's removal is
  correctly deferred to a later migration rather than attempted here;
  the domain is implicated and the capability traces the sequencing and
  backfill, confirming both hold. `clean`.
- **Additive nullable column** — mirrors the capability doc's own "does
  not engage" worked example: a new, nullable column with no default, no
  backfill, no constraint, and a single application version reading it
  defensively. Base reasoning already suffices. `clean`.
- **Comment/formatting-only migration edit** — mirrors the capability
  doc's own "Misleading superficial signal" worked example: a file under
  `migrations/` changes only comments and the migration's own
  documentation, with the schema operation itself byte-for-byte
  unchanged; file location alone does not activate the capability.
  `clean`.
- **DynamoDB GSI/access-pattern evolution (#279)** — a new Global
  Secondary Index is added to support a new access pattern, the handler
  serving that pattern queries only the new index, and no backfill step
  or dual-read fallback exists for items written before the index was
  added, so they silently never appear in the new access pattern.
  Mirrors the capability doc's "Engages — DynamoDB GSI/access-pattern
  evolution" worked example. Flagged.
- **MongoDB document-shape evolution (#279)** — a field is renamed in a
  document collection, application code reads and writes only the new
  field name, and no document-migration script or dual-read fallback
  exists for documents still holding the old field name. Mirrors the
  capability doc's "Engages — MongoDB document-shape evolution" worked
  example, the document-store counterpart to the existing relational
  column-rename fixture. Flagged.
- **DynamoDB conditional-write fix, no data-model evolution (#279)** — a
  missing `ConditionExpression` optimistic-lock check is added to an
  existing update; no attribute, index, or item shape is added, removed,
  or changed, and no backfill or coexistence question is raised. Mirrors
  the capability doc's "Does not engage — ordinary NoSQL correctness, no
  data-model evolution" worked example: the required NoSQL negative case
  proving DynamoDB involvement alone is not activation evidence. `clean`.

The three original `clean` cases are deliberately distinct from each other, the
same discipline the precedent Security and Distributed Systems deepening
corpora use for their own three "stays quiet" reasons: the
comment-only-edit case fails Activation condition 1 (no schema-evolution
content exists at all to reason about), the additive-nullable-column
case satisfies condition 1 but fails condition 2 (the domain is
implicated but the evidence does not warrant deeper tracing — bounded
base reasoning already suffices), and the expand/contract case satisfies
both conditions and the capability *does* trace it, but confirms the
sequencing and backfill are already safe — so a regression in any one of
the three distinct "stay quiet" reasons is caught even if the other two
stayed correct. The DynamoDB negative case #279 added follows the same
discipline against a fourth storage model: it fails Activation condition
2 for a distinct reason again — the domain is implicated (a stored item
is updated) but the evidence shows only an ordinary correctness fix with
no data-model evolution signal at all.

Each of the six original cases is a crafted, self-contained
Django-migration patch (`input.patch` + `input.base`); the three #279
added are crafted, self-contained DynamoDB (`boto3`) or MongoDB
(`pymongo`) patches in the same shape — keeping the corpus runnable
without network access and consistent with the other corpora under
[`../`](../README.md). Per Issue #186's non-goals, this corpus contains
no cross-domain composition fixture (that is
[#85](https://github.com/amirbena/code-review-skill/issues/85)'s job,
reusing this corpus) and adds no new severity/evidence semantics.

## Cases

| File | Outcome shape | A correct review must… | Decision |
|---|---|---|---|
| [`database-migration-deepening-destructive-drop-column.yaml`](database-migration-deepening-destructive-drop-column.yaml) | destructive migration on a live, referenced table | report one **P1**: dropping `legacy_email` breaks `UserSerializer`, which still reads it, on a table documented as live and actively written (an optional missing-migration-test note is also acceptable) | `changes-required` |
| [`database-migration-deepening-unsafe-online-blocking-lock.yaml`](database-migration-deepening-unsafe-online-blocking-lock.yaml) | unsafe online migration / blocking lock on a large table | report one **P1**: a non-concurrent `CREATE UNIQUE INDEX` takes an `ACCESS EXCLUSIVE` lock on a table documented as ~50M rows under sustained write load (an optional missing-migration-test note is also acceptable) | `changes-required` |
| [`database-migration-deepening-nullable-to-non-null-no-backfill.yaml`](database-migration-deepening-nullable-to-non-null-no-backfill.yaml) | nullable-to-non-null transition with no backfill | report one **P1**: `subscription_tier` is tightened to `NOT NULL` with no backfill, while existing rows are documented as still holding `NULL` (an optional missing-migration-test note is also acceptable) | `changes-required` |
| [`database-migration-deepening-expand-contract-safe-clean.yaml`](database-migration-deepening-expand-contract-safe-clean.yaml) | expand/contract sequenced and backfilled safely | report **nothing required** — the capability traces the sequencing and backfill and confirms both hold (an optional note on backfill-interruption test coverage is also acceptable) | `clean` |
| [`database-migration-deepening-additive-nullable-column-clean.yaml`](database-migration-deepening-additive-nullable-column-clean.yaml) | additive nullable column, no deeper tracing warranted | report **nothing** — base reasoning already suffices | `clean` |
| [`database-migration-deepening-comment-only-edit-not-implicated-clean.yaml`](database-migration-deepening-comment-only-edit-not-implicated-clean.yaml) | migration file touched with no schema-evolution content | report **nothing** — the domain is not materially implicated | `clean` |
| [`database-migration-deepening-dynamodb-gsi-backfill-missing.yaml`](database-migration-deepening-dynamodb-gsi-backfill-missing.yaml) | DynamoDB GSI added with no backfill for pre-existing items | report one **P1**: `list_orders_by_status` queries the new `status-index` GSI, which is sparse on the newly introduced `status` attribute — pre-existing orders that never had `status` set are excluded regardless of DynamoDB's automatic index backfill — and no step populates `status` on them and no fallback exists (an optional missing-migration-test note is also acceptable) | `changes-required` |
| [`database-migration-deepening-mongodb-document-shape-rename.yaml`](database-migration-deepening-mongodb-document-shape-rename.yaml) | MongoDB document field renamed with no coexistence handling | report one **P1**: `get_shipping_address`/`set_shipping_address` read and write only the renamed `shippingAddress` field, with no document-migration script or fallback for existing documents or a still-running previous application version still using `mailingAddress` (an optional missing-migration-test note is also acceptable) | `changes-required` |
| [`database-migration-deepening-dynamodb-conditional-write-no-data-model-change-clean.yaml`](database-migration-deepening-dynamodb-conditional-write-no-data-model-change-clean.yaml) | DynamoDB conditional-write correctness fix, no data-model evolution | report **nothing** — an ordinary optimistic-lock fix with no attribute/index/shape change; DynamoDB involvement alone is not activation evidence | `clean` |

Per-case provenance and a one- or two-sentence rationale also live in
each fixture's `metadata` block (`source`, `tags`, `rationale`) and in
the header comment.

## Validation

[`../../../../tests/unit/benchmark/test_database_migration_deepening_corpus.py`](../../../../tests/unit/benchmark/test_database_migration_deepening_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../runtime_platform/benchmark/reference/benchmark_fixture.py`](../../../../runtime_platform/benchmark/reference/benchmark_fixture.py)
used for the worked example and every other corpus. It never defines a
second one, and asserts: the sub-corpus stays small and documented;
every required outcome shape is present; every case pins an explicit
`decision` consistent with its required findings; every flagged case's
required finding is `P1`; every strictly clean case carries no findings
at all; and every finding's anchor resolves inside its own case's patch
or base. Matching a reviewer's output to these expectations and scoring
it are out of scope here (Issues #41 / #52 / #54). Peer review of the
expected findings themselves happens on the pull request.
