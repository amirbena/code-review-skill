# Capability Architecture

Repository-development **research record** for how this repository's two
Code Review Agent Skills should be decomposed into independently loadable
capabilities, and what repository topology should hold them.

Like [`../benchmark-measurement-architecture/README.md`](../benchmark-measurement-architecture/README.md),
[`../candidate-finding-validation/README.md`](../candidate-finding-validation/README.md),
and [`../repository-intelligence/README.md`](../repository-intelligence/README.md),
this is a repository-development doc: **not** packaged into either Skill
archive, and no packaged Skill resource depends on it.

It is a **research recommendation, not a contract change.** Nothing here
has been implemented: no file has moved, no repository has been created,
no policy's canonical ownership has changed. Every canonical rule named
below still lives exactly where [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
and [`../../shared/policies/README.md`](../../shared/policies/README.md)
say it lives.

## Document map

| Document | Owns |
| --- | --- |
| [`capability-architecture-model.md`](capability-architecture-model.md) | The current-state diagnosis with measured evidence, the proposed capability map and load tiers, the progressive-loading design, the local/GitHub adapter relationship, the evaluation of the three repository models and the recommended topology, current and target dependency graphs, per-capability contracts, benchmark ownership, the performance-measurement plan, the migration sequence and its first extraction, risks and rollback, and the follow-up issue breakdown. |
| [`capability-loading-baseline.md`](capability-loading-baseline.md) | The pre-`specialist-depth`-extraction baseline (§I.2): today's packaged instruction-surface word/token counts attributed by capability, and the current values of the existing quality-metric contracts (#55/#56/#57), recorded so a later loading change is diffable against a fixed reference. |
| [`specialist-depth-progressive-loading-proof.md`](specialist-depth-progressive-loading-proof.md) | Benchmark-backed behavioral proof (#411) that `specialist-depth`'s conditional, fail-closed loading (#410) is safe and stable relative to the baseline above: the surface a "not needed" review no longer has to apply, a live-run confirmation that the regression set is unchanged, and live-run confirmation that activation-case review judgment (not exact matcher output — see the doc's §4 caveat) is correct. |
| [`specialist-depth-continuation-checkpoint.md`](specialist-depth-continuation-checkpoint.md) | Architecture reassessment checkpoint (#412) deciding, from the two records above, whether to repeat the `specialist-depth` extraction pattern for another capability: yes, for exactly one more capability (`scale`) as an #403 child issue rather than a batch, and no, do not generate a runtime routing projection from the manifest yet. |

## Why this record exists

The repository grew to ~110,000 words of canonical review instruction
across `shared/` and `skills/`, in a link graph whose 38 nodes form a
single 35-node strongly-connected component. A review cannot cheaply
determine what it does *not* need to read. That is a latency and
token-consumption problem before it is a maintenance problem, and the two
have the same root cause: **no capability boundary in this repository is
expressed as a loading boundary.**

## Related

- The system map this record proposes to evolve:
  [`../ARCHITECTURE.md`](../ARCHITECTURE.md).
- The measurement architecture this record must not contradict, and whose
  "no duplicate reviewer/runner/evaluator implementations" invariant it
  inherits:
  [`../benchmark-measurement-architecture/README.md`](../benchmark-measurement-architecture/README.md).
- The existing structural-decomposition inventory this record supersedes
  in scope (file-size seams) but not in authority:
  [`../large-file-decomposition.md`](../large-file-decomposition.md).
- The capability-composition contract this record proposes to promote into
  a loading contract:
  [`../../shared/policies/specialist-depth.md`](../../shared/policies/specialist-depth.md).
- The trust architecture that constrains what may ever be lazy-loaded:
  [`../threat-model/threat-model.md`](../threat-model/threat-model.md).
