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
named for it.

[#65](https://github.com/amirbena/code-review-skill/issues/65) has
installed the orchestration around these contracts —
[`delta-re-review-contract.md`](delta-re-review-contract.md) (#64)
specifically — as packaged runtime behavior in
[`skills/github-pr-review/policies/stateful-delta-rereview.md`](../../skills/github-pr-review/policies/stateful-delta-rereview.md).
That policy consumes, without redefining, the identity/matching
vocabulary (#58/#59/#60), the lifecycle transitions (#62), and the
reviewed-state record (#63) documented below; none of those four have
their own packaged algorithm/schema yet — see each document's own
"Status and canonical home" for what still awaits its own installing
issue.

## Document map

| Document | Owns | Issue |
| --- | --- | --- |
| [`finding-identity-requirements.md`](finding-identity-requirements.md) | *What* finding identity must and must not do — must-survive / must-change scenarios, determinism, portability, fail-toward-splitting. | [#58](https://github.com/amirbena/code-review-skill/issues/58) |
| [`finding-matching-strategy.md`](finding-matching-strategy.md) | *Which* prior finding a current one continues — the precision-first staged hybrid, its two proof axes, and the `MATCH` / `AMBIGUOUS` / `NO MATCH` outcomes. | [#59](https://github.com/amirbena/code-review-skill/issues/59) |
| [`finding-stable-identity.md`](finding-stable-identity.md) | *How* the stable identifier and its descriptor primitives are constructed — the canonical deterministic derivation, with a test-only reference model. | [#60](https://github.com/amirbena/code-review-skill/issues/60) |
| [`finding-lifecycle-contract.md`](finding-lifecycle-contract.md) | The `OPEN` / `RESOLVED` state of one identity across reviews and its evidence-gated transitions. | [#62](https://github.com/amirbena/code-review-skill/issues/62) |
| [`reviewed-sha-state-contract.md`](reviewed-sha-state-contract.md) | The reviewed-SHA state a re-review compares against — the recorded fields, which commit is authoritative, and invalidation. | [#63](https://github.com/amirbena/code-review-skill/issues/63) |
| [`delta-re-review-contract.md`](delta-re-review-contract.md) | The review delta's semantics — change classes, delta-as-optimization, regression/blast-radius surfacing, settled-assumption reconsideration, and escalation to a broader/full review. | [#64](https://github.com/amirbena/code-review-skill/issues/64) |

The identity regression suite required by
[#61](https://github.com/amirbena/code-review-skill/issues/61) lives in
[`../../tests/unit/test_finding_identity_regression.py`](../../tests/unit/test_finding_identity_regression.py)
and exercises the reference model in
[`../../tests/reference/finding_identity.py`](../../tests/reference/finding_identity.py).

The stateful re-review regression fixtures required by
[#66](https://github.com/amirbena/code-review-skill/issues/66) live in
[`../../tests/unit/test_rereview_regression_fixtures.py`](../../tests/unit/test_rereview_regression_fixtures.py):
paired before/after review histories that assert re-review mode, change
class, lifecycle event/state (inheriting
[`finding-lifecycle-contract.md`](finding-lifecycle-contract.md) §9's
fifteen scenarios), surfaced/suppressed findings, the mechanical decision,
finding-identity continuity, and exact-reviewed-HEAD binding — driven
entirely through the existing
[`../../tests/reference/`](../../tests/reference/) models for #64/#62/#60
and severity, with an induced-regression / mutation check.

## Related

The architecture map is [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
