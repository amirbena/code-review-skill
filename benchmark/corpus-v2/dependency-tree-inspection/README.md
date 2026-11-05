# Dependency Tree Inspection Regression Corpus

Repository-development artifact for GitHub Issue
[#732](https://github.com/amirbena/code-review-skill/issues/732) (parent
[#731](https://github.com/amirbena/code-review-skill/issues/731)). A
network-free `benchmark-case/v2` sub-corpus that measures the opt-in dependency
tree inspection of
[`../../../shared/policies/dependency-tree-inspection.md`](../../../shared/policies/dependency-tree-inspection.md)
(#730) on **synthetic** Base and Head trees. Every case is labeled synthetic:
its tree text is crafted, never real tool output, and the tool format it
imitates is recorded in the case. The original private BOM incident is **not**
reproduced and is never claimed to be.

Measurement design, arms, pre-registered acceptance, and status:
[`../../../runtime_platform/benchmark/dependency-tree-inspection-measurement.md`](../../../runtime_platform/benchmark/dependency-tree-inspection-measurement.md).
Fixture input: `input.dependency_trees`,
[`fixture-format.md`](../../../runtime_platform/benchmark/fixture-format.md) §6.7.
The pre-registered protocol is committed in [`pre-registration.json`](pre-registration.json).

## Cases

All cases change one line, the `acme-platform-bom` version in `pom.xml`
(except the patch-bump control, which moves `spring-core`), against a base whose
`docs/security-policy.md` requires FIPS-only runtime crypto.

| Group | Cases |
| --- | --- |
| Incident shape, added | `dti-incident-added-user-provided`, `-authorized-execution`, `-blocked-then-provided`, `dti-incident-supplied-text-contains-instructions` |
| Incident shape, renamed | `dti-incident-renamed-user-provided`, `-authorized-execution` |
| Evidence | `dti-head-only-no-introduction-claim`, `dti-base-only-no-comparison`, `dti-malformed-output`, `dti-incomplete-resolution-error`, `dti-incomplete-missing-pom-warning`, `dti-incomplete-truncated-output`, `dti-wrong-project`, `dti-unidentified-side`, `dti-mismatched-commands`, `dti-mismatched-profiles` |
| Workflow | `dti-user-declines-output`, `dti-blocked-then-declined` |
| Controls | `dti-control-routine-patch-bump`, `-unrelated-churn`, `-test-scope-only`, `-same-family-no-documented-incompatibility` |

Authorized-execution cases never run a real build: the runner offers a
fixture-local `cat` of the recorded text as the approved command.
