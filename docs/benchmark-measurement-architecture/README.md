# Benchmark, Measurement & Analytics Architecture

Repository-development design record for the **cross-component
architecture** spanning benchmark-quality CI (epic
[#329](https://github.com/amirbena/code-review-skill/issues/329)) and the
three related-but-distinct measurement capabilities — review execution
telemetry ([#182](https://github.com/amirbena/code-review-skill/issues/182)),
review analytics ([#131](https://github.com/amirbena/code-review-skill/issues/131)),
and repository-scoped learning
([#130](https://github.com/amirbena/code-review-skill/issues/130)).

Like [`../benchmark/README.md`](../benchmark/README.md),
[`../finding-confidence/README.md`](../finding-confidence/README.md), and
[`../review-context/README.md`](../review-context/README.md), this is a
repository-development doc: **not** packaged into either Skill archive, and
no packaged Skill resource depends on it. It is the single place that
defines how #329's runtime/selection/nightly work and #182/#131/#130's
measurement work relate — each issue still owns its own local
implementation scope; this document owns only the boundaries and the
dependency order between them.

## Document map

| Document | Owns | Issues |
| --- | --- | --- |
| [`benchmark-measurement-architecture-model.md`](benchmark-measurement-architecture-model.md) | The canonical dependency DAG across #330/#331/#332's children, the architecture layers from runtime execution through repository-scoped learning, the vendor-neutral runtime contract, the PR-time and nightly benchmark paths at a principles level, and the telemetry ≠ benchmark ground truth ≠ analytics ≠ learning boundary. | [#329](https://github.com/amirbena/code-review-skill/issues/329), [#330](https://github.com/amirbena/code-review-skill/issues/330), [#331](https://github.com/amirbena/code-review-skill/issues/331), [#332](https://github.com/amirbena/code-review-skill/issues/332), [#333](https://github.com/amirbena/code-review-skill/issues/333), [#334](https://github.com/amirbena/code-review-skill/issues/334), [#335](https://github.com/amirbena/code-review-skill/issues/335), [#336](https://github.com/amirbena/code-review-skill/issues/336), [#337](https://github.com/amirbena/code-review-skill/issues/337), [#338](https://github.com/amirbena/code-review-skill/issues/338), [#339](https://github.com/amirbena/code-review-skill/issues/339), [#182](https://github.com/amirbena/code-review-skill/issues/182), [#131](https://github.com/amirbena/code-review-skill/issues/131), [#130](https://github.com/amirbena/code-review-skill/issues/130) |

## Related

- The benchmark contracts this architecture sits above (corpus, runner,
  match criteria, quality metrics, existing CI wiring):
  [`../benchmark/README.md`](../benchmark/README.md).
- The finding `confidence` field that benchmark-derived and runtime-validated
  evidence roll up into: [`../finding-confidence/README.md`](../finding-confidence/README.md).
- The architecture map: [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
