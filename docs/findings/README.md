# Finding Identity, Matching & Lifecycle

Repository-development contracts for **cross-review finding identity** —
telling "the same defect again" from "a new defect" when a change is
reviewed more than once. They are the fixed contract the stateful
re-review work (parent [#42](https://github.com/amirbena/code-review-skill/issues/42) /
[#43](https://github.com/amirbena/code-review-skill/issues/43)) is built
against.

Like [`../runtime-parallelism.md`](../runtime-parallelism.md), these are
repository-development docs: **not** packaged into either Skill archive,
and no packaged Skill resource depends on them. They are explanatory /
design records — the normative rule for each concern lives in the file
named for it, and moves into a packaged `shared/` policy when
[#65](https://github.com/amirbena/code-review-skill/issues/65) installs the
runtime behavior.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`finding-identity-requirements.md`](finding-identity-requirements.md) | *What* finding identity must and must not do — must-survive / must-change scenarios, determinism, portability, fail-toward-splitting. | [#58](https://github.com/amirbena/code-review-skill/issues/58) |
| [`finding-matching-strategy.md`](finding-matching-strategy.md) | *Which* prior finding a current one continues — the precision-first staged hybrid, its two proof axes, and the `MATCH` / `AMBIGUOUS` / `NO MATCH` outcomes. | [#59](https://github.com/amirbena/code-review-skill/issues/59) |
| [`finding-stable-identity.md`](finding-stable-identity.md) | *How* the stable identifier and its descriptor primitives are constructed — the canonical deterministic derivation, with a test-only reference model. | [#60](https://github.com/amirbena/code-review-skill/issues/60) |
| [`finding-lifecycle-contract.md`](finding-lifecycle-contract.md) | The `OPEN` / `RESOLVED` state of one identity across reviews and its evidence-gated transitions. | [#62](https://github.com/amirbena/code-review-skill/issues/62) |
| [`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md) | The reviewed-SHA state a re-review compares against — the recorded fields, which commit is authoritative, and invalidation. | [#63](https://github.com/amirbena/code-review-skill/issues/63) |

The identity regression suite required by
[#61](https://github.com/amirbena/code-review-skill/issues/61) lives in
[`../../tests/unit/test_finding_identity_regression.py`](../../tests/unit/test_finding_identity_regression.py)
and exercises the reference model in
[`../../tests/reference/finding_identity.py`](../../tests/reference/finding_identity.py).

## Related

The architecture map is [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
