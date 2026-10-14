# Deployment & Infrastructure Deepening Regression Fixture Corpus

Repository-development artifact for GitHub Issue
[#743](https://github.com/amirbena/code-review-skill/issues/743), a
deterministic fixture corpus for the Deployment & Infrastructure deepening
capability delivered by
[#742](https://github.com/amirbena/code-review-skill/issues/742) under
parent [#740](https://github.com/amirbena/code-review-skill/issues/740).
It is a **focused sub-corpus** of
[`benchmark-case/v2`](../../../runtime_platform/benchmark/fixture-format.md)
fixtures; it measures the capability after it exists and does not define,
gate, or redesign it. The capability is specified in
[`../../../shared/policies/deployment-infrastructure-deepening.md`](../../../shared/policies/deployment-infrastructure-deepening.md)
and designed in
[`../../../docs/deployment-infrastructure/deployment-infrastructure-review-contract.md`](../../../docs/deployment-infrastructure/deployment-infrastructure-review-contract.md);
this corpus's expectations must stay consistent with both.

Every case is a self-contained inline `patch` plus its `base` pre-image, so
the corpus runs without network access. Like the rest of
[`../`](../README.md) it is **not** packaged into either Skill archive and
is consumed only by this repository's own test suite, through the single
reference validator
[`../../../runtime_platform/benchmark/reference/benchmark_fixture.py`](../../../runtime_platform/benchmark/reference/benchmark_fixture.py)
(never a second one). It adds no runner, lane, or scheduler; the cases are
picked up by the existing comprehensive lane through programmatic corpus
discovery.

## Selection principle

The set is representative, not a technology-by-technology matrix: it
spans Kubernetes, Helm, Terraform, and GitHub Actions, and each case
isolates one outcome so a regression in any one is unambiguous. The four
`clean`/no-blocking cases each fail a **distinct** precondition:

| File | Outcome shape | A correct review must… | Decision |
|---|---|---|---|
| [`…-probe-port-no-longer-matches-listener.yaml`](deployment-infrastructure-deepening-probe-port-no-longer-matches-listener.yaml) | real deployment defect, found through reference wiring (no manifest touched) | report one **P1**: the listen port moves to 9090 while probes and Service still target 8080 | `changes-required` |
| [`…-workflow-permissions-widened.yaml`](deployment-infrastructure-deepening-workflow-permissions-widened.yaml) | security/permission regression | report one **P1**: workflow token widened to `contents: write` on a `pull_request` workflow | `changes-required` |
| [`…-smoke-test-failure-no-longer-gates-deploy.yaml`](deployment-infrastructure-deepening-smoke-test-failure-no-longer-gates-deploy.yaml) | operational reliability regression | report one **P1**: `continue-on-error` on the smoke test lets a failing gate reach the production deploy | `changes-required` |
| [`…-helm-value-key-renamed-template-unresolved.yaml`](deployment-infrastructure-deepening-helm-value-key-renamed-template-unresolved.yaml) | configuration compatibility problem | report one **P1**: `image.tag` is renamed while the template still reads `.Values.image.tag` | `changes-required` |
| [`…-memory-limit-raise-consistent-clean.yaml`](deployment-infrastructure-deepening-memory-limit-raise-consistent-clean.yaml) | safe configuration change | report **nothing**: a resource bound loosens and stays consistent with the JVM heap | `clean` |
| [`…-db-resize-impact-needs-plan-output.yaml`](deployment-infrastructure-deepening-db-resize-impact-needs-plan-output.yaml) | missing evidence requiring a Context gap | raise **no blocking finding** and make no outage claim; at most one optional, non-asserting observation | `clean` |
| [`…-comment-and-unused-label-edit-not-activated-clean.yaml`](deployment-infrastructure-deepening-comment-and-unused-label-edit-not-activated-clean.yaml) | non-activation: manifest file, no behavior property | report **nothing** | `clean` |
| [`…-dockerfile-from-only-boundary-clean.yaml`](deployment-infrastructure-deepening-dockerfile-from-only-boundary-clean.yaml) | #181 boundary: `FROM`-only change | report **nothing** from this capability (supply-chain pass owns it) | `clean` |

The "safe change" case activates the capability (a resource-bounds property
changes) and stays quiet on evidence; the two non-activation cases fail
activation itself, for distinct reasons (no behavior property changed, and
a property owned by the dependency/supply-chain pass).

## Evaluation dimensions

| Dimension | Pinned by |
|---|---|
| Required-finding detection | the four flagged cases, one required finding each |
| False-positive behavior | the three `clean` cases with `findings: []` |
| Severity correctness | required findings are `P1`; the gap case caps its optional finding at `P1`/`P2` and its decision at `clean` |
| Evidence quality | each `claim` names the changed line **and** the consuming or contradicting artifact |
| Context-gap handling | the db-resize case (see limitations) |
| Activation correctness | non-activation and boundary cases against the four activating ones |
| Regression in existing behavior | the existing corpora and their tests, unchanged |

## Results and limitations

- **Fixture validity.** All eight cases parse and validate through the
  single reference validator, resolve every anchor inside their own patch
  or base, and are indexed under the new `deployment-infrastructure`
  capability value; this is asserted by
  [`../../../tests/unit/benchmark/test_deployment_infrastructure_deepening_corpus.py`](../../../tests/unit/benchmark/test_deployment_infrastructure_deepening_corpus.py).
- **No live reviewer run is recorded here.** Authoring this corpus did not
  run the benchmark harness (Issue #743 non-goal), so required-finding
  recall, false-positive rate, and baseline comparison against the
  existing corpora are **not yet measured**. They are produced by the next
  comprehensive-lane run, which discovers this directory automatically;
  record that run's result in the scheduled-benchmark history, and file a
  focused follow-up for any genuine defect it surfaces.
- **Context gap is not directly assertable.** `benchmark-case/v2` has no
  key for an expected Context gap, so the db-resize case pins the
  observable part (no blocking finding, no unsupported outage claim). That
  a `deployment validation evidence gap` is emitted is asserted by the
  policy tests for #742, not by this corpus. Extending the fixture format
  is out of scope.
- **Single-artifact fixtures.** Cases are small and crafted. They do not
  cover Argo CD, Jenkins, or Docker `USER`/`ENTRYPOINT` defects, and none
  exercises user-supplied validation output (`input.context` carries only
  the statement that none was supplied). Expand only with evidence that
  this set is insufficient.

## Validation

[`../../../tests/unit/benchmark/test_deployment_infrastructure_deepening_corpus.py`](../../../tests/unit/benchmark/test_deployment_infrastructure_deepening_corpus.py)
loads every `*.yaml` here through the reference validator and asserts the
set stays small and documented, every outcome shape is present, flagged
cases carry exactly one required `P1`, clean cases carry no required
finding and decide `clean`, and the non-activation cases are distinct.
