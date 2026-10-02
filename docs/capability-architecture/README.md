# Capability Architecture

Repository-development **research record** for how this repository's two
Code Review Agent Skills should be decomposed into independently loadable
capabilities, and what repository topology should hold them.

Like [`../benchmark-measurement-architecture/README.md`](../benchmark-measurement-architecture/README.md),
[`../candidate-finding-validation/README.md`](../candidate-finding-validation/README.md),
and [`../repository-intelligence/README.md`](../repository-intelligence/README.md),
this is a repository-development doc: **not** packaged into either Skill
archive, and no packaged Skill resource depends on it.

It began as a **research recommendation, not a contract change**, and
part of it has since shipped. Every canonical rule named below still lives
exactly where [`../ARCHITECTURE.md`](../ARCHITECTURE.md) and
[`../../shared/policies/README.md`](../../shared/policies/README.md) say it
lives: no policy's canonical ownership has changed, no repository has been
created, and the model doc's recommended topology (a modular monorepo) is
what exists.

## Current shipped state

What exists on `main` today, split by where it takes effect:

- **Declarative and build-time (CI-checked).** 17 manifests,
  `capabilities/*/capability.yaml`, declare each capability's files,
  activation, adapters, `requires:` and `never:` clauses. They drive the
  generated `scripts/packaging/package-manifest.json` and each Skill's
  `metadata/skill.yaml` `shared:` lists, plus per-adapter subset checks;
  CI fails when a committed generated file diverges. Field-level detail:
  [`capability-manifest-schema.md`](capability-manifest-schema.md).
- **Enforced at review time, by policy text only.** Conditional,
  fail-closed loading is stated in canonical policy text for exactly two
  capabilities, `specialist-depth` and `scale`, with proof records below.
  The model reads and follows that text; **no mechanical runtime loader**
  reads the manifests or decides what a review loads. Every other
  capability's `activation:` is a declaration, not an enforced load gate.
- **Not built.** A runtime routing projection generated from the
  manifests, per-adapter shared packaging (both archives still ship the
  whole `shared/` tree), per-capability file relocation under
  `capabilities/`, and manifests for the targets listed below.

**Unmanifested `requires:` targets.** These names appear in manifests'
`requires:` lists but have no `capabilities/<name>/capability.yaml` yet:
`capability-posture`, `review-router`, `review-kernel`, `finding-contract`,
and `review-context-core`. No check resolves these `requires:` entries
against a manifest today.

## Document map

| Document | Owns |
| --- | --- |
| [`capability-architecture-model.md`](capability-architecture-model.md) | The current-state diagnosis with measured evidence, the proposed capability map and load tiers, the progressive-loading design, the local/GitHub adapter relationship, the evaluation of the three repository models and the recommended topology, current and target dependency graphs, per-capability contracts, benchmark ownership, the performance-measurement plan, the migration sequence and its first extraction, risks and rollback, and the follow-up issue breakdown. |
| [`capability-loading-baseline.md`](capability-loading-baseline.md) | The pre-`specialist-depth`-extraction baseline (§I.2): today's packaged instruction-surface word/token counts attributed by capability, and the current values of the existing quality-metric contracts (#55/#56/#57), recorded so a later loading change is diffable against a fixed reference. |
| [`specialist-depth-progressive-loading-proof.md`](specialist-depth-progressive-loading-proof.md) | Benchmark-backed behavioral proof (#411) that `specialist-depth`'s conditional, fail-closed loading (#410) is safe and stable relative to the baseline above: the surface a "not needed" review no longer has to apply, a live-run confirmation that the regression set is unchanged, and live-run confirmation that activation-case review judgment (not exact matcher output — see the doc's §4 caveat) is correct. |
| [`specialist-depth-continuation-checkpoint.md`](specialist-depth-continuation-checkpoint.md) | Architecture reassessment checkpoint (#412) deciding, from the two records above, whether to repeat the `specialist-depth` extraction pattern for another capability: yes, for exactly one more capability (`scale`) as an #403 child issue rather than a batch, and no, do not generate a runtime routing projection from the manifest yet. |
| [`scale-progressive-loading-proof.md`](scale-progressive-loading-proof.md) | Second proof point (#447), continuing #412's decision: `scale`'s conditional, fail-closed loading, the static instruction-surface reduction it makes possible, and the reconciliation of `repository-expansion.md`'s pre-existing "always active" framing against `capability.yaml`'s `on-activation` declaration. |
| [`benchmark-ownership-boundary-checkpoint.md`](benchmark-ownership-boundary-checkpoint.md) | Ownership-boundary decision record (#425), unblocked by #329 and #412 both closing: `benchmark/`'s corpus, contracts, and harness are benchmark/evaluation infrastructure, not generic documentation; relocation should follow §E.2's `runtime_platform/benchmark/` + `capabilities/<name>/corpus/` split but is sequenced behind capability-body extraction rather than moved as one batch, and is not performed by this record. **Corpus direction amended by #578** (root `benchmark/`). |
| [`benchmark-root-ownership-decision.md`](benchmark-root-ownership-decision.md) | Decision record (#578) amending the checkpoint above: ratifies a root `benchmark/` for corpus, index, examples and operator/routine content, fixes the final ownership table and the `benchmark/` vs `runtime_platform/benchmark/` boundary, classifies `cloud-routine-integration.md` as executable benchmark content, and defers the per-capability corpus split. Moves no file. |

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
