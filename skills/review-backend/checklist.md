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

## Concurrency and distributed systems

- Read-then-write on shared state without a lock, transaction or atomic
  operation, under threaded or multi-process callers.
- Retries or at-least-once delivery reaching a non-idempotent effect with
  no idempotency key or deduplication.
- Single-owner or leader-only assumptions that another path bypasses;
  ordering assumptions; timeouts and partial failure between services.

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
  the change.
- CI/CD gates weakened (`continue-on-error`, skipped steps), widened
  permissions, unpinned references, changed secrets handling.
- Runtime or tool minimums raised without the docs, images and CI that
  state them.
