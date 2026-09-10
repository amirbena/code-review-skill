# Shared Policy — Affected-Test / Test-Impact Analysis

Applies identically to `local-code-review` and `github-pr-review`. It owns
the signal-triggered pass that traces a behavioral change into the existing
tests that encode or depend on that behavior — frequently tests **not in
the diff** — and judges whether they still hold.

This is the test-impact sub-domain of
[`review-scope.md`](review-scope.md), which owns base review scope and
routes here. It is the complement of
[`review-scope.md`](review-scope.md), "Related changes as one unit," and
adds no second scope or evidence model: blast radius is scoped per
[`evidence.md`](evidence.md), "Findings beyond the changed lines," labels
are reused from [`evidence.md`](evidence.md), and
[`severity.md`](severity.md) still derives the decision mechanically. It is
read-only — it never authorizes running the target repository's tests (see
[`git-safety.md`](git-safety.md), [`runtime-validation.md`](runtime-validation.md)).

## Affected-test / test-impact analysis

When a change alters observable production behavior, asking only whether the
*changed code* has tests is not enough. Trace the behavioral change into the
existing tests that encode or depend on that behavior and judge whether they
still hold:

```text
changed code
→ affected observable behavior / contract / branch / interaction
→ existing tests that exercise or depend on that behavior
→ regression / coverage impact
```

The tests that matter here are frequently **not in the diff**. This is the
complement of "Related changes as one unit" above, which pairs an
implementation with the tests changed alongside it; here the concern is an
*unchanged* test that is still relevant review evidence — it may assert an
output the change just altered, depend on a fixture or mock whose shape the
change invalidated, encode an expected error/status the change moved, or stop
short of a branch the change just introduced. The review can still look clean
because that test file was never opened.

### When this applies — signal-triggered

This triggers only when the diff changes behavior an existing test could
reasonably be expected to protect: a changed return value, status, error, or
emitted event; an altered calculation, validation, or state-transition rule;
a new or removed branch or precondition; a changed interaction with a
collaborator; or a modified public contract. A pure refactor with no
observable behavior change, a docs-only change, or a change with no plausible
existing test dependency does not trigger it and requires no action.

### What to do when triggered

Scoped to the change's realistic blast radius (see
[`evidence.md`](evidence.md), "Findings beyond the changed lines"), and using
ordinary repository search — no dependency graph, coverage tool, or test
runner:

- **Locate** the existing tests that exercise or depend on the changed
  behavior — unit, integration, contract, snapshot, or fixture-backed —
  including tests outside the changed-file set when repository inspection can
  reasonably find them (by changed symbol, endpoint, message/event type,
  error type, or shared fixture).
- **Re-validate** each located test against the new behavior. Look for
  assertions, expected errors/statuses/values, fixtures, mocks/stubs, test
  data, and boundary cases the change has made stale — a test that now passes
  for the wrong reason, still asserts the old behavior, or can no longer fail
  if the behavior regresses again.
- **Check coverage of the new path.** When the change adds or widens a
  branch, error path, or edge case, determine whether an existing test
  meaningfully exercises it or whether the new behavior is now unprotected.

### Findings

Raise a finding only on concrete evidence of a meaningful test/regression
gap: a specific stale assertion, fixture, or mock the change invalidates, or
a specific newly introduced path with no meaningful regression protection.
Name the test (or fixture/mock) and the change that invalidates or fails to
cover it. Label it confirmed defect / credible engineering risk / optional
improvement per [`evidence.md`](evidence.md) and classify severity per
[`severity.md`](severity.md) — an important test now protecting the wrong
behavior around a changed contract is typically P1; a lower-risk gap is P2.

### Boundaries

- This is **not** "did the PR add tests?" Existing tests may already cover
  the changed behavior completely — when they do, there is no finding, and a
  production change is never required to add or modify a test on its own.
- No exhaustive impact discovery. The obligation is to inspect the tests
  ordinary repository search can reasonably connect to the change, not to
  prove every affected test was found; state that limit rather than implying
  completeness.
- Read-only. Inspect and reason about test code as text; this never
  authorizes running the target repository's tests (see
  [`git-safety.md`](git-safety.md) and
  [`runtime-validation.md`](runtime-validation.md)).
- Not a repository-wide test audit. A test elsewhere that merely shares a
  name or module with the changed code, with no evidenced dependency on the
  changed behavior, does not widen scope; a pre-existing test weakness the
  change does not touch is out of scope per [`evidence.md`](evidence.md),
  "Findings beyond the changed lines."
- This adds no second scope or evidence model — it is one application of the
  proportional-scope and evidence-labeling rules this policy and
  [`evidence.md`](evidence.md) already define, and [`severity.md`](severity.md)
  still derives the decision mechanically.
