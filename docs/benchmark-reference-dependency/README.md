# Benchmark reference-model dependency direction (#792)

Design record. Parent: #786. Related: #457, #651, #680, #466.

## Decision

`tests.reference.review` is the **sanctioned reference-model library**. It owns
the test-only models that mirror packaged review policy (`decision_semantics`,
`verdict_consistency`, `mutation_authority`, …). The benchmark reference code
under `runtime_platform/benchmark/reference/` may import from it; the models
are not relocated.

Why not relocate: the models back many unit tests under `tests/unit/review/`,
so moving them would touch every one of those import sites to change a
dependency that is already one-directional and test-only (neither Skill archive
loads either side). Relocation stays available as a separate follow-up.

## Allowed and forbidden directions

```text
runtime_platform/  ──►  tests.reference.review      allowed
tests.reference.review  ──►  stdlib, itself          allowed
runtime_platform/  ──►  any other tests.*            forbidden
tests.reference.review  ──►  runtime_platform        forbidden
```

"Any other `tests.*`" includes `tests.support`, `tests.unit`, `tests.policy`
and `tests.reference.benchmark` (the pre-#457 location, now gone).

## Enforcement scope

[`test_reference_dependency_direction.py`](../../tests/policy/benchmark/test_reference_dependency_direction.py)
scans `runtime_platform/**` and `tests/reference/review/**`. `scripts/` is
**out of scope**: #792 concerns the benchmark platform, and `scripts/` has no
`tests` imports today. Extending the rule to `scripts/` would be a new
architectural decision, not part of this one.

Imports are normalised to absolute targets, so equivalent forms classify the
same: `import tests.reference.review`, `… as review`,
`from tests.reference import review` and
`from tests.reference.review import x` are all allowed; `from tests import x`,
`from tests.reference import benchmark` and relative imports resolving outside
the library are not.

## Known limitations

The scan is static. It does not see dynamic imports (`importlib`,
`__import__`), `sys.path` manipulation, or imports in non-Python files. Imports under a
`TYPE_CHECKING` guard and inside functions count as real dependencies.

## Stale `tests/reference/benchmark` references

The directory was relocated to `runtime_platform/benchmark/reference/` by #457.
The remaining mentions are in
[`docs/capability-architecture/benchmark-ownership-boundary-checkpoint.md`](../capability-architecture/benchmark-ownership-boundary-checkpoint.md),
a record of the pre-#457 inventory; they are intentionally historical and that
document carries a note saying so.
