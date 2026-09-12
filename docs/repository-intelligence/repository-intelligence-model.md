# Repository Intelligence Model

Repository-development design record for **[#129](https://github.com/amirbena/code-review-skill/issues/129)**.
Not packaged; explanatory. It is the canonical home for the candidate
architecture comparison, the typed entity/relationship model, retrieval
bounds, provenance, snapshot identity and staleness, and
relationship-influence attribution — the packaged
[`shared/policies/repository-expansion.md`](../../shared/policies/repository-expansion.md)
and [`shared/policies/evidence.md`](../../shared/policies/evidence.md)
reference this document by name and do not restate its model.

The test-only reference model is
[`../../tests/reference/review/repository_intelligence.py`](../../tests/reference/review/repository_intelligence.py);
its behavior is exercised by
[`../../tests/unit/review/test_repository_intelligence.py`](../../tests/unit/review/test_repository_intelligence.py)
and [`../../tests/policy/review/test_repository_intelligence_docs.py`](../../tests/policy/review/test_repository_intelligence_docs.py).
The benchmark evidence for the acceptance criterion "measurable gains over
diff-only review" is
[`../benchmark/corpus/repository-intelligence/README.md`](../benchmark/corpus/repository-intelligence/README.md),
exercised by
[`../../tests/unit/review/test_repository_intelligence_corpus.py`](../../tests/unit/review/test_repository_intelligence_corpus.py).

## 1. Problem and goal

Diff-only review can miss defects whose evidence lives in callers,
consumers, interfaces, or dependent symbols.
[`repository-expansion.md`](../../shared/policies/repository-expansion.md)
(#87) already defines **when** a review expands beyond the diff (a fixed
trigger catalog), and **how far** (a bounded ring ceiling scaled by
change-risk depth). It does not define **how the repository relationships
that a fired trigger points at are actually modeled, retrieved, or kept
honest** — what counts as an entity, what counts as a relationship, how a
retrieved relationship carries evidence, whether a stale index can silently
mislead a review, or how a finding can say which specific relationship made
it possible. This is that missing layer.

The goal is the **simplest** repository-intelligence model that yields
measurable review gains through targeted, relationship-aware context
retrieval — not generic retrieval-augmented review, not an organization
knowledge graph, and not a system that replaces Git as source of truth.

## 2. Where this sits relative to repository-expansion.md

[`repository-expansion.md`](../../shared/policies/repository-expansion.md)
(#87) stays canonical for:

- **when** expansion happens (a trigger fires or it does not);
- **which trigger** authorizes it (the fixed catalog: call-site,
  interface/contract, migration/schema, config-consumer);
- **how far** it may reach (the ring ceiling, scaled by `standard` /
  `elevated` / `deep` change-risk depth).

This document owns everything *inside* an authorized expansion:

- entity semantics — what is a file, module, class, function, or symbol;
- relationship semantics — what is a `calls`, `implements`, `references`,
  or `imports` edge, and which trigger surfaces each;
- bounded retrieval **within** the ring #87 already authorized — this
  model never re-derives or loosens the ceiling, it only makes what
  happens inside it inspectable;
- provenance — the source evidence a retrieved relationship carries;
- snapshot validity — whether the relationship data still describes the
  worktree under review;
- relationship-influence attribution — which retrieved relationship(s)
  materially enabled a specific finding.

Nothing here changes #87's trigger catalog, ring ceiling, or reporting
contract. A change with no fired trigger has nothing for this model to
retrieve, exactly as before.

## 3. Candidate architectures compared

| # | Candidate | Verdict |
| --- | --- | --- |
| 1 | **Heavyweight GraphRAG / persistent graph database** — ingest the whole repository into a vector- or graph-indexed store, kept live, queried generically. | **Rejected.** Explicitly out of the issue's Non-Goals. Disproportionate to a single-repository, diff-scoped, ring-bounded need; introduces persistence, infrastructure, and a real "is the store still accurate" problem this repository does not otherwise have. |
| 2 | **Full static-analysis project graph** — a whole-repository AST index or IDE/LSP-style cross-reference database, built once and kept live across reviews. | **Rejected as the default.** Most accurate in principle, but expensive to build and maintain per language, introduces a genuine persisted-staleness problem (§7), and is disproportionate to retrieval that is already ring-bounded and trigger-fired — #87 never authorizes looking at more than a few call sites or implementers for a `standard`/`elevated` change. |
| 3 | **Recommended: an ephemeral, per-review, snapshot-bound, trigger-scoped symbol index** — built lazily, only for the ring(s) a fired #87 trigger authorizes, from the same lightweight code reading a bounded-expansion investigation already does; formalized with a typed entity/relationship model, explicit snapshot identity, and explicit provenance. | **Recommended.** Smallest model that satisfies every acceptance criterion: it makes ring-bounded retrieval inspectable and its influence on findings attributable, without persistence, without a new store, and without expanding #87's authorized reach. |

Candidate 3 is the model the rest of this document defines.

## 4. The typed entity/relationship model

**Entities** — a closed, typed set:

| Entity kind | Definition |
| --- | --- |
| `file` | A single source file, identified by its repo-relative path. |
| `module` | A named importable unit (a package, namespace, or file-as-module, per the target language's own convention). |
| `class` | A class, struct, or equivalent type definition. |
| `function` | A function or method. |
| `symbol` | Any other named, referenceable unit not covered above (a constant, an exported variable, a configuration key). |

**Relationships** — a closed, typed set, each tagged with the #87 trigger
that surfaces it:

| Relationship kind | Trigger | Meaning |
| --- | --- | --- |
| `calls` | call-site | A function/method invokes another. |
| `imports` | call-site | A file/module imports another, the mechanism by which a call-site trigger's caller is discovered. |
| `implements` | interface/contract | A class implements or extends an interface, abstract base, or protocol. |
| `references` | migration/schema | A query, ORM model, or sibling migration references a changed table or column. |
| `references` | config-consumer | Code reads or otherwise consumes a changed configuration key, feature flag, or environment variable. |

The set is closed on both axes: an entity or relationship outside this
table is not modeled, and a reviewer does not invent a new kind. This
mirrors [`repository-expansion.md`](../../shared/policies/repository-expansion.md),
"a reviewer does not invent new trigger types" — the same discipline, one
level down.

The trigger column's machine-readable identifiers are reused verbatim from
[`repository-expansion.md`](../../shared/policies/repository-expansion.md)'s
own machine-readable model: `call_site`, `interface_contract`,
`migration_schema`, `config_consumer` — this document does not mint a
second vocabulary for the same four triggers.

## 5. Retrieval bounds

Retrieval never reaches further than the ring #87 already authorized for
the current change:

| Change-risk depth | Maximum ring reachable (unchanged from #87) |
| --- | --- |
| `standard` | Ring 1 — direct call sites/consumers only, and only when a trigger fired. |
| `elevated` | Ring 2. |
| `deep` | Ring 3. |

This model's only addition is that **what is resolved inside that ring is
now a typed set of entities and relationships**, not an informal "looked at
the callers" note. A relationship resolved at ring 2 for a `standard`
change is not a valid retrieval — the ceiling is enforced, not merely
advisory. Stopping at the first ring that resolves or disproves the
question, per #87's "Stop at the first ring," is unchanged.

## 6. Provenance

Every resolved relationship carries the source evidence for the edge
itself: the file and line of the referencing fact (an import statement, a
call expression, an `implements` clause, a config read). This is the same
evidentiary bar [`evidence.md`](../../shared/policies/evidence.md) already
requires of any finding, made explicit for graph-sourced facts
specifically — a relationship without a concrete `path:line` is not a
resolved relationship.

## 7. Snapshot identity and staleness

An ephemeral index can still become stale if the reviewed worktree changes
after the index was built. This model closes that gap explicitly rather
than leaving it implicit:

- The index is bound to one explicit **repository snapshot identity** — a
  commit/worktree token in real use, a fixture-declared snapshot id in
  tests.
- Before the index is used, the reviewed worktree's **current** snapshot
  identity is compared against the index's bound identity.
- **Match** — the index is valid for this review; retrieval proceeds.
- **Mismatch** (the worktree changed since the index was built) — the
  index is **stale**: it is **rejected and discarded outright**, a rebuild
  is required, and the review **never silently continues** on stale
  relationship data. This is a hard reject, not a soft warning or a
  best-effort continuation.

Git / the current worktree remains the **sole source of truth**. The index
never persists across reviews, never claims independent authority, and is
rebuilt fresh — scoped only to the ring a trigger authorizes — every time
it is needed. There is therefore no cross-review staleness window to
manage beyond "does the index's bound snapshot match the worktree right
now" — a single, mechanical check.

## 8. Relationship-influence attribution

A finding can identify which retrieved relationship(s) **materially
influenced** it — the acceptance criterion this section satisfies, without
adding a new packaged finding field (§11 explains why that stays deferred).

The reference model **records and exposes** an `influential_relationships`
list per retrieval result, separate from the full resolved-edge set. This
proves the contract at fixture/reference level; it is deliberately **not**
a general-purpose algorithm that infers materiality from arbitrary
repository state:

- a result can identify the resolved relationship(s) that materially
  enabled it — which edges the worked example / fixture designates as
  load-bearing for that specific case;
- each influential edge retains its provenance (§6);
- edges that were retrieved (in-ring, trigger-authorized, successfully
  resolved) but turned out irrelevant to the outcome are **excluded** from
  `influential_relationships`, even though they were legitimately
  retrieved. Retrieving more context must never, by itself, inflate what
  counts as influential (§10, worked example 5).

An ambiguous or unresolved candidate (§9) is **never** a resolved edge, and
therefore can never appear in `influential_relationships` and can never
support a finding.

## 9. Safe behavior for ambiguity, missing data, and unsupported languages

Unsupported language shapes, ambiguous resolution (dynamic dispatch,
reflection, string-keyed runtime lookups, and similar), or missing
relationship data mean a candidate relationship is **not successfully
resolved** — it never enters the normal resolved-edge set at all. The
reference model may represent it separately as a diagnostic /
resolution-failure record (`UnresolvedCandidate`), but such a record must
never: become a resolved edge, appear in `influential_relationships`, or
support a finding.

Reported to the review as **"insufficient evidence"** — a valid terminal
outcome already established by
[`repository-expansion.md`](../../shared/policies/repository-expansion.md),
"Stop at the first ring" — never an invented relationship. A reviewer does
not guess which concrete implementation a dynamically dispatched call
reaches; it says the dispatch is ambiguous and stops there.

## 10. Worked examples

Each example is also a benchmark fixture in
[`../benchmark/corpus/repository-intelligence/`](../benchmark/corpus/repository-intelligence/README.md)
and a case in the reference corpus
([`../../tests/unit/review/test_repository_intelligence.py`](../../tests/unit/review/test_repository_intelligence.py)),
asserted to resolve exactly as documented here. Three positive examples
cover two language shapes (Python, TypeScript); one covers safe failure on
ambiguity; one is a negative/control case.

### Worked example 1 — call-site trigger catches a caller-side null dereference (Python)

```text
Change: app/users/lookup.py::get_user stops raising UserNotFound for a
  missing user and instead returns None — reads as a plausible, even
  benign, API simplification in isolation.
Diff-only read: nothing in get_user's new body is itself incorrect; a
  diff-only review has no way to know any caller assumed the old
  exception-raising contract.
Call-site trigger fires (get_user is a changed function with a consumer);
  ring 1 resolves app/billing/charge.py::charge_user, which still does
  `except UserNotFound: return declined(...)` around the call and then
  dereferences `user.account_id` unconditionally afterward.
Resolved relationship: calls — charge_user -> get_user, ring 1, provenance
  app/billing/charge.py (the call site).
Finding: P1 — "get_user now returns None for a missing user instead of
  raising UserNotFound; charge_user's except clause no longer triggers, so
  a missing user crashes with AttributeError on user.account_id instead of
  a clean decline."
influential_relationships: [calls — charge_user -> get_user] — the caller
  relationship is exactly what makes this a finding; without it, get_user's
  new body alone supports no finding.
```

### Worked example 2 — interface/contract trigger catches an inconsistent implementer (TypeScript)

```text
Change: src/cache/Cache.ts narrows Cache.get()'s return type from
  Promise<string | null> to Promise<string> (a cache miss now throws
  instead of returning null); src/cache/RedisCache.ts is updated in the
  same diff to throw on miss, correctly matching the new contract.
Diff-only read: the diff looks internally consistent — the interface and
  the one implementer shown both changed together.
Interface/contract trigger fires (a changed interface with implementers);
  ring 2 (owning interface) then ring 3 (sibling implementers) resolves
  src/cache/InMemoryCache.ts, untouched by the diff, whose get() still
  returns string | null on a cache miss.
Resolved relationship: implements — InMemoryCache -> Cache, ring 2/3,
  provenance src/cache/InMemoryCache.ts (the implements clause) and
  src/cache/Cache.ts (the changed signature).
Finding: P1 — "InMemoryCache.get no longer satisfies the updated
  Cache.get(): Promise<string> contract; it still resolves null on a
  cache miss, breaking any caller written against the new no-null
  contract."
influential_relationships: [implements — InMemoryCache -> Cache].
```

### Worked example 3 — config-consumer trigger catches a stale consumer (Python)

```text
Change: app/settings.py renames MAX_UPLOAD_MB (a megabyte limit) to
  MAX_UPLOAD_BYTES (a byte limit) — the old name is removed entirely.
Diff-only read: settings.py's diff alone looks like an ordinary rename;
  nothing in it is wrong on its own.
Config-consumer trigger fires (a changed configuration key); ring 1
  resolves app/uploads.py, untouched by the diff, which still does
  `from app.settings import MAX_UPLOAD_MB`.
Resolved relationship: references — uploads.py -> MAX_UPLOAD_MB (config
  consumer), ring 1, provenance app/uploads.py (the import line).
Finding: P0 — "app/settings.py removes MAX_UPLOAD_MB; app/uploads.py still
  imports it, so the module fails to import (ImportError) as soon as an
  upload path is exercised."
influential_relationships: [references — uploads.py -> MAX_UPLOAD_MB].
```

### Worked example 4 — dynamic dispatch is safe failure, not an invented relationship (Python)

```text
Change: app/handlers/base.py::BaseHandler.process behavior changes.
app/handlers/registry.py dispatches via a string-keyed registry,
  HANDLERS[kind]().process(payload), where kind is external request data —
  not a static literal at any call site in the reviewed code.
Call-site trigger fires (BaseHandler.process is a changed method with
  consumers); resolution is attempted at ring 1, but which concrete
  Handler subclass's process() override a given external caller reaches
  cannot be determined statically from kind.
Outcome: UnresolvedCandidate(reason=ambiguous) — not a resolved edge, never
  promoted to influential_relationships, never used to support a finding.
  The review reports insufficient evidence for the dispatch question rather
  than guessing which concrete subclass is affected.
```

### Worked example 5 — retrieval succeeds but the relationship is compatible: no finding (Python, control)

```text
Change: app/text/normalize.py::normalize_whitespace changes from
  s.strip() (trims only the ends) to " ".join(s.split()) (also collapses
  internal whitespace) — a strictly more thorough normalization.
Call-site trigger fires; ring 1 resolves app/text/slugify.py::make_slug,
  the only caller, which lowercases the result and replaces spaces with
  hyphens regardless of how many consecutive spaces existed.
Resolved relationship: calls — make_slug -> normalize_whitespace, ring 1,
  provenance app/text/slugify.py (the call site) — retrieved successfully,
  with valid provenance, exactly like worked example 1.
Outcome: the retrieved relationship is compatible with the change — no
  finding. Retrieval breadth alone does not create a finding.
influential_relationships: [] — none of the retrieved relationships
  materially changes the review's conclusion, so none is reported as
  influential even though the edge itself was legitimately resolved.
```

## 11. Smallest useful first implementation

The smallest slice that delivers the capability, matching what actually
lands with #129:

1. **This typed model** — the entity/relationship kinds (§4), the
   retrieval-bound reuse of #87's ring ceiling (§5), provenance (§6),
   snapshot identity and staleness (§7), and relationship-influence
   attribution (§8) — consumed as a **design record and a test-only
   reference model**, not as new runtime behavior.
2. **Benchmark evidence** — the fixtures in
   [`../benchmark/corpus/repository-intelligence/`](../benchmark/corpus/repository-intelligence/README.md)
   demonstrate the mechanism on representative cases across two language
   shapes; they are illustrative, not a measured hit-rate (§10 note; the
   corpus README states this explicitly — no statistical-significance
   claim is made from a small corpus).
3. **Reference-level cross-links only** from
   [`repository-expansion.md`](../../shared/policies/repository-expansion.md)
   and [`evidence.md`](../../shared/policies/evidence.md) to this document
   — no model or table duplicated into packaged policy.

**Deferred to later, separately-scoped issues** (named here so scope stays
fixed):

- a real, non-ephemeral index or a language-specific static-analysis
  backend that builds §4's entities/relationships from actual source
  instead of being hand-supplied per fixture/case;
- **a packaged finding-template field carrying `influential_relationships`
  in review output** — the eventual representation of §8's attribution in
  the packaged finding contract is explicitly deferred to a later,
  separately-scoped implementation issue, mirroring how the [contextual
  evidence model](../review-context/contextual-evidence-model.md) (#118)
  preceded #176/#178's later packaged fields;
- any runtime that builds, persists, queries, or auto-attaches a
  repository graph during a review;
- cross-repository or stacked-PR relationship context (explicit Non-Goal);
- a general-purpose materiality-inference algorithm — §8's
  `influential_relationships` stays fixture/reference-designated until a
  later issue, if any, defines one.

## 12. Runtime boundary

[#129](https://github.com/amirbena/code-review-skill/issues/129) adds this
design record and a test-only reference model. It introduces **no**
automatic relationship retrieval, no persisted or live index, no graph
database, no new capability (no mutation, no network), and it does **not**
change [`repository-expansion.md`](../../shared/policies/repository-expansion.md)'s
(#87) trigger catalog, ring ceiling, or reporting contract. No code in this
repository builds, persists, or queries a repository graph.

## 13. Relationship to existing canonical policies

- [`repository-expansion.md`](../../shared/policies/repository-expansion.md)
  owns the trigger catalog, the ring-bounded expansion procedure, the
  ring-ceiling-by-change-risk-depth table, and the reporting contract
  ("Expansion decisions are reported"). This document does not restate or
  alter any of it — it types what a fired trigger resolves *inside* the
  ring that policy already authorizes.
- [`evidence.md`](../../shared/policies/evidence.md) owns the code-evidence
  bar and "Findings beyond the changed lines"; a relationship's provenance
  (§6) meets that same bar, it does not lower it.
- [`review-scope.md`](../../shared/policies/review-scope.md) owns
  "Architectural placement and execution-lifecycle fidelity" (its own
  bounded caller/callee/owning-boundary expansion for placement/lifecycle
  questions specifically) and the scope-explosion guard; this document
  does not replace either.
- [`severity.md`](../../shared/policies/severity.md) owns severity and the
  mechanical decision derivation; nothing here computes, raises, or lowers
  a severity — a relationship can supply the evidence a finding needs, the
  same way any code evidence would, never a severity value of its own.
- [`shared/templates/finding.md`](../../shared/templates/finding.md) owns
  the finding contract. This document introduces no new field on it; §8's
  `influential_relationships` stays a design-record and reference-model
  concept only, deferred as described in §11.
