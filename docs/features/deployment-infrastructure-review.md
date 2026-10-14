# Deployment & infrastructure review

## What it does

When a change alters how an application is **deployed or run**, the review
looks further than a normal pass: it reasons about the changed lines together
with the files that define and consume the same names, ports, keys, and
settings, and reports an evidenced concern as an ordinary finding.

It reviews infrastructure and deployment **changes**. It does **not** guarantee
that a deployment will succeed, and it does not replace Kubernetes
validators, Terraform validation, CI/CD execution, runtime monitoring, or
production deployment verification. Run those as you normally would.

## Supported scope

Kubernetes, Helm, Argo CD, Docker, Terraform, Jenkins, and GitHub Actions
configuration. Other deployment technologies (Kustomize-only repositories,
Pulumi, CloudFormation, GitLab CI) get the normal review only, with no extra
depth.

## When it runs

Automatically — there is no invocation option and nothing to enable. It
engages only when the change alters a deployment behavior, such as:

- rollout and availability (replicas, update strategy, probes, sync order);
- resource requests and limits against the runtime's own settings;
- privilege or credential scope (RBAC, security context, workflow token
  permissions);
- a name, key, port, or environment variable one file defines and another
  consumes;
- destructive or state-affecting behavior (replacement, removal, prune,
  immutable fields);
- failure handling and gates (swallowed errors, removed approvals);
- the startup contract (entrypoint, ports, working directory).

A file type, path, or name alone never triggers it, so an inert edit (a
comment, an unused label, key order) stays silent. Asking for extra attention
on deployment safety adds depth; it is not required.

## Examples

- **Engages:** a change moves an application's default listen port while the
  Deployment's probe and Service still use the old one — even though no
  manifest changed.
- **Engages:** a workflow's `permissions:` block gains `contents: write`.
- **Engages, with a gap:** a Terraform resource is renamed without a `moved`
  block. The review reasons from the diff and tells you which `terraform plan`
  output would settle it.
- **Stays out:** a Dockerfile `FROM`-only change or a GitHub Actions `uses:`
  bump is handled by the dependency review, not here.

## How it gathers evidence

1. **Static inspection** of the diff — always, and never waits on anything
   else.
2. **Repository context** — unchanged files that define or consume the same
   values.
3. **Validation output you supply** — for example the result of a `terraform
   plan` the review could not safely run. It must be recognizably the tool's
   output, name the reviewed target, identify the Base or Head commit it came
   from, and be complete. Anything else is recorded as a Context gap, never
   treated as a clean result. Treat plan output as sensitive: paste only what
   is needed.
4. **Optional execution** of a validation command — only through the
   existing execution rules, when it is available, authorized, and safe.

Evidence you supply can support or settle a finding but cannot by itself make
it `confirmed`.

## Running validation commands

Execution is optional and never a gate. The review does not run a command just
because it looks safe by name: each command goes through the existing
[runtime validation](runtime-validation.md) rules, inside a verified
isolation boundary or under your explicit
[trusted-host authorization](../../shared/policies/trusted-host-execution.md). Commands that need cloud,
cluster, registry, or state-backend credentials, or that contact such
systems, are not run. A command that would change infrastructure (`apply`,
`sync`, `push`, `install`) is never run.

Every command considered is listed in the review's `Validation` section as
`executed`, `failed`, `skipped`, or `unavailable`; a skipped or unavailable
command is never presented as a pass.

## Local versus GitHub API-only

| | Static diff | Repository context | Supplied output | Execution |
|---|---|---|---|---|
| `local-code-review` | yes | yes | yes | per the rules above |
| `github-pr-review`, repository-backed | yes | yes (checkout at the PR head) | yes | per the rules above |
| `github-pr-review`, API-only (default) | yes | changed files only | yes | **unavailable** |

In API-only mode an unchanged referenced file is not assumed reachable: the
review reasons from the diff when it is conclusive, and otherwise records a
Context gap. Repository settings such as environment protection rules and
default token permissions are not visible to the review in either Skill.

## What you get

- **Ordinary findings** with the usual severity, evidence bar, and Decision,
  labeled as coming from this deeper review. Generic infrastructure advice
  with no evidenced concern in the change is not reported.
- **A deployment validation evidence gap** in the review's "Context gaps"
  when a concern it examined needs evidence that is unavailable — naming what
  is missing and the command or output that would resolve it. A gap is not a
  finding, never raises severity, and never changes the Decision.

## Limits and non-goals

- No guarantee of deployment success; no reasoning about live cluster, cloud,
  registry, or Terraform state.
- Not a policy engine, and no replacement for `helm`, `kubeconform`,
  `terraform validate`/`plan`, `actionlint`, or CI execution.
- No infrastructure mutation, dependency installation, or new execution
  permission; no tool is mandatory.
- Technologies outside the list above are not given deployment-specific depth.

## Canonical sources

[`deployment-infrastructure-deepening.md`](../../shared/policies/deployment-infrastructure-deepening.md)
is the canonical contract; it composes with
[`review-scope.md`](../../shared/policies/review-scope.md) and
[`specialist-depth.md`](../../shared/policies/specialist-depth.md). Execution
rules live in [`runtime-validation.md`](../../shared/policies/runtime-validation.md)
and [`trusted-host-execution.md`](../../shared/policies/trusted-host-execution.md).
Contributors: change behavior there, not here.
