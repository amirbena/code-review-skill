# Dependency-Graph Regression Review — Design Record

Repository-development design record for reviewing the **resolved** impact
of a dependency change: Base→Head dependency-graph delta analysis, the
resolution-acquisition decision and its threat model, and the claim,
severity, and finding contracts that keep such a review honest.

Like [`../dependency-supply-chain/README.md`](../dependency-supply-chain/README.md),
[`../workspace-sibling-context/README.md`](../workspace-sibling-context/README.md),
and [`../finding-confidence/README.md`](../finding-confidence/README.md), this
is a repository-development doc: **not** packaged into either Skill archive,
and no packaged Skill resource depends on it. The normative, adapter-neutral
contract lives in
[`../../shared/policies/dependency-graph-regression.md`](../../shared/policies/dependency-graph-regression.md),
which is **unwired**: no `SKILL.md`, runbook, adapter policy, or capability
manifest references it until [#724](https://github.com/amirbena/code-review-skill/issues/724).
No review behavior changes ship with this record. The `metadata-resolution` path is approved in principle and **not enabled**: the policy's "Production-enablement gates" own what must pass first.

Issue: [#723](https://github.com/amirbena/code-review-skill/issues/723)
(parent Epic [#722](https://github.com/amirbena/code-review-skill/issues/722);
implementation #724, benchmark gate #725, Wiki #726).

## Core invariant

**A resolved graph is evidence of what resolves, never proof of what breaks;
and no acquired, bound graph means no graph claim.**

## Document map

| Document | Owns |
| --- | --- |
| [`../../shared/policies/dependency-graph-regression.md`](../../shared/policies/dependency-graph-regression.md) | The **normative contract** — graph model, delta semantics, evidence states, claim strength, severity table, finding contract. Canonical and unwired. |
| [`dependency-graph-regression-model.md`](dependency-graph-regression-model.md) | Why the model is shaped this way: worked examples (the incident, npm, Gradle), the evidence-state examples, claim strength, severity rationale, interaction decisions, and the #724/#725 hand-off. Explanatory. |
| [`resolution-acquisition.md`](resolution-acquisition.md) | The resolution-acquisition decision with rejected alternatives, the per-adapter workflow, safe parsing per format, the threat-model mapping, and the **proposed maintainer decision** that reduces the Epic's Maven scope. Explanatory. |
| [`metadata-only-resolution.md`](metadata-only-resolution.md) | Maintainer-directed research into resolving a Maven graph from POM metadata without repository-controlled code: the three-way distinction, evaluation criteria, variants, comparison with admitted paths, the incident reconstructed from public POMs, and the approvals (D1–D6) it would need. Classified **B**. |
| [`fidelity-study.md`](fidelity-study.md) | Maintainer-directed fidelity study of a pinned, metadata-only resolver against real Maven on trusted synthetic projects and the real Spring Cloud / BouncyCastle chain; security observations; the dedicated-cache decision; the recommended offline architecture; the exact D1/D4/D5/D6 approval requirements; remaining risks; readiness. Research artifacts in [`fidelity-study/`](fidelity-study/README.md). |
| [`root-cause-replay.md`](root-cause-replay.md) | The root-cause investigation of the missed Maven BOM regression: method, trace, classification, and what could not be determined. |

## Related

- Existing diff-text dependency deepening (unchanged, keeps running in every
  state): [`../dependency-supply-chain/README.md`](../dependency-supply-chain/README.md)
  (#181; corpus #188).
- Activation contract this composes under, never redefines:
  [`../../shared/policies/specialist-depth.md`](../../shared/policies/specialist-depth.md) (#82).
- Execution boundaries this record leaves unchanged:
  [`../../shared/policies/runtime-validation.md`](../../shared/policies/runtime-validation.md),
  [`../../shared/policies/trusted-host-execution.md`](../../shared/policies/trusted-host-execution.md),
  and `skills/github-pr-review/policies/repository-checkout.md`.
- Threat scenarios: INJECT-021–029, SCOPE-007, DOS-009–010, and
  GIT-010 in [`../threat-model/catalog/`](../threat-model/catalog/README.md).
- Severity, evidence, and the finding shape, all unchanged:
  [`../../shared/policies/severity.md`](../../shared/policies/severity.md),
  [`../../shared/policies/evidence.md`](../../shared/policies/evidence.md),
  [`../../shared/templates/finding.md`](../../shared/templates/finding.md).
- External contract and sibling context (repository identity is never taken
  from a dependency declaration): #133, #645,
  [`../workspace-sibling-context/README.md`](../workspace-sibling-context/README.md).
- Repository test execution backend (#535): unchanged and not a graph
  acquisition path.

## Non-goals

- Implementation, wiring, or benchmark execution (#724, #725).
- A hardcoded BouncyCastle (or any per-library) rule, a CVE/SCA scanner, or
  a license-policy engine.
- Changing severity definitions, `confidence` values, decision tokens, or
  the decision derivation. No literal P3 is introduced.
- Granting execution or network access. Any such path needs a separate,
  maintainer-approved amendment to the owning policy.
