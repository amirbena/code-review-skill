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

- A config key, port, path, env var or flag renamed or changed in one place
  while another file still reads the old one (probes, services, templates,
  compose, workflows).
- Resource limits, replicas, timeouts and health checks that no longer fit
  the change, or that break an assumption in application code.
- CI/CD gates weakened (`continue-on-error`, skipped steps), widened
  permissions, unpinned references, changed secrets handling.
- Runtime or tool minimums raised without the docs, images and CI that
  state them.
