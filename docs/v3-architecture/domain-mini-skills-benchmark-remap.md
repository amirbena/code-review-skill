# Domain mini-skill benchmark re-mapping (Issue #846)

Re-maps the v2 deepening benchmark cases under `benchmark/corpus/` to the v3
domain mini-skills. Explanatory only: the fixtures stay where they are, and the
uplift cases themselves are added in the benchmark child of Epic #841.

## Classes

Cases are classified by the reasoning needed to detect the defect, not by how
many files it touches.

- **core-floor** — `review-core` should detect it alone, from the diff, the
  changed files read in full and one reference hop. Scored without a
  mini-skill; it is not uplift.
- **uplift** — detection genuinely benefits from domain expertise: tracing
  entry points or invariants the diff does not show, engine or ecosystem
  semantics, or threat reasoning. Scored with and without the skill; the
  difference is the skill's uplift.
- **clean-guard** — expected clean. Neither the Core nor the skill may report a
  finding; one would be a false positive.

This is a judgment recorded per case, not a computed rule. A `core-floor` case
may still carry optional depth P2 findings; those are the skill's to measure.

Fixtures follow [`packaged-file-disposition.md`](packaged-file-disposition.md):
supply-chain cases belong to `review-security`, the rest to `review-backend`.
No v2 corpus exercises `review-frontend`; its cases arrive with the benchmark
child.

## `review-security`

| Case | Corpus | Class | Why |
| --- | --- | --- | --- |
| `security-deepening-alternate-path-missing-check` | `security-deepening` | uplift | The missing check is on a second route the diff does not touch; finding it means enumerating every entry point to the privileged helper. |
| `security-deepening-auth-module-no-trust-boundary-clean` | `security-deepening` | clean-guard | Expected clean. |
| `security-deepening-confused-deputy-worker-credential` | `security-deepening` | core-floor | The function itself transfers funds with the worker's credential on payload data and no authorization check; visible in the changed code, so the Core must catch it. |
| `security-deepening-filename-signal-suppressed-clean` | `security-deepening` | clean-guard | Expected clean. |
| `security-deepening-sanitization-assumption-bypass` | `security-deepening` | uplift | The bypass depends on an invariant other callers rely on (the value stays sanitized); the decode-after-sanitize order only matters once that is traced. |
| `security-deepening-single-caller-check-enforced-clean` | `security-deepening` | clean-guard | Expected clean. |
| `dependency-supply-chain-deepening-major-version-breaking-api-change` | `dependency-supply-chain-deepening` | core-floor | The changed dependency version plus one grep of the removed call site; the removed function is the evidence. |
| `dependency-supply-chain-deepening-no-manifest-touched-not-implicated-clean` | `dependency-supply-chain-deepening` | clean-guard | Expected clean. |
| `dependency-supply-chain-deepening-runtime-minimum-raised` | `dependency-supply-chain-deepening` | core-floor | The raised minimum contradicts the README in the repository; plain consistency check. |
| `dependency-supply-chain-deepening-safe-patch-bump-clean` | `dependency-supply-chain-deepening` | clean-guard | Expected clean. |
| `dependency-supply-chain-deepening-transitive-dependency-expansion` | `dependency-supply-chain-deepening` | uplift | Needs lockfile-versus-manifest reasoning to see packages the one new dependency does not explain. |
| `dependency-supply-chain-deepening-unpinned-github-actions-reference` | `dependency-supply-chain-deepening` | uplift | Mutable-tag risk is supply-chain knowledge, not a behavior change a functional read flags. |

## `review-backend`

