# Benchmark Candidate Taxonomy and Inverted Index

Repository-development contract for GitHub Issue
[#333](https://github.com/amirbena/code-review-skill/issues/333). Parent:
[#331](https://github.com/amirbena/code-review-skill/issues/331). Canonical
architecture:
[`../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md)
§3 ("Benchmark candidate taxonomy/indexing") and §5 ("PR benchmark path").
This document is that architecture's implementation contract for one
layer; a genuine contradiction between the two is resolved by updating the
canonical design through a reviewed change, never by redefining the
architecture locally here.

Like [`fixture-format.md`](fixture-format.md), this is a
repository-development doc: **not** packaged into either Skill archive,
and no packaged Skill resource depends on it.

## Canonical invariant

> **A small, closed, alias-free classification vocabulary is the only thing that stands between a PR and a full corpus scan.**

Selection (owned by [#334](https://github.com/amirbena/code-review-skill/issues/334))
never scores or scans the whole corpus per PR — it narrows through the
inverted index this document defines. That narrowing is only trustworthy
if the taxonomy behind it is closed (no alias drift — e.g. `authz` /
`authorization` / `permissions` never coexist as separate keys) and every
corpus case and PR diff is classified against the *same* enum.

## 1. Scope

This document owns:

- The taxonomy's four dimensions and their canonical, closed values (§2).
- The `unclassified` value as a first-class member of every dimension (§2).
- Corpus case classification: `metadata.taxonomy` in
  [`fixture-format.md`](fixture-format.md) §10.1, and its fail-closed
  validation.
- The one bounded, schema-constrained PR-diff classification model call
  (§4), and the fail-open-into-`unclassified` handling of its response.
- The deterministic, non-LLM inverted index built from corpus taxonomy
  metadata (§5), and keeping the committed index in sync with the corpus.

This document does **not** own (non-goals, mirroring the issue):

- Case relevance scoring, weighting, bands, or Top-K/coverage selection
  logic — [#334](https://github.com/amirbena/code-review-skill/issues/334).
- Actually executing any benchmark case.
- Runtime/credential provisioning for the model call —
  [#330](https://github.com/amirbena/code-review-skill/issues/330) /
  [`runtime-execution-contract.md`](runtime-execution-contract.md).

## 2. The four dimensions

Each dimension is a **closed**, **alias-free** enum. A value belongs to
exactly one dimension; no value is a synonym for another value in the same
or a different dimension. `unclassified` is always a legal, non-error
member: an unconfident classification (by a model, or a corpus author who
genuinely cannot narrow a dimension) declares it explicitly rather than
guessing or omitting the dimension.

The canonical enums are code, not prose — the single source of truth is
[`../../tests/reference/benchmark/benchmark_taxonomy.py`](../../tests/reference/benchmark/benchmark_taxonomy.py)
(`CAPABILITY_VALUES`, `POLICY_CONTRACT_VALUES`, `RISK_MODE_VALUES`,
`AFFECTED_SURFACE_VALUES`). The tables below describe each dimension's
purpose and value-selection rule; consult the module, not this document,
for the exact current value list.

### 2.1 `capability`

Canonical name per existing corpus domain directory
(`docs/benchmark/corpus/<directory>/`), plus `core` for the four
loose root-level cases that predate sub-directory organization.

A directory name carrying a `-deepening` suffix (a naming convention from
when these domains were added as *deepening* follow-ups to an existing
capability, e.g. `database-migration-deepening`) is normalized to its bare
capability — `database-migration`, `dependency-supply-chain`,
`distributed-systems`, `performance`. `security-deepening` is additionally
renamed to `security-boundary` to stay vocabulary-consistent with the
"Security / trust boundaries" system-level dimension in
[`../../shared/policies/review-scope.md`](../../shared/policies/review-scope.md)
(#211) — naming consistency only; `review-scope.md`'s dimension list is not
a shared artifact this taxonomy imports or forks.

The mapping from corpus directory to canonical `capability` value is
`CAPABILITY_BY_CORPUS_DIRECTORY` in `benchmark_taxonomy.py`.

**Note on drift from the issue text.** Issue #333's body enumerates a
`capability` list that predates several corpus domains added since
(`analogue-placement-pattern`, `candidate-finding-validation`,
`security-events`, `trusted-host-nl-authorization`, `verdict-consistency`)
and does not carry the `-deepening`-suffixed directory names verbatim.
Per the issue's own operative wording — "canonical name per existing
corpus domain directory" — this taxonomy derives `capability` from the
**live** corpus directory set (normalized as above), not from the issue
body's snapshot, so the enum stays accurate as the corpus grows rather
than re-drifting from actual directories on day one.

### 2.2 `policy_contract`

A maintained closed list of `shared/policies/*.md` stems, extended
deliberately — mirroring `APPLICABLE_PREFIXES` in
`scripts/benchmark/benchmark_ci_classifier.py`, which is also a
hand-maintained list rather than a filesystem scan. A corpus case (or PR
diff) declares the policy contract(s) its expected review behavior is
grounded in.

### 2.3 `risk_mode`

Reuses `metadata.tags`' existing enum
(`correctness` / `security` / `quality` / `no-op` / `regression` /
`concurrency` / `performance`) **unchanged**, plus `unclassified`. This is
deliberately the same vocabulary, not a parallel one: for a corpus case,
`metadata.taxonomy.risk_mode` is the same value set as `metadata.tags` —
one concept, one enum, one place it's spelled out per case.
`benchmark_fixture.py` pins the two frozensets equal at import time so
they can never silently drift apart.

### 2.4 `affected_surface`

The four named surfaces a change to **this repository** (not the
repository under review by a Skill) can land on, refined from the boolean
applicability check in `scripts/benchmark/benchmark_ci_classifier.py`
(#255):

| Value | Path basis |
|---|---|
| `shared-policy` | `shared/` |
| `skill-instructions` | `skills/` |
| `runtime-adapter` | `scripts/benchmark/run_benchmark.py`, `scripts/benchmark/benchmark_review_adapter.py` |
| `benchmark-corpus-or-tooling` | `docs/benchmark/`, `tests/reference/benchmark/`, `tests/unit/benchmark/`, `tests/policy/benchmark/`, the rest of `scripts/benchmark/` |

Unlike `capability`/`policy_contract`/`risk_mode`, `affected_surface` is
**fully deterministic** — `classify_affected_surfaces()` in
`benchmark_taxonomy.py` derives it directly from a PR's changed paths,
the same way `benchmark_ci_classifier.py` derives applicability. It is
never part of the one model call (§4): a path-prefix lookup needs no
judgment. `benchmark_taxonomy.py` deliberately does not import
`benchmark_ci_classifier.py` (and is not imported by it), mirroring that
module's own documented independence from other classifiers — the two
must never couple, even though their prefix sets overlap.

For an existing corpus case, `affected_surface` describes what a review of
*this repository's own future changes* in that capability area would
touch — most corpus cases (which benchmark review quality over an
arbitrary *external* diff, not a change to this repository) legitimately
declare `unclassified` here; it only resolves to a concrete surface for
cases that are themselves about this repository's own benchmark/Skill
machinery.

## 3. Corpus classification metadata

Every corpus case declares `metadata.taxonomy`, per
[`fixture-format.md`](fixture-format.md) §10.1: a mapping with all four
dimension keys, each a non-empty list of one or more values from that
dimension's enum (a case may legitimately belong to more than one
`capability`, `policy_contract`, etc. — e.g. a case exercising both
database-migration and performance concerns). Validation is fail-closed:
[`../../tests/reference/benchmark/benchmark_fixture.py`](../../tests/reference/benchmark/benchmark_fixture.py)
rejects the whole case on a missing dimension, an unknown dimension key,
an unknown value, or a duplicate value — via
`benchmark_taxonomy.validate_taxonomy()`. This is a hard requirement, not
a warning: a corpus case with missing or invalid taxonomy metadata fails
corpus validation.

## 4. PR-diff classification

The **one** bounded, schema-constrained model call in this whole design
(mirroring the "no embeddings, one model call" principle in the
architecture model's §5): classify a PR's changed paths/diff into
`capability`, `policy_contract`, and `risk_mode` (`affected_surface` is
computed deterministically per §2.4 and never asked of the model). The
model is given the closed enum for each of the three dimensions and may
only select from it — it can never invent a key or a value.

Two functions in `benchmark_taxonomy.py` implement the two sides of this
contract:

- `sanitize_taxonomy_response(raw)` — the **untrusted-input side**. Given
  the model's raw decoded-JSON response, it keeps only values that are
  both a known dimension and a known value in that dimension's enum;
  everything else (an invented key, an invented value, a malformed shape,
  a missing dimension, non-JSON output) is silently dropped, never raised.
  A dimension left with no valid values resolves to `(unclassified,)`.
  This is deliberately **not** the same function as
  `validate_taxonomy()` (§3): a corpus author's mistake should fail
  loudly; a model's off-taxonomy guess should fail safely into
  `unclassified` so a malformed response never breaks the PR path.
- The runtime invocation itself reuses
  [#330](https://github.com/amirbena/code-review-skill/issues/330)'s
  provisioned Class 2 (maintainer-controlled) runtime/credential path —
  see [`runtime-execution-contract.md`](runtime-execution-contract.md) —
  rather than introducing a second secret-bearing integration. It is not
  reachable from contributor PR automation or a required check.

## 5. The inverted index

A deterministic, non-LLM build step — parsing corpus YAML, never running a
benchmark — producing:

```
{ (dimension, value) -> [case_id, ...] }
```

serialized as
[`corpus-index.json`](corpus-index.json), built by
[`../../scripts/benchmark/build_benchmark_index.py`](../../scripts/benchmark/build_benchmark_index.py)
from every corpus case's `metadata.taxonomy`. The index is **committed**
and regenerated whenever the corpus changes; a policy test
(`tests/policy/benchmark/test_benchmark_index_sync.py`, mirroring
`tests/policy/benchmark/`'s existing sync-guard pattern) asserts the
committed index equals a fresh build from the live corpus.

This index is what keeps PR-time selection ([#334](https://github.com/amirbena/code-review-skill/issues/334))
off the full corpus: candidate narrowing is a lookup keyed on the PR's own
classified `(dimension, value)` pairs, bounded by the matched candidate
set — never a scan whose cost grows with total corpus size.

### 5.1 Index shape

```json
{
  "capability": {
    "security-boundary": ["security-command-injection", "..."],
    "unclassified": ["..."]
  },
  "policy_contract": { "...": ["..."] },
  "risk_mode": { "...": ["..."] },
  "affected_surface": { "...": ["..."] }
}
```

Top-level keys are exactly the four dimension names (§2), in that order.
Each dimension maps every value **present in the live corpus** for that
dimension (a value with zero current cases is simply absent, not an
empty-list placeholder) to a sorted, de-duplicated list of case `id`s.

## 6. Status and canonical home

This document is the authoritative contract for the candidate taxonomy and
inverted index until a later issue installs an equivalent schema in
another canonical home, exactly as
[`fixture-format.md`](fixture-format.md) describes for itself.
