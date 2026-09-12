# Repository Intelligence — Entities, Relationships & Retrieval

Repository-development design records for how a review models and
retrieves **repository entities and relationships** inside a ring
[`../../shared/policies/repository-expansion.md`](../../shared/policies/repository-expansion.md)
(#87) has already authorized: what an entity and a relationship are, how
far retrieval reaches, how a retrieved relationship keeps provenance, how a
snapshot-bound index avoids going stale, and how a finding can identify
which retrieved relationship materially influenced it.

Like [`../review-context/README.md`](../review-context/README.md) and
[`../findings/README.md`](../findings/README.md), these are
repository-development docs: **not** packaged into either Skill archive, and
no packaged Skill resource depends on them. They are explanatory / design
records — the normative rule for each concern lives in the file named for
it, and the packaged shared policies
([`../../shared/policies/repository-expansion.md`](../../shared/policies/repository-expansion.md),
[`../../shared/policies/evidence.md`](../../shared/policies/evidence.md))
reference this document by name.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`repository-intelligence-model.md`](repository-intelligence-model.md) | The candidate-architecture comparison and the recommended minimal model: the typed entity/relationship model, retrieval bounds inside an already-authorized ring, provenance, snapshot identity and staleness (reject-and-rebuild), relationship-influence attribution, and safe behavior for ambiguity, missing data, and unsupported languages. | [#129](https://github.com/amirbena/code-review-skill/issues/129) |

## Architectural boundary

[`repository-expansion.md`](../../shared/policies/repository-expansion.md)
(#87) stays canonical for **when** an investigation expands past the diff,
**which trigger** authorizes it, and **how far** (the ring ceiling). This
model never re-derives or loosens that ceiling — it defines what happens
*inside* an authorized ring: entity semantics, relationship semantics,
bounded retrieval, provenance, snapshot validity, and relationship-influence
attribution. See
[`repository-intelligence-model.md`](repository-intelligence-model.md),
"Where this sits relative to repository-expansion.md."

## Related

- The packaged, deterministic trigger-catalog and ring-bounded expansion
  procedure this model retrieves inside:
  [`../../shared/policies/repository-expansion.md`](../../shared/policies/repository-expansion.md).
- The general "scale dependency exploration to blast radius" instruction
  this makes concrete for repository relationships specifically:
  [`../../shared/policies/evidence.md`](../../shared/policies/evidence.md),
  "Findings beyond the changed lines."
- The test-only reference model:
  [`../../tests/reference/review/repository_intelligence.py`](../../tests/reference/review/repository_intelligence.py).
- The benchmark evidence demonstrating relationship-aware context catching
  defects diff-only review misses, without unacceptable false-positive
  growth:
  [`../benchmark/corpus/repository-intelligence/README.md`](../benchmark/corpus/repository-intelligence/README.md).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
