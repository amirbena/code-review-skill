# v3 packaged-file disposition

Companion to [`adr-v3-review-core.md`](adr-v3-review-core.md). It
classifies **every** packaged file under `skills/*/**` and `shared/**` at
v2.0.0 (`0369f40`, 91 files) into exactly one destination:

- **Core**: content moves into `review-core`.
- **a named mini-skill**: content moves into that Skill.
- **Removed**: not migrated. See ADR §6.

A file whose content splits is listed under its **primary** destination,
and the reason names where the rest goes. "Core" means the content is
condensed into the Core's `SKILL.md`, its rule files or its report
template. It does not mean the file moves verbatim. Implementing children
choose the exact file layout within the ADR §4 target shape.

## Summary

| Destination | Files |
| --- | ---: |
| `review-core` | 28 |
| `review-publish-github` | 9 |
| `review-requirements` | 3 |
| `review-deep-investigation` | 5 |
| `review-suggestions` | 3 |
| `review-security` | 1 |
| `review-backend` | 5 |
| `review-frontend` | 3 |
| `review-runtime-check` | 2 |
| Removed | 32 |
| **Total** | **91** |

## `shared/policies/`

| File | Destination | Reason |
| --- | --- | --- |
| `README.md` | Removed | v3 has no `shared/` directory to navigate. |
| `affected-test-analysis.md` | `review-deep-investigation` | Tracing a behavior change into tests outside the diff is deep investigation. |
| `agent-delegation.md` | Removed | `spawn_agent` and agent delegation are removed (ADR §6). |
| `api-contract-compatibility.md` | `review-backend` | API/contract compatibility is backend domain depth. |
| `architectural-placement.md` | `review-deep-investigation` | Ring-by-ring lifecycle placement reasoning lifts the Core investigation bound. |
| `change-risk-signals.md` | Removed | Change-risk depth classification is removed. |
| `code-hygiene.md` | `review-suggestions` | Hygiene is non-blocking P2 suggestion work. |
| `database-migration-deepening.md` | `review-backend` | DB and migrations are backend domain depth. |
| `dependency-tree-inspection.md` | Removed | Dependency-tree inspection is a removed context source; supply-chain reasoning moves with `review-scope.md` to `review-security`. |
| `deployment-infrastructure-deepening.md` | `review-backend` | Deployment and config are backend domain depth. |
| `design-reference.md` | `review-frontend` | Design-reference comparison is part of rendered UI review. |
| `distributed-systems-deepening.md` | `review-backend` | Concurrency and distributed systems are backend domain depth. |
| `engineering-design-deepening.md` | `review-suggestions` | Design-content review produces non-blocking design suggestions. |
| `evidence.md` | Core | Owns the evidence rule (S4). |
| `failure-retry-recovery.md` | `review-deep-investigation` | Failure, retry and recovery reasoning is deep investigation. |
| `file-reviewability.md` | Core | Generated/unreadable-file handling feeds Core `REVIEW INCOMPLETE` trigger 2. |
| `git-safety.md` | Core | No-destructive-Git (S10). |
| `invocation-options.md` | Removed | The invocation-options matrix is removed; the Core has no presentation options. |
| `jira-context.md` | `review-requirements` | Read-only Jira resolution (S9). |
| `large-pr-partitioning.md` | Removed | Deterministic large-PR partitioning is removed. |
| `mutation-authority.md` | Core | Read-only posture (S1); the mutation capability pipeline is removed. |
| `null-absence-risk.md` | `review-deep-investigation` | Null-absence reasoning is deep investigation. |
| `parallel-review.md` | Removed | Parallel review is removed. |
| `performance-deepening.md` | `review-backend` | Performance is backend domain depth. |
| `reasoning-checkpoint.md` | Removed | The reasoning checkpoint is removed. |
| `remediation-guidance.md` | Core | Becomes the finding's `fix` field: focused, actionable guidance in every finding; the option-gated guidance is removed. |
| `remediation-scope-boundary.md` | `review-suggestions` | Its P2 side becomes suggestions; the mandatory Core step is removed (ADR §6). |
| `rendered-inspection-environment.md` | `review-frontend` | Render-consent gate and Playwright check for rendered inspection. |
| `rendered-inspection.md` | `review-frontend` | Rendered-UI inspection. |
| `repository-expansion.md` | `review-deep-investigation` | Wider repository tracing is what lifts the bound. |
| `repository-instructions.md` | Core | Target-repo instructions inform conventions only (S5). |
| `requirement-coverage.md` | `review-requirements` | Per-requirement verification status. |
| `review-base-policy.md` | Removed | A workflow-policy finding, not defect detection (ADR §6, added). |
| `review-context.md` | `review-requirements` | Deep requirement/scope context; the Core keeps only the target vs. untrusted-context distinction. |
| `review-evidence.md` | `review-publish-github` | Existing Review Evidence reconciliation decides what is published. |
| `review-ownership.md` | Removed | Review ownership (`REVIEW ALREADY OWNED`) is removed. |
| `review-scope.md` | Core | What is examined, candidate validation, implication checklist, bounded investigation. Its depth-owner sections follow their mini-skill: supply chain → `review-security`, the others per this table. |
| `review-stopping-criteria.md` | Removed | The stopping-criteria pass family and mandatory-loading checkpoint are removed. |
| `root-cause-consolidation.md` | Core | Root-cause dedup; the deep model-completeness pass goes to `review-deep-investigation`. |
| `runtime-validation.md` | `review-runtime-check` | Sandboxed execution to confirm a finding (S8). |
| `security-deepening.md` | `review-security` | Security deepening. |
| `severity.md` | Core | P0/P1/P2 semantics. |
| `specialist-depth.md` | Removed | Specialist-depth activation predicates are removed; mini-skills are selected by model judgment (ADR §5.1). |
| `structured-output.md` | Core | JSON result kept for the benchmark adapter. |
| `trusted-host-execution.md` | `review-runtime-check` | Host execution only with explicit per-invocation authorization (S8). |
| `verdict-consistency.md` | Core | Folded into the mechanical decision rule (S3); the separate comparator pass is removed. |
| `workspace-sibling-context.md` | Removed | Workspace-sibling context is removed. |

