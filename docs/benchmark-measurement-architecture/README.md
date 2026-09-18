# Benchmark, Measurement & Analytics Architecture

Repository-development design record for the **cross-component
architecture** spanning benchmark-quality CI (epic
[#329](https://github.com/amirbena/code-review-skill/issues/329)) and
review execution telemetry
([#182](https://github.com/amirbena/code-review-skill/issues/182)). This
document also designed, and then closed as `not planned`, two further
measurement capabilities — review analytics
([#131](https://github.com/amirbena/code-review-skill/issues/131)) and
repository-scoped learning
([#130](https://github.com/amirbena/code-review-skill/issues/130)) — as
**product-layer** capabilities outside this Skill's scope: both require
persisted, cross-invocation history (historical aggregation and learned
behavior from stored reviewer feedback) that crosses the boundary from an
invocation-scoped review Skill into a stateful product/knowledge layer.
See the model document's "Product-layer boundary decision" addendum for
the full rationale.

Like [`../../runtime_platform/benchmark/README.md`](../../runtime_platform/benchmark/README.md),
[`../finding-confidence/README.md`](../finding-confidence/README.md), and
[`../review-context/README.md`](../review-context/README.md), this is a
repository-development doc: **not** packaged into either Skill archive, and
no packaged Skill resource depends on it. It is the single place that
defines how #329's runtime/selection/nightly work and #182's measurement
work relate, and where #131/#130's product-layer boundary is recorded —
each active issue still owns its own local implementation scope; this
document owns only the boundaries and the dependency order between them.

## Document map

| Document | Owns | Issues |
| --- | --- | --- |
| [`benchmark-measurement-architecture-model.md`](benchmark-measurement-architecture-model.md) | The canonical dependency DAG across #330/#331/#332's children, ending at `(#182 + #329) → Tier 4 complete`; the architecture layers from runtime execution through telemetry; the vendor-neutral runtime contract (now split into two execution classes — automatic/repository-triggered, and maintainer-controlled via Claude Cloud Routines, per #391); the PR-time and nightly benchmark paths at a principles level; the telemetry ≠ benchmark ground truth boundary; and the product-layer boundary decision that closes #131 (analytics) and #130 (learning) as `not planned`. | [#329](https://github.com/amirbena/code-review-skill/issues/329), [#330](https://github.com/amirbena/code-review-skill/issues/330), [#331](https://github.com/amirbena/code-review-skill/issues/331), [#332](https://github.com/amirbena/code-review-skill/issues/332), [#333](https://github.com/amirbena/code-review-skill/issues/333), [#334](https://github.com/amirbena/code-review-skill/issues/334), [#335](https://github.com/amirbena/code-review-skill/issues/335), [#336](https://github.com/amirbena/code-review-skill/issues/336), [#337](https://github.com/amirbena/code-review-skill/issues/337), [#338](https://github.com/amirbena/code-review-skill/issues/338), [#339](https://github.com/amirbena/code-review-skill/issues/339), [#182](https://github.com/amirbena/code-review-skill/issues/182), [#391](https://github.com/amirbena/code-review-skill/issues/391); [#131](https://github.com/amirbena/code-review-skill/issues/131) and [#130](https://github.com/amirbena/code-review-skill/issues/130) closed `not planned` |
| [`verdict-consistency-boundary-research.md`](verdict-consistency-boundary-research.md) | Research recommendation (not a contract change), §12.4 second bullet: whether a deterministic runtime step should reconcile a live review's rendered findings, rendered Result/Decision, and (for `github-pr-review`) its submitted GitHub review event before or at publication. Recommends building an MVP now against the existing fixed-vocabulary decision/severity markers rather than waiting on #67/#71's schema, defines the exact mismatch condition, places the check at four pre-publish call sites across both Skills' runbooks, and recommends withhold-and-report (never self-correct) on a detected mismatch. | [#351](https://github.com/amirbena/code-review-skill/issues/351) |

## Related

- The benchmark contracts this architecture sits above (corpus, runner,
  match criteria, quality metrics, existing CI wiring):
  [`../../runtime_platform/benchmark/README.md`](../../runtime_platform/benchmark/README.md).
- The finding `confidence` field that benchmark-derived and runtime-validated
  evidence roll up into: [`../finding-confidence/README.md`](../finding-confidence/README.md).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
