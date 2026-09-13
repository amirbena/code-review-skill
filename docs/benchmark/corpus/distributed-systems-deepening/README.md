# Distributed Systems Deepening Regression Fixture Corpus

Repository-development artifact for GitHub Issue
[#272](https://github.com/amirbena/code-review-skill/issues/272), a
deterministic fixture corpus for the Distributed Systems deepening
capability tracked by parent Issue
[#84](https://github.com/amirbena/code-review-skill/issues/84) and its
own parent, the adaptive specialist-depth composition contract
[#82](https://github.com/amirbena/code-review-skill/issues/82). This is a
**focused sub-corpus** of [`benchmark-case/v1`](../../fixture-format.md)
fixtures pinning representative Distributed Systems deepening outcomes as
follow-up quality hardening — it validates domain correctness after the
capability exists and does not define, gate, or redesign it. The
capability itself is designed and packaged in
[`../../../../shared/policies/distributed-systems-deepening.md`](../../../../shared/policies/distributed-systems-deepening.md),
which this corpus's expectations must stay consistent with.

Every case conforms to [`../../fixture-format.md`](../../fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of [`../`](../README.md)
and [`../../`](../../README.md) this is **not** packaged into either
Skill archive and no packaged Skill resource depends on it — it is
consumed only by this repository's own test suite, through the single
reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
(never a second one).

## Selection principle

**One case per outcome shape** #272's scope requires, each isolating that
shape so a regression in any one is unambiguous. The six cases mirror
[`distributed-systems-deepening.md`](../../../../shared/policies/distributed-systems-deepening.md)'s
own worked examples and Activation section, and split evenly between
"the capability engages and finds a real defect" and "the capability
correctly stays quiet":

- **Concurrent interleaving** — an inventory count is read, compared
  against a requested quantity, and decremented in a separate write,
  while the server runs threaded so more than one request handler can
  reach the same shared dict concurrently with no lock guarding the
  sequence. Flagged (read → decide → write race / TOCTOU).
- **Retry interaction** — a queue consumer with an explicit
  at-least-once delivery guarantee forwards a message straight into a
  charge call with no idempotency key or dedup check on the
  side-effecting step. Flagged (redelivery double-charges).
- **Ownership/coordination assumption violated** — a new method writes
  the same shared "last_run" state an existing leader-only check
  protects, without checking leadership itself, so more than one node in
  the multi-node deployment can now write it concurrently. Flagged.
- **Retry already idempotency-guarded** — the same at-least-once queue
  consumer shape as the retry-interaction case, but the charge call
  already checks a dedup set before calling the payment gateway; base
  reasoning already suffices and the capability contributes nothing
  further. `clean`.
- **Not materially implicated** — a read-only accessor over settings
  already loaded once at startup, with no write, no retryable operation,
  and no evidence of concurrent mutation; the domain is not materially
  implicated at all, so Activation condition 1 is never satisfied.
  `clean`.
- **Filename signal suppressed** — a message-queue-adjacent filename
  (`worker/queue_consumer.py`) changes only a log message's argument
  style; naming alone must not trigger engagement. `clean`.

The two `clean` "no engagement" cases (not-materially-implicated and
filename-signal-suppressed) are deliberately distinct from each other and
from the guarded-clean case: the not-materially-implicated case fails
Activation condition 1 (the domain itself is not implicated), the
filename-signal case is the narrower guard from
[`specialist-depth.md`](../../../../shared/policies/specialist-depth.md)
that a naming coincidence is a signal, never independently sufficient,
and the retry-idempotency-guarded case shows the domain *is* implicated
and the capability *does* trace it, but finds the guard already holds —
so a regression in any one of the three distinct "stay quiet" reasons is
caught even if the other two stayed correct.

Each case is a crafted, self-contained Python patch (`input.patch` +
`input.base`), keeping the corpus runnable without network access and
consistent with the other corpora under [`../`](../README.md).

## Cases

| File | Outcome shape | A correct review must… | Decision |
|---|---|---|---|
| [`distributed-systems-deepening-concurrent-interleaving-inventory-race.yaml`](distributed-systems-deepening-concurrent-interleaving-inventory-race.yaml) | concurrent interleaving over shared mutable state | report one **P1**: `reserve_item`'s read-decide-write sequence over `_inventory` has no lock, and the threaded server lets more than one request thread race it (an optional missing-concurrency-test note is also acceptable) | `changes-required` |
| [`distributed-systems-deepening-retry-interaction-missing-idempotency.yaml`](distributed-systems-deepening-retry-interaction-missing-idempotency.yaml) | retry interaction with no idempotency guard | report one **P1**: the at-least-once queue consumer calls `capture_payment`, which has no idempotency key/dedup guard, so redelivery double-charges (an optional missing-concurrency-test note is also acceptable) | `changes-required` |
| [`distributed-systems-deepening-ownership-assumption-violated.yaml`](distributed-systems-deepening-ownership-assumption-violated.yaml) | ownership/coordination assumption contradicted by multiple owners | report one **P1**: `force_run_job` writes the shared `last_run` state without the leader check every other writer relies on, so more than one node can write it concurrently (an optional missing-concurrency-test note is also acceptable) | `changes-required` |
| [`distributed-systems-deepening-retry-idempotency-guarded-clean.yaml`](distributed-systems-deepening-retry-idempotency-guarded-clean.yaml) | retry interaction, idempotency already guarded | report **nothing** — base reasoning already suffices | `clean` |
| [`distributed-systems-deepening-not-materially-implicated-clean.yaml`](distributed-systems-deepening-not-materially-implicated-clean.yaml) | read-only accessor, no concurrency evidence | report **nothing** — the domain is not materially implicated | `clean` |
| [`distributed-systems-deepening-filename-signal-suppressed-clean.yaml`](distributed-systems-deepening-filename-signal-suppressed-clean.yaml) | message-queue-adjacent filename, no behavioral implication | report **nothing** — naming alone does not trigger deepening | `clean` |

Per-case provenance and a one- or two-sentence rationale also live in
each fixture's `metadata` block (`source`, `tags`, `rationale`) and in
the header comment.

## Validation

[`../../../../tests/unit/benchmark/test_distributed_systems_deepening_corpus.py`](../../../../tests/unit/benchmark/test_distributed_systems_deepening_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
used for the worked example and every other corpus. It never defines a
second one, and asserts: the sub-corpus stays small and documented;
every required outcome shape is present; every case pins an explicit
`decision` consistent with its required findings; every flagged case's
required finding is `P1`; every clean case carries no findings at all;
and every finding's anchor resolves inside its own case's patch or base.
Matching a reviewer's output to these expectations and scoring it are
out of scope here (Issues #41 / #52 / #54). Peer review of the expected
findings themselves happens on the pull request.
