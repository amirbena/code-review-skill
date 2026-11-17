# Backend Guarantee-Reasoning Fixture Corpus

Repository-development artifact for GitHub Issue
[#874](https://github.com/amirbena/code-review-skill/issues/874). It pins the
`review-backend` checklist block "Guarantees the change relies on"
([`skills/review-backend/checklist.md`](../../../skills/review-backend/checklist.md)).
Not packaged into any Skill archive.

## Selection principle

The fixtures verify a **dimension**, not a named scenario. Each dimension has
at least two cases built on different mechanisms, so the behaviour cannot be
memorised:

- **Coordination:** a process-local lock with three replicas, and a library
  lock whose TTL is shorter than the work it protects.
- **Persisted state:** a numeric offset cursor invalidated by a sort change,
  and a version marker that is written but never checked.
- **External contract:** a key-value store and a payment API, each shown only
  by a mock or fake. These are P2 test gaps, which derive to `clean`.

Clean cases prove nothing is reported for guarded or hypothetical risks: a
single replica, an atomic conditional update, a version check with recovery, a
mock backed by an integration test, and a change touching none of these.

## Cases

| File | Outcome |
|---|---|
| [`backend-guarantee-clean-atomic-conditional-update.yaml`](backend-guarantee-clean-atomic-conditional-update.yaml) | clean |
| [`backend-guarantee-clean-dimension-not-implicated.yaml`](backend-guarantee-clean-dimension-not-implicated.yaml) | clean |
| [`backend-guarantee-clean-mock-backed-by-contract-test.yaml`](backend-guarantee-clean-mock-backed-by-contract-test.yaml) | clean |
| [`backend-guarantee-clean-single-replica-in-memory-lock.yaml`](backend-guarantee-clean-single-replica-in-memory-lock.yaml) | clean |
| [`backend-guarantee-clean-version-checked-with-recovery.yaml`](backend-guarantee-clean-version-checked-with-recovery.yaml) | clean |
| [`backend-guarantee-coordination-in-memory-lock-multi-replica.yaml`](backend-guarantee-coordination-in-memory-lock-multi-replica.yaml) | P1 |
| [`backend-guarantee-coordination-lock-expires-before-work-ends.yaml`](backend-guarantee-coordination-lock-expires-before-work-ends.yaml) | P1 |
| [`backend-guarantee-external-contract-mocked-payment-api.yaml`](backend-guarantee-external-contract-mocked-payment-api.yaml) | P2 test gap |
| [`backend-guarantee-external-contract-mocked-store.yaml`](backend-guarantee-external-contract-mocked-store.yaml) | P2 test gap |
| [`backend-guarantee-persistence-cursor-after-sort-change.yaml`](backend-guarantee-persistence-cursor-after-sort-change.yaml) | P1 |
| [`backend-guarantee-persistence-version-marker-not-checked.yaml`](backend-guarantee-persistence-version-marker-not-checked.yaml) | P1 |

## Validation

[`../../../tests/unit/benchmark/test_backend_guarantee_reasoning_corpus.py`](../../../tests/unit/benchmark/test_backend_guarantee_reasoning_corpus.py)
loads every case through the single reference validator
[`benchmark_fixture.py`](../../../runtime_platform/benchmark/reference/benchmark_fixture.py).
