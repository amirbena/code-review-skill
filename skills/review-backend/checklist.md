# Backend checklist

Use as prompts for tracing, not as a list to tick through. Each item needs
a concrete consequence in this change to become a finding.

## APIs and contracts

- A public or cross-service contract changed: removed or renamed field,
  optional made required, narrowed type, removed enum member, changed
  status code, error shape or default. Check the consumers you can see.
- Adding an enum member or response field is compatible only if consumers
  tolerate it; check how they read it.
- Versioning, deprecation and the old path still working where promised.

## Databases and migrations

- Destructive steps (drop, rename, type change) with no expand/contract
  sequence or deprecation window, on a table the code shows is live.
- A column made non-null, or a new constraint or index, with no backfill or
  default for rows that already exist.
- Locks and long-running DDL on a large table; indexes built without the
  online option the engine offers; reversibility of the migration.
- Code and schema deployed in an order that breaks one of them mid-rollout.
- Non-relational stores: document-shape renames, secondary indexes that
  need a backfill, conditional-write semantics.

## Guarantees the change relies on

Only when the change touches shared or stored state, repeatable work or an
external service; otherwise report it skipped.

- Name the guarantee relied on (exclusive access, single execution,
  ordering, durability, compatibility with stored data, a service's real
  behavior, safe interruption). Check that code, config and contracts you
  can see establish it across several executors, restart or interruption,
  and a config or deployment change. A mock is not the contract. Shapes:
  read-then-write, at-least-once delivery, leader-only paths, a lock scoped
  to one process or expiring mid-work, a stored cursor a setting invalidates.
- Trace the failure path through unchanged code; a guard dismisses a
  candidate only if it covers that path. A deciding fact outside the repo
  is listed as not investigated.

## Performance

- A call, query or I/O per element of an input the code shows is
  unbounded (N+1); work repeated inside loops; nested scans over unbounded
  data; blocking I/O on a request or event-loop hot path.
- Missing pagination, limits or batching; caches without invalidation.

## Deployment and config

Ownership: `review-backend` owns permission and privilege scope as
configured in infra artifacts, and deploy safety; `review-security` keeps
code-level auth, secrets handling and supply chain. A finding both would
raise is one root cause.

- A config key, port, path, env var or flag renamed or changed in one place
  while another file still reads the old one (probes, services, templates,
  compose, workflows).
- Resource limits, replicas, termination grace period, timeouts and health
  checks that no longer fit the change, or that break an assumption in
  application code.
- CI/CD gates weakened (`continue-on-error`, skipped steps), widened
  permissions, unpinned references, changed secrets handling.
- Runtime or tool minimums raised without the docs, images and CI that
  state them.

IaC lifecycle and state:

- A stateful resource replaced or destroyed: rename without `moved` or
  `import`, ForceNew or immutable attribute edits, `count`/`for_each`
  re-addressing.
- `prevent_destroy` or deletion protection removed; state backend or
  provider changes. Where only a plan output decides it, list it as not
  investigated.

Kubernetes/Helm:

- Wildcard RBAC, a binding widened to `cluster-admin`, `privileged`, root or
  host namespaces, a removed NetworkPolicy, a wider Service or Ingress.
- Immutable-field edits (selector, `volumeClaimTemplates`); rollout
  settings (PDB, strategy) that break the change's assumptions.

CI/CD deploy safety:

- Environment protection or approval removed; overlapping deploys with no
  concurrency group; OIDC trust or role scope widened; no rollback path.