| Case | Corpus | Class | Why |
| --- | --- | --- | --- |
| `api-compat-add-enum-member-context-dependent` | `api-compatibility` | clean-guard | Expected clean. |
| `api-compat-add-optional-field-compatible` | `api-compatibility` | clean-guard | Expected clean. |
| `api-compat-optional-to-required-breaking` | `api-compatibility` | core-floor | The contract change is the diff itself. |
| `api-compat-remove-enum-member-breaking` | `api-compatibility` | core-floor | The contract change is the diff itself. |
| `api-compat-remove-field-breaking` | `api-compatibility` | core-floor | The contract change is the diff itself. |
| `api-compat-rename-response-property-breaking` | `api-compatibility` | core-floor | A rename is a removal plus an addition to any consumer; visible in the diff. |
| `database-migration-deepening-additive-nullable-column-clean` | `database-migration-deepening` | clean-guard | Expected clean. |
| `database-migration-deepening-comment-only-edit-not-implicated-clean` | `database-migration-deepening` | clean-guard | Expected clean. |
| `database-migration-deepening-destructive-drop-column` | `database-migration-deepening` | core-floor | A plain column drop on a live table with no deprecation; visible in the migration. |
| `database-migration-deepening-dynamodb-conditional-write-no-data-model-change-clean` | `database-migration-deepening` | clean-guard | Expected clean. |
| `database-migration-deepening-dynamodb-gsi-backfill-missing` | `database-migration-deepening` | uplift | Needs DynamoDB semantics: a new GSI is sparse until existing items are backfilled. |
| `database-migration-deepening-expand-contract-safe-clean` | `database-migration-deepening` | clean-guard | Expected clean. |
| `database-migration-deepening-mongodb-document-shape-rename` | `database-migration-deepening` | core-floor | Code reads only the new field while existing documents hold the old one; generic old-data reasoning. |
| `database-migration-deepening-nullable-to-non-null-no-backfill` | `database-migration-deepening` | core-floor | The model docstring states NULL rows exist and the migration adds no backfill. |
| `database-migration-deepening-unsafe-online-blocking-lock` | `database-migration-deepening` | uplift | Needs engine knowledge that a plain unique index build blocks writes on a large live table. |
| `distributed-systems-deepening-concurrent-interleaving-inventory-race` | `distributed-systems-deepening` | core-floor | Unguarded read-then-write under a threaded server; a classic race visible in the function. |
| `distributed-systems-deepening-filename-signal-suppressed-clean` | `distributed-systems-deepening` | clean-guard | Expected clean. |
| `distributed-systems-deepening-not-materially-implicated-clean` | `distributed-systems-deepening` | clean-guard | Expected clean. |
| `distributed-systems-deepening-ownership-assumption-violated` | `distributed-systems-deepening` | uplift | Needs the leader-only write assumption established elsewhere, then a bypassing path found. |
| `distributed-systems-deepening-retry-idempotency-guarded-clean` | `distributed-systems-deepening` | clean-guard | Expected clean. |
| `distributed-systems-deepening-retry-interaction-missing-idempotency` | `distributed-systems-deepening` | uplift | Needs the queue's at-least-once guarantee combined with a non-idempotent charge. |
| `performance-deepening-batched-fix-bounded-clean` | `performance-deepening` | clean-guard | Expected clean. |
| `performance-deepening-blocking-io-request-hot-path` | `performance-deepening` | core-floor | A blocking read moved from startup into the request path; visible in the diff. |
| `performance-deepening-constant-size-loop-clean` | `performance-deepening` | clean-guard | Expected clean. |
| `performance-deepening-n-plus-one-remote-call-in-loop` | `performance-deepening` | core-floor | A batched call became one call per element of an input the docstring calls unbounded. |
| `performance-deepening-nested-unbounded-scan-quadratic` | `performance-deepening` | core-floor | A set lookup became a list scan inside a loop; visible in the diff. |
| `performance-deepening-non-executed-config-constant-not-implicated-clean` | `performance-deepening` | clean-guard | Expected clean. |
| `deployment-infrastructure-deepening-comment-and-unused-label-edit-not-activated-clean` | `deployment-infrastructure-deepening` | clean-guard | Expected clean. |
| `deployment-infrastructure-deepening-db-resize-impact-needs-plan-output` | `deployment-infrastructure-deepening` | clean-guard | Expected clean. |
| `deployment-infrastructure-deepening-dockerfile-from-only-boundary-clean` | `deployment-infrastructure-deepening` | clean-guard | Expected clean. |
| `deployment-infrastructure-deepening-helm-value-key-renamed-template-unresolved` | `deployment-infrastructure-deepening` | core-floor | One reference hop from the renamed key finds the template still reading the old one. |
| `deployment-infrastructure-deepening-memory-limit-raise-consistent-clean` | `deployment-infrastructure-deepening` | clean-guard | Expected clean. |
| `deployment-infrastructure-deepening-probe-port-no-longer-matches-listener` | `deployment-infrastructure-deepening` | core-floor | One reference hop from the changed port finds the probes and service still on the old one. |
| `deployment-infrastructure-deepening-smoke-test-failure-no-longer-gates-deploy` | `deployment-infrastructure-deepening` | core-floor | continue-on-error on the only gate before production; visible in the workflow. |
| `deployment-infrastructure-deepening-workflow-permissions-widened` | `deployment-infrastructure-deepening` | uplift | Needs CI threat reasoning: write token plus a pull_request trigger running untrusted code. |
