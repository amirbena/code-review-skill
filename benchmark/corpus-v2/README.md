# Frozen `benchmark-case/v2` corpus

An immutable copy of the v2 benchmark corpus as it stood before the v3
migration ([#848](https://github.com/amirbena/code-review-skill/issues/848)).
**Do not edit, re-format or migrate anything here.**

Historical experiments and sealed records pin these bytes by digest, and
rewriting them would silently change what that evidence refers to:

- the concurrency-campaign subset (`subset_id` in
  `runtime_platform/benchmark/schedule/concurrency-experiment-spec.json`);
- the dependency-tree pre-registration
  (`corpus/dependency-tree-inspection/pre-registration.json`, whose
  `fixture_set_digest` covers `dependency-tree-inspection/` here);
- the pre-#688 sentinel snapshot (`tests/support/pre_688_sentinel_record.json`,
  whose corpus digest covers the four top-level fixtures here).

This directory is not an active lane: it holds `benchmark-case/v2` fixtures,
which the default validator rejects. It is read only with an explicit
`parse_case(..., legacy=True)` or by passing it as `--corpus-dir`. v3 records
start a new baseline epoch and v2 sealed history is not comparable with them.
It also keeps the sub-corpora v3 removed (see
[`../corpus/README.md`](../corpus/README.md)). Guarded by
`tests/unit/benchmark/test_benchmark_v2_epoch.py`.
