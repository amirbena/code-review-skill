# Benchmark Runner Contract

Repository-development contract for GitHub Issue
[#52](https://github.com/amirbena/code-review-skill/issues/52). It defines
**how a benchmark run executes the reviewer over the corpus and what it
emits** — the execution-isolation and repository-safety guarantees every
run must hold, and the machine-readable per-case result shape a regression
report ([#53](https://github.com/amirbena/code-review-skill/issues/53))
later consumes. It builds on the fixture format
([`fixture-format.md`](fixture-format.md), #50) and the corpus
([`corpus/README.md`](corpus/README.md), #51). Parent capability:
[#40](https://github.com/amirbena/code-review-skill/issues/40).

Like [`fixture-format.md`](fixture-format.md) and the rest of
[`./`](README.md), this is a **repository-development doc: not packaged
into either Skill archive**, and no packaged Skill resource depends on it.
It reuses the shared review vocabulary (finding shape, P0/P1/P2 severity,
the mechanical decision); it does not define a parallel review model.

## Canonical invariant

> **A benchmark run executes each case's reviewer against an isolated, disposable copy of that case's input, records what the reviewer produced, and leaves every protected source checkout byte-for-byte unchanged — whether the case succeeds or fails.**

Every rule below is an elaboration of that sentence. Two concerns are
deliberately *out* of it and owned elsewhere (§9): deciding whether a
produced finding *matches* an expected one, and turning matches into a
score.

## 1. Terminology and ownership

- **Runner** — the external evaluation infrastructure that performs a
  benchmark run. It is **not** a Skill and is never packaged. Neither
  `local-code-review` nor `github-pr-review` launches a benchmark; the
  Skill is only ever *invoked by* the runner against a prepared target.
- **Reviewer adapter** — a caller-supplied callable the runner invokes
  once per case with the path to that case's isolated workspace, which
  returns the **produced findings** for that workspace. The runner owns
  isolation, sequencing, result capture, cleanup, and safety
  verification; the adapter owns *how a review is actually performed*
  (a runtime reading a Skill, a recorded transcript, a stub in tests).
  The runner never reads Skill instructions itself and never executes
  target-repository code — consistent with
  [`../ARCHITECTURE.md`](../ARCHITECTURE.md), "Automatic execution of PR
  code."
- **Produced finding** — one reviewer result in the shared shape of
  [`../../shared/templates/finding.md`](../../shared/templates/finding.md),
  carrying at least a severity (`P0` / `P1` / `P2`,
  [`../../shared/policies/severity.md`](../../shared/policies/severity.md))
  and a location. The runner records produced findings verbatim; it does
  **not** classify, dedupe, or match them.
- **Case result** — the machine-readable per-case record the runner emits
  (§6).
- **Protected source checkout** — any of: the user's active working tree,
  the caller / source repository checkout the run was invoked from, and
  the benchmark repository's own working tree. None may be mutated by a
  run (§4).
- **Workspace** — the isolated, disposable directory a single case
  executes in (§3). One per case; never shared, never a protected source
  checkout.

This contract does **not** define: the expected-vs-produced match
relation ([#54](https://github.com/amirbena/code-review-skill/issues/54),
[`match-criteria.md`](match-criteria.md)); false-positive / false-negative
accounting, precision/recall, retrieval thresholds, or aggregate quality
metrics built on it
([#41](https://github.com/amirbena/code-review-skill/issues/41)); the
regression report across runs
([#53](https://github.com/amirbena/code-review-skill/issues/53),
[`regression-report.md`](regression-report.md)); CI
wiring; or container/sandbox orchestration, a hosted service, or result
persistence beyond writing per-case files (§8).

## 2. Run modes

A run executes **either the whole corpus or one selected case**, chosen by
`id` ([`fixture-format.md`](fixture-format.md) §5):

- **Whole-corpus run** — every `*.yaml` under
  [`corpus/`](corpus/README.md) is parsed and executed. A parse failure
  in any fixture fails the run before any case executes (fail-closed: a
  malformed corpus is not silently partially run).
- **Single-case run** — exactly the case whose `id` is given executes.
  An unknown `id` is an execution failure (§7); it never silently
  becomes a no-op or a whole-corpus run.

Cases execute independently. One case's outcome — a passing review, a
reviewer error, a patch that does not apply — never changes what another
case does or whether it runs.

## 3. Per-case isolation

For every case, before the reviewer adapter is invoked:

1. The runner creates a fresh workspace under a temporary directory it
   owns (never inside, and never a hardlink/symlink into, a protected
   source checkout).
2. It materializes the case input **into that workspace only**:
   - **`patch` input** — initialize a new Git repository in the
     workspace, write the `input.base` pre-image files (when present),
     create one commit as the pre-image, then apply `input.patch` **in
     the workspace**. A patch that does not apply is a per-case execution
     failure (§7) — never retried against, or applied outside, the
     workspace.
   - **`repo_ref` input** — obtain the referenced state as an isolated,
     disposable clone / checkout (or equivalent disposable repository
     state). The user's active checkout is never reused, updated, or
     fetched into. How the referenced commit/PR ref is retrieved (a fresh
     clone, a local mirror, an adapter-provided checkout) is an
     implementation choice; that it is disposable and separate from every
     protected source checkout is not.
3. The reviewer adapter receives **only the workspace path** as its
   review target. It is given no path to, and no handle on, any protected
   source checkout.

The workspace is single-use. A second case never runs in a workspace a
previous case used.

## 4. Repository-safety invariants

These hold for **every** protected source checkout, on **every** run,
regardless of case outcome:

- **No mutation.** The run performs no write, of any kind, to a protected
  source checkout: no file edit, no `git add` / `commit` / `checkout` /
  `reset` / `clean` / `stash` / branch creation or deletion / tag /
  config change / `worktree add`, no `.git` write. Reads only.
- **Dirty state is preserved exactly.** A protected source checkout may be
  dirty *before* the run — pre-existing staged edits, unstaged edits, and
  untracked files. The run does not require it to be clean and does not
  normalize it. Afterward, its `HEAD`, tracked-file contents, staged and
  unstaged diffs, untracked files, branch list, and stash list are
  identical to before — byte for byte.
- **Integrity is verified around execution.** The runner captures
  observable state of the caller / source repository **before** and
  **after** the run and compares them, without requiring or making the
  repository clean. `git status --porcelain` records *which* paths
  changed, not their content, so a snapshot sufficient for the
  byte-for-byte guarantee also captures content: at minimum `HEAD`, the
  porcelain status, the full tracked-change diff (`git diff HEAD`), and a
  per-file digest of untracked content; it SHOULD also capture the branch
  list and stash list.
- **A detected mutation is an execution failure.** If the after-snapshot
  differs from the before-snapshot, the run reports execution failure
  (§7) even if every individual case's review completed.

## 5. Cleanup

- Every workspace and every temporary artifact the runner created is
  removed after the case completes — **on both the success and the
  failure path** (a patch that did not apply, a reviewer adapter that
  raised, a safety-check failure). Cleanup is unconditional; it is not
  skipped to "leave evidence for debugging" by default.
- **A failed cleanup is an execution failure** (§7), reported even when
  the reviews themselves succeeded.
- After a run, no benchmark-created residue remains anywhere: no leftover
  temporary directory, workspace, clone, branch, stash entry, worktree,
  or config change — in the caller's repository or on the filesystem the
  runner controls.

## 6. Case result shape

The runner emits **one machine-readable result per executed case**,
stable across runs (a re-run of the same case against the same adapter
output produces an equal record, modulo inherently run-specific fields
like timing if present). Each result carries at least:

| Field | Meaning |
|---|---|
| `id` | The case `id` ([`fixture-format.md`](fixture-format.md) §5) — the stable join key #53 uses. |
| `input_kind` | `patch` or `repo_ref`. |
| `status` | `executed` (the reviewer adapter ran to completion) or `error` (the case could not be executed — §7). |
| `produced_findings` | List of produced findings recorded verbatim (severity + location + the shared finding fields the adapter supplied). Empty list is a valid, meaningful value — the reviewer produced nothing. Absent/`null` only when `status` is `error`. |
| `error` | When `status` is `error`: a stable machine-readable reason (e.g. `patch-did-not-apply`, `reviewer-adapter-raised`, `unknown-case-id`, `workspace-setup-failed`, `cleanup-failed`, `source-checkout-mutated`). Absent otherwise. |

The runner records `produced_findings` exactly as the adapter returned
them. It does **not** compare them to the fixture's `expected` block,
attach match verdicts, or compute pass/fail — that is #54 (the match
relation) and #41/#53 (metrics and reporting).

`expected`-vs-`produced` comparison *structure* (pairing a result with its
fixture's expectations for a downstream matcher) MAY be emitted alongside
the per-case result, but the **match relation itself**
([#54](https://github.com/amirbena/code-review-skill/issues/54),
[`match-criteria.md`](match-criteria.md)) and any scoring are out of scope
(§9).

## 7. Execution status and exit code

- A **per-case** failure sets that case's result `status: error` with an
  `error` reason (§6) and does not abort sibling cases.
- The **run** fails (non-zero overall status / exit code) when any of:
  a requested single-case `id` is unknown; the corpus fails to parse; a
  workspace could not be isolated; cleanup failed; or a protected source
  checkout was mutated.
- **Exit code reflects execution health, not review quality.** A run in
  which every case executed cleanly is a **success** even if reviewers
  found many defects, found none, or "scored" poorly. Finding defects is
  never a runner failure. Scoring does not exist at this layer (§9).

## 8. Explicitly out of scope

| Not defined here | Owner |
|---|---|
| The expected-vs-produced match relation — deciding when a produced finding satisfies an expected spec, an `alternatives` restatement, or an `any_of` member | [#54](https://github.com/amirbena/code-review-skill/issues/54) — [`match-criteria.md`](match-criteria.md) |
| FP/FN accounting, precision/recall, retrieval thresholds, aggregate quality metrics built on that relation | [#41](https://github.com/amirbena/code-review-skill/issues/41) |
| Regression reporting across runs (seeded-regression detection, run-to-run comparison) | [#53](https://github.com/amirbena/code-review-skill/issues/53) — [`regression-report.md`](regression-report.md) |
| CI wiring / scheduled execution | tracked on [#40](https://github.com/amirbena/code-review-skill/issues/40) |
| Container / sandbox orchestration, a hosted service, database persistence, dashboards | out of scope for the epic; a container is at most a *future* isolation mechanism, not required by this contract |
| The fixture format and the corpus | [#50](https://github.com/amirbena/code-review-skill/issues/50) / [#51](https://github.com/amirbena/code-review-skill/issues/51) |
| The P0/P1/P2 definitions and the decision derivation | [`../../shared/policies/severity.md`](../../shared/policies/severity.md) |
| The finding field shape | [`../../shared/templates/finding.md`](../../shared/templates/finding.md) |

## 9. On the reviewer adapter

The runner is defined so that what performs the review is pluggable and
supplied by the caller. This contract fixes the **boundary** — isolation,
one workspace per case, workspace-path-only review target, verbatim
result capture, cleanup, source-checkout safety — not the adapter's
internals. A production adapter that drives a real runtime reading a
Skill, and a deterministic test adapter that returns recorded findings,
are both valid; the safety and result guarantees above do not depend on
which is used. The runner never itself reads Skill instructions and never
runs target-repository code.

## Status and canonical home

**This document is the authoritative contract** for the benchmark runner
until a later issue installs an equivalent runnable component in a
canonical home. At that point this document becomes the design record: it
MUST link to that component and MUST NOT keep evolving the runner
behavior independently — exactly as
[`fixture-format.md`](fixture-format.md), "Status and canonical home,"
describes for its own eventual installation.

The test-only reference runner
[`../../tests/reference/benchmark_runner.py`](../../tests/reference/benchmark_runner.py)
mirrors this document for regression coverage (executed by
[`../../tests/unit/test_benchmark_runner.py`](../../tests/unit/test_benchmark_runner.py),
including the deliberately-dirty-source-repo safety regression). It is not
packaged and is not a Skill.
