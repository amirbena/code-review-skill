# Deployment & Infrastructure Review Contract

Research record for Issue
[#741](https://github.com/amirbena/code-review-skill/issues/741), parent
Epic [#740](https://github.com/amirbena/code-review-skill/issues/740).
Docs-only: it implements nothing. It states what the deployment and
infrastructure depth reviews per technology, which evidence tier can
support each check, where execution is and is not permitted, and what
[#742](https://github.com/amirbena/code-review-skill/issues/742),
[#743](https://github.com/amirbena/code-review-skill/issues/743), and
[#744](https://github.com/amirbena/code-review-skill/issues/744) should
deliver. Every rule this record relies on is cited to the policy that
owns it; this record restates none of them as a new rule.

## 1. Summary of recommendations

1. Add **one** domain-specific deepening capability,
   `deployment-infrastructure-deepening`, as a fifth domain policy
   composed under [`specialist-depth.md`](../../shared/policies/specialist-depth.md).
   It is a second depth owner of the existing "Infrastructure /
   deployment" dimension, next to the dependency/supply-chain pass.
2. Activation is the existing two-condition specialist-depth predicate.
   The second condition is a closed list of **semantic** signals (§4),
   never a file type or path.
3. Static diff (A) and repository context (B) are the main evidence
   tiers. User-provided output (C) is accepted only after the
   validate-before-trust checks that
   [`dependency-tree-inspection.md`](../../shared/policies/dependency-tree-inspection.md)
   already uses. Authorized local execution (D) is limited to commands
   that [`runtime-validation.md`](../../shared/policies/runtime-validation.md)
   already admits. Under the safety gate, most well-known validators
   cannot run (§6).
4. When a materially implicated concern needs evidence that is
   unavailable, the review records a **Context gap**. That gap never
   creates a finding and never raises severity. This requires extending
   the Context-gaps section of `review-summary.md` by one gap kind (§9).
5. No new execution permission, approval workflow, finding field,
   confidence value, severity, review gate, benchmark input key, or
   runner.

## 2. Evidence inspected

| Area | Source | What it establishes for this contract |
| --- | --- | --- |
| Base scope | [`review-scope.md`](../../shared/policies/review-scope.md), "What is examined" and "Materially relevant concerns" | Docker, Kubernetes, Helm, Terraform, CI/CD, and GitHub Actions are already examined. Deployment safety, infrastructure behavior, and CI/CD behavior are already concerns. |
| Base dimension | `review-scope.md`, "Semantic change-implication reasoning" — "Infrastructure / deployment" | Has a base obligation: correct across reachable environments and deployment states, and fails safely when an assumed dependency is unavailable. Its only depth owner is "Dependency / supply-chain deepening review." |
| Existing depth owner | `review-scope.md`, "Dependency / supply-chain deepening review"; [`dependency-tree-inspection.md`](../../shared/policies/dependency-tree-inspection.md) | Already owns Dockerfile `FROM` base-image references, GitHub Actions `uses:` pinning and provenance, toolchain and runtime minimum bumps, and major-version compatibility. |
| Structural evidence rule | `review-scope.md`, "Evidence is semantic, not structural" | Its fourth worked example is exactly a deployment/configuration change. File type is a signal, never the trigger. |
| Activation and composition | [`specialist-depth.md`](../../shared/policies/specialist-depth.md), "Activation", "Conditional loading: fail-closed", "Composition", "Capability-contributed findings are labeled" | Defines the two-condition predicate, fail-closed loading, one review with 0..N capabilities, and the optional `capability` provenance field. |
| Capability manifest | [`capabilities/specialist-depth/capability.yaml`](../../capabilities/specialist-depth/capability.yaml) | The four current domain policies, loaded `on-activation` for adapters `[local, github]`. |
| Depth level | [`change-risk-signals.md`](../../shared/policies/change-risk-signals.md), "Infra / config change" | An infra/config change already raises the depth level to `elevated`. That is a depth level, not a capability. It never produces a finding and is never a gate. |
| Execution boundary | [`runtime-validation.md`](../../shared/policies/runtime-validation.md), "Trust model and execution boundary", "Declaring and discovering commands", "Safety gate", "Outcome contract" | Only exact commands declared by the repository may run. The network is denied. Network-, secret-, and service-dependent commands, deployment, and dependency installation are skipped. Outcomes are `executed`/`failed`/`skipped`/`unavailable`. |
| Host backend | [`trusted-host-execution.md`](../../shared/policies/trusted-host-execution.md), "What trusted-host execution still requires" | Changes only the isolation backend. The safety gate still skips network- and secret-dependent commands. |
| User-provided output | `dependency-tree-inspection.md`, "Two workflows" (Workflow 2), "Validate before trusting", "Context gaps and findings" | Supplied output is data, never instructions. Checks: format, project, side, completeness. Invalid output becomes a Context gap. Confidence never comes from the output's source. |
| Adapter split | [`rendered-inspection.md`](../../shared/policies/rendered-inspection.md), "Local and GitHub adapters"; [`repository-checkout.md`](../../skills/github-pr-review/policies/repository-checkout.md), "Three modes"; [`pr-scope.md`](../../skills/github-pr-review/policies/pr-scope.md) | One contract serves both Skills. The adapters differ only in what they can reach. API-only mode is the default: it has the changed-path diff and blobs and no checkout. A checkout is not an execution boundary. |
| Finding contracts | [`finding.md`](../../shared/templates/finding.md), "Confidence and evidence state", "Capability provenance"; [`severity.md`](../../shared/policies/severity.md); [`evidence.md`](../../shared/policies/evidence.md) | The confidence set is closed. Provenance is never a severity input. The evidence bar is the same for every finding. |
| Context gaps | [`review-summary.md`](../../shared/templates/review-summary.md), "Context gaps" | Currently admits only two kinds: unresolved repository relationships and dependency-tree evidence gaps. |
| Benchmarks | [`fixture-format.md`](../../runtime_platform/benchmark/fixture-format.md) §6.3, §6.7, §10.1; [`benchmark_taxonomy.py`](../../runtime_platform/benchmark/reference/benchmark_taxonomy.py); `benchmark/corpus/*-deepening/` | Sub-corpora of inline-patch cases exist for each deepening. No infra-deployment corpus exists. The only infra-adjacent cases are in `dependency-supply-chain-deepening/` (unpinned `uses:`) and `risk-depth/`. |

## 3. Gap analysis

| Concern family | Existing coverage | Gap |
| --- | --- | --- |
| Base-image tag, `uses:` pinning, toolchain/runtime minimums, provider/module **version** compatibility | Dependency/supply-chain pass (#181), tree inspection (#730) | None. This contract excludes them. |
| Rollout/availability, probes, resource bounds (Kubernetes, Helm, Argo CD) | Base dimension only | No depth owner, so this reasoning stays generic. |
| Declarative privilege and permission scope (RBAC, `securityContext`, workflow `permissions:`, Jenkins credential scope) | Base "Security / trust boundaries" plus `security-deepening.md` when a flow is traced | Security deepening traces data/control **flows**. Nothing owns a **configuration delta** that widens privilege when no flow is involved. |
| Config/secret reference wiring, values/template compatibility, override layering | Base dimension; generic "Findings beyond the changed lines" | No guidance on cross-file reference resolution in declarative config. |
| Destructive and state-affecting changes (Terraform replacement or destroy, Argo CD prune, immutable Kubernetes fields) | "Deployment safety" named as a concern only | No concern list and no evidence rule for "this would destroy or replace." |
| Pipeline failure propagation and deployment gates (Jenkins, GitHub Actions) | Base dimension; "Failure state, retry safety, and recovery" is application-focused | No owner for "a failure no longer stops a deploy." |
| Validator output and execution | `runtime-validation.md` (generic); dependency-tree inspection (dependency trees only) | No statement of which infra validators can and cannot pass the safety gate, and no Context-gap kind for missing infra validation evidence. |
| Benchmarks | None for this domain | #743 needs a new sub-corpus. |

## 4. Activation rules

Activation reuses `specialist-depth.md`, "Activation: evidence-driven,
never routed", without change. Both conditions must hold:

1. The base pass has materially implicated **Infrastructure /
   deployment** (`review-scope.md`).
2. That pass's own evidence shows that the change alters at least one of
   the **deployment-behavior properties** below, and that its
   correctness cannot be settled inside the base pass's bounded ring:
   - **availability and rollout**: replica count, update strategy, surge
     or unavailability bounds, disruption budgets, health/readiness
     gating, sync waves and hooks, stage ordering;
   - **resource bounds**: requests and limits, runtime memory settings
     relative to a container limit, autoscaling bounds;
   - **privilege, permission, or credential scope**: RBAC rules, security
     context, container user, workflow token permissions, credential
     binding scope, `pull_request_target`-style trust context;
   - **configuration and secret reference wiring**: a name, key, path,
     port, value key, or environment variable that one artifact defines
     and another consumes;
   - **destructive or state-affecting behavior**: replacement-forcing
     attributes, removed resources, prune or self-heal enablement,
     immutable fields, state backend or `moved`/`import` blocks;
   - **failure propagation and gating**: error swallowing, `always()` and
     `continue-on-error`-style conditions, removed approval, environment,
     or input gates, and job dependencies;
   - **startup and runtime contract**: entrypoint and command form,
     exposed or probed ports, working directory, and the runtime
     environment the application reads.

Contrasts, for #742's tests and #743's fixtures:

- A YAML file under `k8s/` whose only change is a comment, a label used by
  no selector, or key reordering does **not** activate.
- A change to an application's default listen port in application config,
  with no manifest touched, **does** activate when the repository's
  manifest probes or routes to the old port. The signal is the reference
  wiring, not the file type.
- A Dockerfile change to `FROM` only is handled by the dependency/supply-chain
  pass. This depth activates only if the same diff also changes a
  property above, such as `USER` or `ENTRYPOINT`.
- A GitHub Actions `uses:` bump is handled by the dependency/supply-chain
  pass. A `permissions:` widening in the same file activates this depth.

Loading is fail-closed (`specialist-depth.md`, "Conditional loading"):
when evaluation is ambiguous, the capability loads. Loading it never
narrows the base obligation. Explicit user focus ("focus on deployment
safety") adds depth only, per "Explicit user focus: additive only."
There is no new review gate and no new depth level. The existing
`elevated` level from `change-risk-signals.md` is unchanged and remains
independent of this capability.

## 5. Concerns per technology and evidence tier

Tiers: **A** static diff inspection; **B** repository context (unchanged
files at Base or Head); **C** user-provided validation output validated
per §7; **D** authorized local execution per §6. "Unsupported" means no
tier available to either Skill can establish the check. When such a check
is material to a specific concern, it is disclosed as a Context gap
(§9). It is never guessed and never reported as passed.

A finding requires evidence from A or B, or from validated C or
executed D tied to the changed lines. Tiers C and D strengthen or settle
a concern. Their absence never creates one.

### 5.1 Kubernetes

| Concern | A | B | C | D | Unsupported |
| --- | --- | --- | --- | --- | --- |
| Deployment/Service config: selector and label match, `targetPort` vs container port, namespace consistency | ✓ | ✓ manifests elsewhere in the repository | rendered or `kubectl` output | schema check only (`kubeconform`-class, offline schemas, repository-declared) | live cluster objects, admission or mutating webhooks |
| Readiness/liveness/startup probes: path and port match the application's listener; liveness depending on a downstream dependency; thresholds vs known startup work | ✓ | ✓ application listener/config | events or describe output | — | real startup latency, real probe behavior |
| Resource requests/limits: limit removed, request > limit, runtime heap vs memory limit | ✓ | ✓ runtime flags in image or config | metrics supplied by the user | — | actual utilization, node capacity |
| Rolling update/availability: `maxUnavailable` vs replicas, `Recreate` on a single replica, PDB vs replicas, HPA vs fixed replicas | ✓ | ✓ PDB/HPA elsewhere | — | — | cluster scheduling, real disruption |
| RBAC and security context: wildcard verbs or resources, namespaced → cluster scope, `privileged`, added capabilities, `runAsNonRoot`/`readOnlyRootFilesystem` removed, `hostPath`/`hostNetwork` | ✓ | ✓ bindings referencing the role | — | — | effective cluster policy (Pod Security admission, OPA/Kyverno) |
| ConfigMap/Secret references: referenced name or key exists, `optional`, env vs volume mount, renamed keys | ✓ | ✓ definition in the repository | rendered output | — | existence or content of objects created outside the repository; secret values are never read |

### 5.2 Helm

| Concern | A | B | C | D | Unsupported |
| --- | --- | --- | --- | --- | --- |
| Values/template compatibility: a `.Values` path renamed or removed on one side only, type changes (quoting, int vs string), `required`/`default` changes | ✓ | ✓ unchanged templates or values | `helm template` output | `helm template` / `helm lint` when repository-declared, dependencies vendored, no network | charts fetched from remote repositories |
| Rendered manifest behavior | partial (reasoning over templates) | ✓ | ✓ main path to a settled conclusion | as above | rendering with values that exist only outside the repository |
| Override behavior: per-environment values files, `--set` in pipeline or Argo CD source, precedence | ✓ | ✓ values and pipeline files in the repository | rendered output per environment | as above | overrides held in external systems |
| Deployment safety: immutable fields (selectors, `volumeClaimTemplates`), hooks and their delete policy, `helm.sh/resource-policy` removed | ✓ | ✓ | `helm diff`-class output | — | `helm upgrade --dry-run` against a cluster |

### 5.3 Argo CD

| Concern | A | B | C | D | Unsupported |
| --- | --- | --- | --- | --- | --- |
| Application config: source repo, path, `targetRevision`, destination; the path exists; revision is mutable vs pinned | ✓ | ✓ path at Head | — | — | the Argo CD server's view of the repository |
| Sync policy: `automated` enabled, `allowEmpty`, sync options (`Replace`, `ServerSideApply`) | ✓ | — | — | — | — |
| Prune and self-heal: enabling prune together with removal or renaming of tracked resources; self-heal vs intentional manual drift | ✓ | ✓ resources tracked under that path | `argocd app diff` output | — | live drift, live resource ownership |
| Ordering and dependencies: sync waves, hooks, app-of-apps dependencies, CRD before CR | ✓ | ✓ | — | — | live sync outcome |

### 5.4 Docker

| Concern | A | B | C | D | Unsupported |
| --- | --- | --- | --- | --- | --- |
| Dockerfile correctness: `COPY` sources exist and are not excluded by `.dockerignore`, stage references, `WORKDIR` | ✓ | ✓ | build log | `hadolint`-class lint when repository-declared | an actual build (needs a daemon and usually the network) |
| Runtime config: `EXPOSE`/`ENV` vs application port and config, `HEALTHCHECK` | ✓ | ✓ | — | — | — |
| Image/tag behavior in deployment manifests: mutable deployed tag combined with `imagePullPolicy`, which affects rollback determinism | ✓ | ✓ repository convention | — | — | registry contents. Base-image `FROM` belongs to #181 |
| Startup and security: shell vs exec form (signal delivery), `USER` removed or set to root, secrets in `ARG`/`ENV`/layers | ✓ | ✓ | — | — | — |

### 5.5 Terraform

| Concern | A | B | C | D | Unsupported |
| --- | --- | --- | --- | --- | --- |
| Resource changes and dependencies: references, `depends_on`, `count`/`for_each` key changes that re-address resources | ✓ | ✓ modules in the repository | `terraform plan` output | `terraform fmt -check` only | — |
| Destructive changes: replacement-forcing attribute changed, resource or module removed, `prevent_destroy` removed, a rename without a `moved` block | ✓ (credible) | ✓ | ✓ plan's replace/destroy lines can settle it | — | knowing replacement without a plan when provider semantics are not evident from the diff |
| State-related operational risk: backend, workspace, `moved`/`import`/`removed` blocks, `terraform_remote_state` consumers | ✓ | ✓ consumers in the repository | plan output | — | actual state contents, other root modules outside the repository |
| Provider/module compatibility: attribute or argument renamed or deprecated in **configuration** | ✓ | ✓ | `terraform validate` output | — | `init`/`validate`/`plan` execution (providers, network, credentials). Version-constraint compatibility belongs to #181 |

### 5.6 Jenkins

| Concern | A | B | C | D | Unsupported |
| --- | --- | --- | --- | --- | --- |
| Pipeline behavior: `when` conditions, `parallel`/`failFast`, agent and label changes | ✓ | ✓ shared library in the repository | build log | — | controller configuration, plugin versions, shared libraries outside the repository |
| Credentials handling: `withCredentials` scope widened, secrets interpolated in Groovy strings, echoed, or archived | ✓ | ✓ | — | — | credential store contents |
| Deployment stages: `input`/approval removed, branch or environment conditions changed | ✓ | ✓ | — | — | — |
| Failure propagation: `catchError`, `\|\| true`, ignored `returnStatus`, `post` blocks that mask failure | ✓ | ✓ | build log | — | — |

### 5.7 GitHub Actions

| Concern | A | B | C | D | Unsupported |
| --- | --- | --- | --- | --- | --- |
| Workflow permissions: `write-all`, widened scopes, top-level `permissions` removed, `pull_request_target`/`workflow_run` combined with a checkout of untrusted head | ✓ | ✓ reusable workflows in the repository | — | `actionlint` when repository-declared | the repository/organization default token setting (when `permissions` is absent, effective scope depends on it) |
| Secrets: secrets reaching untrusted contexts, `secrets: inherit`, `${{ github.event.* }}` interpolated into `run:` | ✓ | ✓ | — | as above | secret values |
| Deployment gates and environments: `environment:` removed or changed, `concurrency` removed from a deploy job | ✓ | ✓ | — | — | environment protection rules and required reviewers (repository settings) |
| Job dependencies and failure handling: `needs`, `if: always()`/`failure()`, `continue-on-error`, matrix `fail-fast` | ✓ | ✓ | run log | as above | — |

Action reference pinning (`uses:`) belongs to #181 and is out of scope
here.

### 5.8 Overlap with security deepening

A declarative widening of privilege (the rows above marked RBAC,
security context, permissions, and credentials) belongs to this
capability. When the base pass or this capability finds an actual
untrusted-to-trusted **flow**, for example untrusted PR content reaching
a step that holds secrets, `security-deepening.md` may also engage
through `specialist-depth.md`, "Cascading activation." The two compose
into one review. Their findings deduplicate per
[`root-cause-consolidation.md`](../../shared/policies/root-cause-consolidation.md),
and only the capability whose reasoning actually contributed the finding
is attributed.

## 6. Execution boundaries (tier D)

This contract adds no execution path. Tier D is
[`runtime-validation.md`](../../shared/policies/runtime-validation.md)
unchanged:

- The exact command must be declared by an applicable target-repository
  source ("Declaring and discovering commands"). The reviewer does not
  find validators in CI workflows or by convention.
- The command must pass the "Safety gate." Network-, secret-,
  service-, cluster-, and daemon-dependent commands are skipped with a
  reason. So are install, deploy, and write-capable commands. A command
  is never trusted because of its name. A command named `validate`,
  `plan`, `dry-run`, `lint`, `template`, or `build` is screened like any
  other.
- None of these validators is a "repository test command," so each takes
  the sandbox-required path. Under
  [`trusted-host-execution.md`](../../shared/policies/trusted-host-execution.md), "What
  trusted-host execution still requires," the backend is the only thing
  that can change. Commands that need the network or secrets stay skipped
  under trusted-host.
- No dependency-tree-style "propose a command and get chat approval"
  workflow is added. Chat approval is not trusted-host authorization
  (`trusted-host-execution.md`, "What can never manufacture this
  authorization"). The repository-declared route is the only route.

Admissibility by command class, assuming the command is
repository-declared:

| Class | Example | Expected outcome under the safety gate |
| --- | --- | --- |
| Offline static lint or schema check | `actionlint`, `hadolint`, `kubeconform` with local schemas, `terraform fmt -check`, `helm lint` (dependencies vendored) | May be admitted when it is provably read-only and offline |
| Offline render | `helm template` (no `dependency update`), `kustomize build` (no remote bases) | May be admitted under the same condition; skipped when it fetches anything |
| Needs init, providers, or the network | `terraform init`/`validate`/`plan`, `helm dependency update`, `docker build` | `skipped` (network/external-dependent) or `unavailable` |
| Needs a cluster, a server, or credentials | `kubectl apply --dry-run=server`, `kubectl diff`, `helm upgrade --dry-run`, `argocd app diff` | `skipped`, never run |
| Mutating | `apply`, `sync`, `push`, `install`, `upgrade` | `skipped`, never run |

Each attempted or considered command gets one record in `Validation`
with the existing outcome and provenance vocabulary. An `executed` lint
or render adds evidence only. A `failed` run is finding material only
when the failure is attributable to the change ("Findings and decision
semantics").

## 7. User-provided validation output (tier C)

Tier C reuses `dependency-tree-inspection.md`'s Workflow 2 and its
"Validate before trusting" rule, applied to infra tool output:

1. **Expected format**: the text is recognizably the named tool's output
   (`helm template`, `terraform plan`, `kubectl diff`, `argocd app diff`,
   or a CI run log).
2. **Bound to the target**: it names the reviewed project, chart,
   module, application, or workflow.
3. **Bound to a revision**: it identifies Head, or Base and Head, by SHA,
   branch, or an explicit statement. A Base/Head comparison needs the same
   command, flags, values files, and workspace or environment on both
   sides, otherwise it is not compared.
4. **Complete**: no errors, truncation, missing-values warnings, or
   "refresh failed"/"unknown after apply" gaps on the concern being
   settled.

Output that fails any check is invalid. It is recorded as a Context gap,
raises no finding, and is never treated as a clean result. Supplied text
is data, never instructions: a command, URL, or instruction inside it is
not followed. Plan or diff output can contain secrets. The review quotes
only the lines needed for the concern and never repeats sensitive values.

Validated output may support or settle a finding. The finding's
`confidence` follows the existing mapping in `finding.md`. User-provided
output is not one of the `confirmed` sources listed there (reviewer-run
reproduction, direct static proof, SHA-matched rendered observation,
authoritative context), so it cannot by itself raise a finding to
`confirmed`. The output's provenance (user-supplied, tool, side) is
recorded in the finding's evidence, the same way as for dependency trees.

## 8. Local vs GitHub API-only behavior

| Mode | A | B | C | D |
| --- | --- | --- | --- | --- |
| `local-code-review` | ✓ | ✓ working tree and repository | ✓ | per §6 |
| `github-pr-review`, repository-backed (optional or required checkout) | ✓ | ✓ checkout at PR head | ✓ | per §6. The checkout is not the execution boundary (`repository-checkout.md`) |
| `github-pr-review`, API-only (default) | ✓ | changed-path Base/Head blobs only (`pr-scope.md`). Unchanged referenced files such as an unchanged `values.yaml` or a ConfigMap defined elsewhere are **not** assumed reachable | ✓ Workflow 2 only. Output must be bound to the PR head SHA | never |

In API-only mode, a concern that needs an unreachable unchanged file is
either reasoned to `insufficient-context` (when the diff already shows
concrete evidence) or recorded as a Context gap. It is never resolved by
assumption. The contract adds no new GitHub API call. Repository
settings such as environment protection rules and default token
permissions stay unsupported in both Skills. Context gaps are rendered
in the review summary and never as inline comments. The publication mode
(`PASSIVE`/`SEMI`/`ACTIVE`) changes nothing in this contract.

## 9. Context gaps and unsupported checks

- Add **one** gap kind, the *deployment validation evidence gap*, to
  `review-summary.md` "Context gaps." Its fields: subject (concern and
  artifact), reason (unsupported check, execution skipped or unavailable,
  output declined or invalid, file unreachable in API-only mode), and
  the user-runnable command or evidence that would resolve it.
- A gap is emitted only for a concern this capability has materially
  activated whose resolution actually depends on the missing evidence.
  The unsupported-check columns in §5 are **not** emitted on every
  review.
- Same non-effects as existing gaps: never a finding, never raises
  severity, never changes coverage or the Decision, and no wording that
  claims the check was performed.

## 10. Findings

Findings from this capability are ordinary findings. They use
[`severity.md`](../../shared/policies/severity.md),
[`evidence.md`](../../shared/policies/evidence.md), and the
confirmed-defect / credible-engineering-risk labeling, and they carry the
optional `capability` provenance value
`deployment-infrastructure-deepening` (`finding.md`, "Capability
provenance"). This record pins no typical severity tier. The #181 model
made the same choice, because one concern can range from P0 to P2
depending on what it exposes or destroys. Depth never enlarges
remediation scope (`specialist-depth.md`, "Orthogonality to remediation
scope").

## 11. Non-goals

- A deployment engine, infrastructure manager, policy engine
  (OPA/Kyverno/Sentinel), or a replacement for `helm`, `kubeconform`,
  `terraform validate`/`plan`, `actionlint`, or CI execution.
- Guaranteeing deployment success, or reasoning about live cluster,
  cloud, registry, or Terraform state.
- Any new execution permission, approval channel, sandbox capability,
  dependency installation, network exception, or unconditional tool
  execution.
- Any new review gate, depth level, severity, finding field, confidence
  value, or schema.
- Duplicating #181/#730 (base images, `uses:` pinning, version
  constraints, dependency trees) or `security-deepening.md`'s flow
  tracing.
- Additional technologies beyond the seven in scope (for example
  Kustomize-only repositories, Pulumi, CloudFormation, GitLab CI). These
  receive base-dimension reasoning only. Extending the list is a separate
  issue.
- New child issues. The Epic's four children stay the delivery plan.

## 12. Minimal implementation proposal (#742)

Packaged changes:

1. New `shared/policies/deployment-infrastructure-deepening.md`, modeled
   on `security-deepening.md`: its sections are activation (§4), concern
   areas (§5, in compact form), evidence tiers and user output (§6–§7),
   adapters (§8), Context gaps (§9), findings (§10), and non-goals.
   Target length is under ~300 lines. The per-technology tables stay in
   this record, which the packaged file names but does not link.
2. `review-scope.md` "Infrastructure / deployment": add the new policy as
   a second depth owner ("when the evidence gathered … warrants deeper
   tracing …, `deployment-infrastructure-deepening.md` per the
   'Domain-specific deepening pass'"). This is a one-sentence change, in
   the same pattern as the other dimensions.
3. `specialist-depth.md`: change "the four domain deepening policies" to
   five, and add the new file to `capabilities/specialist-depth/capability.yaml`
   `files`. Its `benchmark` line gains the #743 sub-corpus once it exists.
4. `review-summary.md` "Context gaps": add the one gap kind (§9).
5. Wiring, following the #181 and #83 precedent: `shared/policies/README.md`,
   both Skills' `metadata/skill.yaml`,
   `scripts/packaging/generate_package_manifest.py` and
   `package-manifest.json`, `docs/capability-architecture/capability-architecture-model.md`,
   and the forwarding in `review-reasoning.md`, `parallel-review.md`, and
   the local and GitHub runbooks where other deepenings are listed.
   Re-capture the `local-review.md` #223 baseline if that file changes.
6. Tests: `tests/policy/review/specialist_depth/test_deployment_infrastructure_deepening.py`.
   It asserts the activation contrasts (§4), the #181 exclusions, the
   execution classes (§6, with no new permission wording), the
   validate-before-trust checks (§7), the API-only row (§8), and the gap
   kind and its non-effects (§9).

Release intent: `Added`.

## 13. Adjustments to the downstream children

- **#742**: implement §12 only. Its "accept user-provided validation
  output under existing evidence-validation rules" is satisfied by
  reusing dependency-tree Workflow 2 and validate-before-trust (§7). The
  one schema-adjacent change it needs is the Context-gap kind (§9). This
  does not conflict with "no new finding/evidence schema," because a
  Context gap is not a finding, but #742 should state it explicitly.
- **#743**: a new `benchmark/corpus/deployment-infrastructure-deepening/`
  sub-corpus of inline-patch cases. The six outcome shapes are already
  listed in #743. Add one **non-activation** case (comment- or label-only
  manifest change) and one **#181-boundary** case (a `FROM`-only or
  `uses:`-only change that must not get a deployment finding). User
  output for the Context-gap and settled cases travels in
  `input.context` (§6.3), so no new fixture key is needed. Add a new
  `deployment-infrastructure` value to the taxonomy `CAPABILITY_VALUES`
  and `POLICY_CONTRACT_VALUES` in `benchmark_taxonomy.py`, and regenerate
  `corpus-index.json`. That is an enum entry, not a new runner.
- **#744**: document only what #742 and #743 deliver, through the
  existing `docs/features/` catalog plus one feature page. Copy §5's
  "Unsupported" column and §8's API-only row as the user-facing
  limitations list, and link this record instead of restating it.
