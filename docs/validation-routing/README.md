# Change-Aware Test Selection — Design Record

Repository-development design record for a **safe, shared, change-aware
rule** that avoids unnecessarily broad validation for small and docs-only
changes ([#624](https://github.com/amirbena/code-review-skill/issues/624)).

Like [`../rendered-inspection/README.md`](../rendered-inspection/README.md),
this is a repository-development doc: **not** packaged into either Skill
archive, and no packaged Skill resource depends on it. It records the
research and design, and the first iteration of it is implemented in the same
issue (see "Implemented in the first iteration" in the model). The routing
mechanics stay owned by
[`../../policies/validation-and-clean-exit.md`](../../policies/validation-and-clean-exit.md)
("Routed CI tests") and
[`../../scripts/validation/ci_test_route.py`](../../scripts/validation/ci_test_route.py).

## Document map

| Document | Owns |
| --- | --- |
| [`partial-tier-model.md`](partial-tier-model.md) | The PARTIAL tier ([#634](https://github.com/amirbena/code-review-skill/issues/634)): why test-only changes were FULL, the derived test-impact graph, the path-to-surface rules, union/monotonicity, fail-upward conditions, the router-is-FULL rule, measured fan-out, and accepted limits. Replaces the deferred "TARGETED" tier of the model below. |
| [`change-aware-test-selection-model.md`](change-aware-test-selection-model.md) | What was implemented, evidence about what consumes `docs/`, the four classes and what runs for each, the shared classifier, the drift guard, the no-live-execution invariant, the deterministic selector test plan, and the proposed implementation issues. |

## Summary

- A `.md` file is **not** inert: tests pin docs, global scanners read every
  tracked file, and integration temp roots copy `docs/`. Classification is by
  **derived consumer evidence**, never by extension or a hand-kept path list.
- Four classes: pure documentation → static docs validation only;
  consumed documentation → only what its consumers need; mixed → classified
  by the non-doc paths; unknown / high-risk → FULL.
- One classifier module serves CI and local validation, so both report the
  same class, tier, reason, and path that forced a broader tier.
- A fourth tier, PARTIAL, runs an explicit, derived module set for a bounded
  test-only change; the tier order is `DOCS < PARTIAL < FAST < FULL`. The
  #624 record's deferred "TARGETED" tier is this tier, renamed.
- #533 invariants are unchanged: FULL stays the default, FAST never removes a
  contract or correctness test, and no label or flag selects a tier.

Related: [#623](https://github.com/amirbena/code-review-skill/issues/623),
[#533](https://github.com/amirbena/code-review-skill/issues/533),
[#535](https://github.com/amirbena/code-review-skill/issues/535),
[#538](https://github.com/amirbena/code-review-skill/issues/538),
[#183](https://github.com/amirbena/code-review-skill/issues/183). Parent:
[#395](https://github.com/amirbena/code-review-skill/issues/395).
