# Mutation-Capability-Boundary Benchmark Corpus

Repository-development artifact for GitHub Issue
[#305](https://github.com/amirbena/code-review-skill/issues/305), a
durable adversarial benchmark corpus proving the mutation-capability
boundary [#301](https://github.com/amirbena/code-review-skill/issues/301)
built cannot regress unnoticed: code mutation never occurs without the
exact required user authorization, and authority never widens across the
`APPLY_PATCH` / `COMMIT` / `PUSH` transitions.

## Why this is not a `benchmark-case/v1` corpus

Unlike the corpora under [`../`](../README.md) (each a self-contained
inline patch plus expected findings), this boundary's inputs and
expectations are not a diff and a set of review findings — they are a
requested capability, an authorization scope/state, a structural
allow/deny result, and an expected repository/Git state after the action.
[`fixture-format.md`](../../fixture-format.md)'s `expected` block has no
field for any of that. This corpus follows the same test-only,
data-driven reference-fixture pattern
[`../delegation-spawn/README.md`](../delegation-spawn/README.md)
(issue [#307](https://github.com/amirbena/code-review-skill/issues/307))
and [`../reviewer-brief/README.md`](../reviewer-brief/README.md) already
established for domains the schema does not fit:

- [`../../../../tests/reference/benchmark/mutation_fixtures.py`](../../../../tests/reference/benchmark/mutation_fixtures.py) —
  one `MutationCase` per required outcome shape, each a zero-argument
  `run()` closure that exercises the *single* reference model,
  [`../../../../tests/reference/review/mutation_authority.py`](../../../../tests/reference/review/mutation_authority.py),
  against a real, disposable temporary Git repository — never a mock or a
  stubbed filesystem — plus the declarative metadata #305 requires:
  requested capability/action, authorization scope/state, expected
  allow/deny result, expected repository/Git state after the case, linked
  `AUTH-###` threat-scenario id(s), and (for a denied case) the
  provisional denial classification.
- [`../../../../tests/unit/benchmark/test_mutation_boundary_corpus.py`](../../../../tests/unit/benchmark/test_mutation_boundary_corpus.py) —
  runs every case's `run()` and asserts its actual outcome matches the
  declared expectation, plus corpus-completeness checks (every required
  category, every catalog `AUTH-###` id excluding `AUTH-014`, every
  requirement tag), the malformed-fixture rejection suite, a dedicated
  "denied cases leave repository/Git state unchanged" check, and a
  dedicated "allowed apply changes only the authorized scope" check.

This corpus is **not** a duplicate of
[`../../../../tests/unit/security/test_mutation_authority.py`](../../../../tests/unit/security/test_mutation_authority.py),
which #301 already landed as hand-written regression tests, one per
`AUTH-###` scenario, against the same reference model. That suite is *why*
the boundary holds; this corpus is the declarative, metadata-bearing
**benchmark** layer #305 asks for — every case carries its expectation as
structured *data*, validated independently of execution, so future
tooling ([#310](https://github.com/amirbena/code-review-skill/issues/310))
can select or introspect the corpus by category or threat-scenario id
without re-deriving it from test method names. Both layers call into the
same single implementation; neither ever forks it.

## Architectural separation from ordinary finding-quality fixtures

Like the delegation-spawn corpus, every case here yields a **capability-
boundary pass/fail outcome**, never a P0/P1/P2 finding match. This module
lives entirely outside `docs/benchmark/corpus/*.yaml`
(`benchmark-case/v1` fixtures) and `tests/reference/benchmark/
benchmark_metrics.py`/`benchmark_match.py` (finding precision/recall/
severity scoring): it is executed by its own dedicated test module,
selectable independently, and never contributes a row to the ordinary
review-quality metrics pipeline. This is a deliberate mirror of how
[`../delegation-spawn/README.md`](../delegation-spawn/README.md) (#307)
kept its capability-boundary corpus disjoint from #40/#41's
finding-quality corpus.

## Evaluation style

Every comparison in this corpus is a **deterministic structural
assertion** — allowed/denied, denial classification, repository/Git
state preserved or not, the exact set of paths an allowed apply touched —
never an LLM/rubric score. This corpus is disjoint from the
finding-precision/recall/severity metrics
([#41](https://github.com/amirbena/code-review-skill/issues/41)) and the
Reviewer Brief semantic-quality corpus
([#309](https://github.com/amirbena/code-review-skill/issues/309)): it
never touches a finding, a severity, or review prose, and it never scores
review *quality* — only capability-boundary correctness.

## Categories and required outcome shapes

| Category | Required shapes |
| --- | --- |
| `default_read_only` | `READ_ONLY` cannot be authorized (`AUTH-001`); a `.git/` target is refused (`AUTH-002`); an unrepresentable capability (e.g. `MERGE`) has no code path (`AUTH-015`); `PROPOSE_PATCH` is implicitly available and never mutates |
| `repository_text_cannot_authorize` | repository-derived text (PR/issue/commit) can never authorize `APPLY_PATCH` (`AUTH-003`); repository instructions (AGENTS.md/CLAUDE.md-style) claiming merge/branch-delete authority have no code path (`AUTH-004`); a genuine `TrustedChannel` succeeds |
| `proposal_advisory` | a proposed patch never mutates the working tree; a path-traversal/absolute target is rejected at proposal time |
| `apply_authorization` | `APPLY_PATCH` without an explicit user authorization is denied (`AUTH-005`); a valid, correctly bound authorization succeeds |
| `stale_approval` | approved patch digest differs from the patch presented for execution → denied (`AUTH-006`/`AUTH-008`); working-tree/base state advanced since approval → denied (`AUTH-007`); matching digest and base → allowed |
| `scope_enforcement` | a patch touching an out-of-scope file is denied (`AUTH-009`/`AUTH-016`); an authorized apply changes only the exact authorized scope, with an unrelated file left untouched |
| `capability_independence` | `APPLY_PATCH` authorization never authorizes `COMMIT` (`AUTH-010`); `COMMIT` authorization never authorizes `PUSH` (`AUTH-011`); each independently authorized, the full pipeline succeeds |
| `replay_protection` | mutation authorization cannot be replayed within the same invocation or across a different invocation (`AUTH-012`); a fresh, correctly bound single-use authorization succeeds exactly once |
| `child_non_inheritance` | a spawned child (and grandchild) cannot inherit or reuse the parent's mutation authorization (`AUTH-013`); a child with its own, independently issued authorization succeeds |
| `github_pr_review_posture` | `github-pr-review`'s own authority-domain reference model never references the mutation executor; a PR prompting it to "apply, commit, and push this fix yourself" confers no authorization; the read-only posture holds identically across every publication mode |

Every case's category, covered requirement tags, and linked `AUTH-###`
threat-scenario id(s) live in its `MutationCase` definition in
`mutation_fixtures.py` — this table is a map, not a second source of
truth.

## Denial classification / #299 extension point

Each denied case's `expected_security_event` cites one of the
denial-classification strings this module defines
(`DENIED_MUTATION_CAPABILITY_ABSENT`, `DENIED_MUTATION_UNAUTHORIZED`,
`DENIED_MUTATION_STALE_APPROVAL`, `DENIED_MUTATION_SCOPE_ESCAPE`,
`DENIED_MUTATION_AUTHORIZATION_REPLAY`) — the same vocabulary
`docs/threat-model/catalog/mutation-authority.yaml` and
`scripts/security/validate_threat_model.py`'s `PROVISIONAL_EVENT_CLASSES`
declare for the `mutation/#305` benchmark family. Each string maps
1:1 to one of `mutation_authority.py`'s typed `MutationAuthorityError`
subclasses (`CapabilityAbsentError`, `UnauthorizedMutationError`,
`StaleApprovalError`, `ScopeEscapeError`, `AuthorizationReplayError`).
[#299](https://github.com/amirbena/code-review-skill/issues/299) (the
real, authoritative security-event taxonomy,
`docs/security-events/security-event-model.md`) has now landed and
confirmed these five names as final without renaming, splitting, or
merging any of them — this corpus's string constants and fixture
structure needed no change.

## Repository/Git-state expectations, and the one documented exception

Every case declares `expected_repo_state_unchanged` (for a denied case)
or `expected_authorized_scope` (for an allowed case) so its actual
post-action repository/Git state is a checked fact, not an assumption.
Nearly every denied case leaves the working tree and refs/HEAD entirely
untouched (denial precedes any write). Exactly one case,
`out-of-scope-file-mutation-denied` (`AUTH-009`/`AUTH-016`), is a
documented exception matching the real reference model's own contract:
`git apply`'s raw working-tree write happens *before* the post-apply
scope-diff check can detect the violation, so — exactly as
`mutation_authority.py`'s own docstring and
`test_mutation_authority.py::Auth009And016ScopeEscapeAtApply` document —
the working-tree side effect is left for investigation rather than
silently reverted. Crucially, no ref/HEAD ever advances in that case
either: the mutation is still never accepted as successful. This corpus
does not paper over that nuance with a blanket invariant; it asserts it
precisely (`test_documented_exception_still_never_advances_refs_or_head`
in the unit-test module).

## Threat-scenario traceability

This corpus covers every `AUTH-###` scenario in
[`../../../threat-model/catalog/mutation-authority.yaml`](../../../threat-model/catalog/mutation-authority.yaml)
(16 scenarios, issue [#300](https://github.com/amirbena/code-review-skill/issues/300)),
excluding `AUTH-014` — a distinct, already-covered GitHub formal
review-action authority domain
(`skills/github-pr-review/policies/review-action-authorization.md`), not
this corpus's or #301/#305's code-mutation scope. Those 15 catalog
entries' `benchmark_reference` field, previously `COVERAGE_GAP`, now
points at this corpus. `test_mutation_boundary_corpus.py` cross-checks its
own required-id set against the live catalog file so a future catalog
edit is caught here, not silently drifted from.

## Focused selection

Run this corpus independently of the rest of the benchmark suite:

```bash
python3 -m unittest tests.unit.benchmark.test_mutation_boundary_corpus
```

exactly like every other `test_*_corpus.py` module under
[`../../../../tests/unit/benchmark/`](../../../../tests/unit/benchmark/)
(e.g. `test_delegation_spawn_corpus.py`) — no other benchmark case needs
to run first.

## Corpus validation

`mutation_fixtures.validate_case` / `validate_corpus` reject a malformed
fixture: an unrecognized category, an empty case id/requested-capability/
authorization-state string, an invalid `expected_result` token, a denied
case missing (or citing an unrecognized) denial classification, a denied
case with a non-bool `expected_repo_state_unchanged`, a denied case that
still carries a declared authorized scope, an allowed case that still
carries a denial classification, an allowed case missing its repo-state
expectation, a threat-scenario id that does not match `AUTH-<3 digits>`,
and (explicitly) `AUTH-014` cited by any case at all.
`MalformedFixtureRejectionTests` in the unit-test module exercises every
one of these against deliberately broken fixtures built from
`dataclasses.replace` over a real, passing case. The validator
deliberately encodes no runtime implementation internals (no
`MutationExecutor`/`AuthorizationLedger` wiring) — it is a clean data
schema, per #305's own constraint.
