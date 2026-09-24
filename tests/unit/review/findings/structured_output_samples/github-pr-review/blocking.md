## Review Summary

**Result: ⚠️ CHANGES REQUIRED**

Not safe to merge at `b81d4a9` yet. Two blocking issues need to be addressed; see the inline comments for detail.

### Findings

- **P1 — Retry loop reports a timed-out charge as successful**
  `src/payments/retry.py:88`
- **P2 — Timeout path of the retry loop is untested**
  `tests/unit/payments/test_retry.py`

#### F2 [P1] Idempotency key is dropped on both charge paths

- **Location:** `src/payments/client.py:41`
- **Affected locations:**
  - `src/payments/charge.py:charge` — a retried charge is submitted twice
  - `src/payments/refund.py:refund` — a retried refund is submitted twice
- **Evidence:** `PaymentsClient.post` rebuilds `headers` without the `Idempotency-Key` the callers pass in.
- **Impact:** Any retried charge or refund is processed twice by the provider.
- **Fix:** Forward the caller's `Idempotency-Key` header in `PaymentsClient.post`.

Validation: `executed` — `python -m pytest tests/unit/payments` (declared in `Makefile`, exit 0).

### Decision
**REQUEST CHANGES**

<details>
<summary>Review metadata</summary>

- reviewed_head: `b81d4a9e0c7f3625d1e8a4b6c90f2e7d5a31c84f`
- review_mode: `full`
- stacked_pr: `none detected` (base is the repository's default branch)
- change_risk_depth: `elevated`
- change_risk_signals: `payment-path (elevated) — src/payments/retry.py`
- repository_expansion_triggers: `none`
- coverage: `complete`
- P0: 0
- P1: 2
- P2: 1
- decision: `request_changes`
- publication_mode: `active`
- mutation: `submitted (REQUEST_CHANGES)`

</details>

## Reviewer Brief

- **What changed:** Adds bounded retries around the charge call and routes charges and refunds through a shared client.
- **User-provided focus:** none provided.
- **Manual review focus:**
  - Confirm the provider deduplicates on `Idempotency-Key` for refunds as well as charges.

```json
{
  "schema_version": "1.0.0",
  "skill": "github-pr-review",
  "reviewed_state": {
    "repository": "acme/payments",
    "base_branch": "main",
    "base_sha": "3f9c1e2a7b4d5c60918273645a1b2c3d4e5f6071",
    "merge_base_sha": "3f9c1e2a7b4d5c60918273645a1b2c3d4e5f6071",
    "reviewed_head_sha": "b81d4a9e0c7f3625d1e8a4b6c90f2e7d5a31c84f",
    "reviewer_identity": "review-bot",
    "completeness": "full",
    "prior_reviewed_sha": null
  },
  "coverage": "complete",
  "decision": {
    "derived": "blocking",
    "outcome": "blocking"
  },
  "counts": {
    "p0": 0,
    "p1": 2,
    "p2": 1
  },
  "summary": "Adds bounded retries around the charge call and routes charges and refunds through a shared client.",
  "findings": [
    {
      "id": "F1",
      "severity": "P1",
      "title": "Retry loop reports a timed-out charge as successful",
      "location": "src/payments/retry.py:88",
      "fix_location_resolved": true,
      "evidence": "`charge_with_retry` catches `TimeoutError` and `continue`s; after the last attempt it falls through to `return ChargeResult.ok()`.",
      "impact": "A charge that never completed is recorded as paid, so the order ships without payment.",
      "fix": "Return a failure result when every attempt timed out.",
      "runtime_validation": "reasoned",
      "confidence": "credible",
      "defect_kind": "swallowed-exception",
      "identity": {
        "stable_id": "fid_v1_2c7a0d6b2c80a885a1752c05f15d70c0",
        "matching_eligible": true
      }
    },
    {
      "id": "F2",
      "severity": "P1",
      "title": "Idempotency key is dropped on both charge paths",
      "location": "src/payments/client.py:41",
      "fix_location_resolved": true,
      "affected_locations": [
        {
          "location": "src/payments/charge.py:charge",
          "note": "a retried charge is submitted twice"
        },
        {
          "location": "src/payments/refund.py:refund",
          "note": "a retried refund is submitted twice"
        }
      ],
      "evidence": "`PaymentsClient.post` rebuilds `headers` without the `Idempotency-Key` the callers pass in.",
      "impact": "Any retried charge or refund is processed twice by the provider.",
      "fix": "Forward the caller's `Idempotency-Key` header in `PaymentsClient.post`.",
      "runtime_validation": "runtime-confirmed",
      "confidence": "confirmed",
      "defect_kind": "missing-idempotency-key",
      "identity": {
        "stable_id": "fid_v1_43694218c49a2784e413ea3dfd660bc3",
        "matching_eligible": true
      }
    },
    {
      "id": "F3",
      "severity": "P2",
      "title": "Timeout path of the retry loop is untested",
      "location": "tests/unit/payments/test_retry.py",
      "fix_location_resolved": true,
      "evidence_location": "src/payments/retry.py:80-92",
      "evidence": "The only new test, `test_charge_retries_on_failure`, exercises a non-timeout failure.",
      "impact": "The timeout regression would not be caught by the suite.",
      "fix": "Add a test that makes every attempt time out and asserts a failure result.",
      "runtime_validation": "attempted-inconclusive",
      "contextual_evidence": [
        "acceptance criterion: failed charges must never be recorded as paid"
      ],
      "confidence": "runtime-validation-unavailable",
      "defect_kind": "missing-test-coverage",
      "identity": {
        "stable_id": "fid_v1_d3b3f8809dcaa5f1dfd78b9cbed739ba",
        "matching_eligible": true
      }
    }
  ]
}
```
