# Engineering Guardrails Policy

Canonical engineering habits for developing *this* repository — features,
fixes, maintenance, and refactoring — distilled from the work merged under
Epic [#786](https://github.com/amirbena/code-review-skill/issues/786)
(children #787–#793 and #798) and tracked in
[#804](https://github.com/amirbena/code-review-skill/issues/804).

This is a repository-development policy. It is **not** packaged into either
Skill archive, and no packaged Skill resource may depend on it. It adds no
review semantics: severity, verdict derivation, and stopping criteria stay
owned by [`shared/policies/`](../shared/policies/). See
[`AGENTS.md`](../AGENTS.md) for global invariants and routing.

Each guardrail states the rule, the failure it prevents (with the evidence
that motivated it), and the canonical source for details. Guardrails codify
only decisions already merged; a migration step still in flight is governed
by its owning Issue and must not be generalized into a standing exception.

## 1. Respect ownership and dependency direction

Preserve documented dependency direction and sanctioned interfaces. Do not add
a reverse dependency, import around a sanctioned interface, or create a second
authoritative implementation of something that already has an owner.

- Benchmark platform code (`runtime_platform/`) may import test-only reference
  models only from `tests.reference.review`; `tests.reference.review` never
  imports `runtime_platform`; `runtime_platform/` never imports other `tests.*`
  packages. A deterministic test enforces this.
- Evidence: #792 found 15 implicit imports from benchmark code into the test
  package with no stated direction.
- Canonical:
  [`docs/benchmark-reference-dependency/README.md`](../docs/benchmark-reference-dependency/README.md),
  [`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md).
- Extending a boundary (for example to `scripts/`) is a new architectural
  decision that needs its own Issue, not a drive-by edit.

## 2. Consolidate only equivalent behavior

Share code when contracts are provably identical. Superficial similarity is not
equivalence; look-alikes that differ in meaning stay separate, with a comment
where they could be mistaken for duplicates.

- Evidence: of 37 `_norm` copies in tests, about nine differed in meaning
  (lowercasing, link rendering, dropping only `**`) and were deliberately not
  merged (#791). `_VERSION_LINE` in `package_domain` differs by `\r?` and was
  left alone while the byte-identical `_SUBSECTION_RE` was shared (#793). Git
  and `gh` wrappers in `scripts/` differ deliberately in error handling.
- Show equivalence (same inputs, outputs, and failure messages) before
  converting callers, and convert in small reviewable batches. Discovered test
  counts must be identical before and after.
- Canonical: [`tests/README.md`](../tests/README.md) (`tests/support/`).

## 3. Keep tests isolated

A test must not depend on execution order, shared mutable state, host
configuration, or artifacts another test produced.

- Tests that create Git repositories call `isolate_git_config()` (from
  `tests/support/git_repo.py`) in `setUpModule` so host signing, hooks, default
  branch, or identity cannot change the result.
- Evidence: under a hostile global Git config, 262 tests in 17 modules failed
  until isolated (#791). Parallelizing tests requires a prior isolation audit.
- Canonical: [`tests/README.md`](../tests/README.md), which documents the
  hostile-config check.

## 4. Establish a check's purpose before removing it

Do not delete a repeated build, second execution path, or redundant-looking
gate because it appears redundant. Establish what it verifies first.

- Evidence: of the repeated packaging builds in tests, only the pristine-tree
  repeats had identical inputs; the rest vary version or changelog by design
  (#798). The mandatory policy-loading checkpoint is intentional redundancy.
- Never weaken an assertion, `SKILL.md` ceiling, or hash baseline to make a
  change easier. A baseline re-capture states its cause (Epic #786, risks).
- Canonical: [`docs/refactoring-baselines/ci-cost-profile.md`](../docs/refactoring-baselines/ci-cost-profile.md).

## 5. Measure before optimizing

A performance change cites a reproducible baseline and comparable before/after
samples, with variance noted, and must not shrink required coverage.

- Required checks stay as named, and `scripts/validation/ci_test_route.py`
  keeps its standalone fail-to-FULL behavior.
- Evidence: the FULL-tier cause was unidentified until #798 profiled it; the
  dominant phase was not the one inferred, and #802 was justified by
  before/after samples (suite wall median 302 s to 252 s).
- Use the same method as the baseline; compare shares, not seconds, across
  different machines or Python versions. Keep CI-workflow, release-helper, and
  packaging-helper changes in separate PRs (#793).
- Canonical: [`docs/refactoring-baselines/README.md`](../docs/refactoring-baselines/README.md).

## 6. Protect distribution contracts

Packaging changes preserve deterministic output and supported-platform
behavior unless the task explicitly authorizes an output change.

- For identical inputs, `dist/` (manifest, tree hashes, archives) must be
  byte-identical before and after; diff it.
- Bash and PowerShell packaging must keep tree-hash parity (the
  `skill-tree-parity` jobs). Add no time-, host-, or order-dependent input.
- Evidence: #802 cut Python spawns from 161 to 29 with `dist/` byte-identical.
- Canonical: [`validation-and-clean-exit.md`](validation-and-clean-exit.md),
  [`skill-development-policy.md`](skill-development-policy.md).

## 7. Keep benchmark evaluation independent

Do not weaken fixtures, baselines, expectations, or reference-model boundaries
to improve a result. A benchmark change must not alter evaluation semantics.

- Benchmark-methodology changes and review-behavior changes land in separate
  PRs, so a result shift stays attributable (Epic #786, non-goals).
- Compare against the recorded baseline; a harness or runtime failure is not a
  quality change.
- Canonical: [`runtime_platform/benchmark/README.md`](../runtime_platform/benchmark/README.md),
  [`docs/refactoring-baselines/README.md`](../docs/refactoring-baselines/README.md).

## 8. Review the exact change; incomplete is not clean

Establish review evidence, coverage, and delta identity before claiming a
clean result.

- Review every relevant category of the delta that will be committed, not an
  earlier one; the staged-delta fingerprint identifies the staged category only.
- Absence of findings is not evidence of correctness, and a review that has not
  completed required coverage reports `REVIEW INCOMPLETE`, never clean
  (#784: a report rendered "Review Clean" while its own metadata said
  `Coverage: incomplete`).
- Do not bypass an approval gate or a stopping criterion to reach a clean
  result. Every `local-code-review` run still needs fresh explicit user
  approval.
- Canonical:
  [`shared/policies/review-stopping-criteria.md`](../shared/policies/review-stopping-criteria.md),
  [`shared/policies/verdict-consistency.md`](../shared/policies/verdict-consistency.md),
  [`skills/local-code-review/policies/repository-state.md`](../skills/local-code-review/policies/repository-state.md),
  [`review-orchestration-policy.md`](review-orchestration-policy.md).
