# Scale progressive-loading proof

Repository-development record for issue
[#447](https://github.com/amirbena/code-review-skill/issues/447), child of
[#403](https://github.com/amirbena/code-review-skill/issues/403), per
[#412](specialist-depth-continuation-checkpoint.md)'s decision to continue
the #408→#410→#411 pattern for exactly one more capability, `scale`. Like
the rest of [`./`](README.md), this is a repository-development doc:
**not** packaged into either Skill archive, and no packaged Skill
resource depends on it.

#447 made `scale`'s loading conditional on its declared activation
predicate and proved the fail-closed contract at the text/manifest level
([`tests/policy/review/test_scale_447.py`](../../tests/policy/review/test_scale_447.py)).
#408 recorded the pre-extraction baseline generically, by capability, for
every capability including `scale`
([`capability-loading-baseline.md`](capability-loading-baseline.md) §per-capability
table). This document is `scale`'s own proof, mirroring
[`specialist-depth-progressive-loading-proof.md`](specialist-depth-progressive-loading-proof.md)'s
(#411) shape: one static measurement, reproducible from the documented
command below, reusing every existing corpus/evaluator rather than
introducing a new one.

## 1. Scope and non-goals

Per #447:

- Proves `scale`'s activation predicate is enforced and fail-closed at
  the text/manifest level (§tests, not restated here — see
  `tests/policy/review/test_scale_447.py`).
- Measures the static instruction-surface reduction an "unnecessary"
  review no longer has to apply once `scale`'s loading is conditional.
- Reuses `repository-intelligence`'s existing corpus (#129) for the
  "not needed" and "must activate" activation-correctness roles, and adds
  exactly one net-new fixture
  ([`docs/benchmark/corpus/scale-progressive-loading-proof/`](../benchmark/corpus/scale-progressive-loading-proof/README.md))
  for the one required shape neither existing corpus covers: an ambiguous
  trigger-evaluation that must still load (fail-closed) rather than skip.
- Does **not** rewrite any existing pinned benchmark expectation, does
  not attempt a general router extraction, and does not change
  `specialist-depth`'s `requires: [... scale]` dependency or any other
  capability's loading behavior (`tests/policy/review/test_scale_447.py`,
  `ScopeBoundaryTests`, verifies this directly).
- Static measurement executed at commit `3b1cfba` +worktree (2026-09-17).

## 2. Static surface reduction

Reproducible with:

```bash
python3 scripts/capability_architecture/scale_progressive_loading_proof.py static
```

Reuses `capability_loading_baseline.py`'s own static-surface measurement
unchanged (`measure_static_surface()` — see
[`capability-loading-baseline.md`](capability-loading-baseline.md) §2 for
methodology) and isolates `scale`'s own attributed word count: the
surface an "unnecessary" review no longer has to apply once loading is
actually conditional.

| Adapter | Total words (`scale` loaded) | `scale` words | Total words (not needed) | Reduction |
| --- | ---: | ---: | ---: | ---: |
| `local-code-review` | 83,766 | 3,878 | 79,888 | 4.63% |
| `github-pr-review` | 112,954 | 3,878 | 109,076 | 3.43% |

These totals reflect a live re-measurement at the current commit (which
now includes both this issue's own "Conditional loading: fail-closed"
prose additions to `repository-expansion.md`/`large-pr-partitioning.md`
and every other change landed since #408's original snapshot), not the
stale #408 baseline figure. `scale` is a much smaller attributed slice
than `specialist-depth` was (3,878 words here vs. `specialist-depth`'s
9,379 at its own #411 measurement) — consistent with #447's own framing
of `scale` as a genuinely different, smaller activation shape, not a
repeat of the first extraction.

As with #411 §2: `scripts/packaging/package-manifest.json` still ships
`scale`'s files unconditionally — packaging membership is unaffected by
this issue. The "reduction" is the instruction surface a review's own
reasoning applies once loading is actually conditional on the activation
predicate, not a change to what the packaged archive contains.

## 3. Activation-correctness corpus (reused + net-new)

Unlike #411, this proof's behavioral half (a live run of the real
reviewer runtime against the regression set, the two reused
`repository-intelligence` cases, and the net-new ambiguous fixture below)
was not executed to completion in this session — attempting it left the
nested reviewer CLI invocation running with no output for several
minutes with no forward progress, and was stopped rather than left to
run indefinitely or have its result guessed at. The command is
documented in §4 exactly as `specialist_depth_progressive_loading_proof.py`
documents its own, and is intended to be run before #403 cites this
document as closing evidence.

What **is** independently verified in this repository's own test suite
(not a live reviewer run) for every case involved:

- Every fixture parses and validates against the single reference
  validator (`tests/reference/benchmark/benchmark_fixture.py`), including
  this issue's own net-new case
  ([`tests/unit/benchmark/test_scale_progressive_loading_proof_corpus.py`](../../tests/unit/benchmark/test_scale_progressive_loading_proof_corpus.py)).
- This issue's own net-new fixture's patch applies cleanly against its
  `base` via `git apply --check` — the same class of corruption #411 §4
  found and fixed in a reused, pre-existing fixture is checked directly
  here rather than discovered only at live-run time.
- `scale-progressive-loading-proof-ambiguous-public-export-forces-fail-closed-expansion`
  carries exactly one required, non-blocking (`P1`/`P2`, never `P0`)
  finding whose claim rests on the ring-1 expansion result
  (`app/checkout/cart.py`), never on the ambiguity itself — proof the
  fixture pins expansion-driven evidence, not manufactured confidence
  (`AmbiguousCaseShapeTests`, same test file).

## 4. Reproducing / re-measuring, including the still-outstanding behavioral run

```bash
python3 scripts/capability_architecture/scale_progressive_loading_proof.py all \
  --out docs/capability-architecture/scale-progressive-loading-proof.json
```

`all` runs both halves. `behavioral` requires the `claude` CLI on `PATH`
(or `BENCHMARK_REVIEW_CLI` set), per `run_benchmark.py`'s own
runtime-availability check, and its exit code is fail-closed on exactly
the two cases this issue owns outright: the regression set (§408's
4-case corpus) and this issue's own net-new ambiguous-fail-closed
fixture. A mismatch on either fails the run. A mismatch on the two
*reused* `repository-intelligence` fixtures (the control case and the
call-site positive case) is reported (to stderr and in the JSON output)
but never fails the run, mirroring #411 §6's precedent for
`specialist-depth-composition`'s reused cases.

## Status and canonical home

This document and
[`scripts/capability_architecture/scale_progressive_loading_proof.py`](../../scripts/capability_architecture/scale_progressive_loading_proof.py)
are the static half of the proof for #447; §3-4 record the behavioral
half's command and current status honestly rather than asserting a live
result that was not obtained. Neither is packaged into either Skill
archive, and no runtime behavior, packaging, or loading changed to
produce this document. This, together with
[`tests/policy/review/test_scale_447.py`](../../tests/policy/review/test_scale_447.py),
is the evidence #403 is scoped to cite for `scale` as the second capability
proving the pattern generalizes.