## `shared/templates/`

| File | Destination | Reason |
| --- | --- | --- |
| `finding-rendering-human.md` | Core | Its senior-voice contract becomes the Core's single voice; the opt-in human projections are removed. |
| `finding-rendering.md` | Core | Report projection of a finding; the inline-comment projection goes to `review-publish-github`. |
| `finding.md` | Core | Reduced to the minimal finding shape: severity, title, location, evidence, impact, fix. |
| `review-summary.md` | Core | Becomes the single Core report template. |

## `skills/github-pr-review/`

| File | Destination | Reason |
| --- | --- | --- |
| `README.md` | Removed | Replaced by the `review-core` and `review-publish-github` READMEs (#850). |
| `SKILL.md` | Core | PR as a Core diff source; the delivery half goes to `review-publish-github`. |
| `agents/openai.yaml` | Removed | Each v3 Skill ships its own adapter (#851). |
| `metadata/skill.yaml` | Removed | Each v3 Skill ships its own metadata (#851). |
| `policies/finding-placement.md` | `review-publish-github` | Inline vs. body placement is a publication decision. |
| `policies/github-review.md` | Removed | A policy index for a load set v3 does not have. |
| `policies/parallel-review.md` | Removed | Parallel review is removed. |
| `policies/pr-scope.md` | Core | Complete PR diff retrieval at a recorded HEAD; prior-activity awareness goes to `review-publish-github`. |
| `policies/repository-checkout.md` | Core | Isolated temporary clone, always cleaned up (S10). |
| `policies/review-action-authorization.md` | `review-publish-github` | PASSIVE/SEMI/ACTIVE collapses to "invoking this Skill is the request"; SEMI is removed. |
| `policies/review-authority.md` | `review-publish-github` | Never approves its own work (S7). |
| `policies/review-context.md` | Core | Thin PR application of the target model. |
| `policies/review-evidence.md` | `review-publish-github` | Reconciliation with existing PR comments. |
| `policies/review-output.md` | `review-publish-github` | Batched submission and HEAD revalidation (S7); HEAD-moved also becomes Core trigger 3. |
| `policies/review-reasoning.md` | Core | Review reasoning over the change. |
| `policies/review-status-enforcement.md` | Removed | The machine-readable review status and required-check setup are removed. |
| `policies/reviewer-brief.md` | Removed | The Reviewer Brief is removed. |
| `policies/reviewer-delta-review.md` | Removed | Reviewer-mode delta selection is removed. |
| `policies/stacked-pr-review.md` | Removed | Stacked-PR policy is removed. |
| `policies/stateful-delta-rereview.md` | Removed | SHA-bound stateful delta re-review is removed. |
| `policies/structured-output.md` | Core | Merged into the one Core JSON result. |
| `policies/workspace-sibling-context.md` | Removed | Workspace-sibling context is removed. |
| `runbooks/active-pr-review.md` | `review-publish-github` | Its publish steps become the inline procedure in that Skill's `SKILL.md`. |
| `runbooks/passive-pr-review.md` | Core | Its review steps become the inline procedure in the Core `SKILL.md`. |
| `templates/external-review-summary.md` | `review-publish-github` | The published review body. |
| `templates/inline-finding.md` | `review-publish-github` | The inline review comment. |
| `templates/reviewer-brief.md` | Removed | The Reviewer Brief is removed. |

## `skills/local-code-review/`

| File | Destination | Reason |
| --- | --- | --- |
| `README.md` | Removed | Replaced by the `review-core` README (#850). |
| `SKILL.md` | Core | Local change as a Core diff source. |
| `agents/openai.yaml` | Removed | Each v3 Skill ships its own adapter (#851). |
| `metadata/skill.yaml` | Removed | Each v3 Skill ships its own metadata (#851). |
| `policies/external-contract-context.md` | Removed | External-contract context is removed. |
| `policies/invocation-approval.md` | Core | Explicit per-run request (S2), generalized to every v3 Skill. |
| `policies/multi-repository-review-target.md` | Removed | Multi-repository Review Targets are removed. |
| `policies/pr-context.md` | Removed | Local Existing Review Evidence is removed (ADR §6, added). |
| `policies/repository-state.md` | Core | Committed/staged/unstaged/untracked resolution; the staged-delta fingerprint is removed. |
| `policies/review-context.md` | Core | Thin local application of the target model. |
| `policies/workspace-sibling-context.md` | Removed | Workspace-sibling context is removed. |
| `runbooks/local-review.md` | Core | Its steps become the inline procedure in the Core `SKILL.md`. |
| `templates/local-review-report.md` | Core | Merged into the single Core report template. |
