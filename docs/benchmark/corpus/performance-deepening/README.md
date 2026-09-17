# Performance Deepening Regression Fixture Corpus

Repository-development artifact for GitHub Issue
[#187](https://github.com/amirbena/code-review-skill/issues/187), a
deterministic fixture corpus for the Performance deepening capability
implemented by Issue
[#180](https://github.com/amirbena/code-review-skill/issues/180) and its
own parent, the adaptive specialist-depth composition contract
[#82](https://github.com/amirbena/code-review-skill/issues/82). This is a
**focused sub-corpus** of [`benchmark-case/v2`](../../fixture-format.md)
fixtures pinning representative Performance deepening outcomes as
follow-up quality hardening — it validates domain correctness after the
capability exists and does not define, gate, or redesign it. The
capability itself is designed and packaged in
[`../../../../shared/policies/performance-deepening.md`](../../../../shared/policies/performance-deepening.md),
which this corpus's expectations must stay consistent with.

Every case conforms to [`../../fixture-format.md`](../../fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of [`../`](../README.md)
and [`../../`](../../README.md) this is **not** packaged into either Skill
archive and no packaged Skill resource depends on it — it is consumed only
by this repository's own test suite, through the single reference
validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
(never a second one). Every case is a crafted, generic Python snippet
rather than a framework- or vendor-specific one, per Issue #187's
preference for semantic/risk-shape coverage over framework/library/vendor
examples.

## Selection principle

**One case per outcome shape** Issue #187's scope requires, each isolating
that shape so a regression in any one is unambiguous. The six cases mirror
[`performance-deepening.md`](../../../../shared/policies/performance-deepening.md)'s
own worked examples and concern areas, and split between "the capability
engages and finds a real cost defect" and "the capability correctly stays
quiet":

- **N+1 remote call in a loop** — a single batched remote call that
  fetched inventory for every order is replaced by a loop issuing one
  remote call per order, over a docstring-documented unbounded order
  count. Flagged.
- **Nested/unbounded scan (accidental O(n^2))** — a set-based membership
  check is replaced by a linear scan against a list that itself grows by
  one element per iteration, turning an O(n) merge into O(n*m) over two
  independently unbounded, docstring-documented inputs. Flagged.
- **Blocking I/O in a request hot path** — a blocking disk read that
  previously ran once at process startup and was cached is moved inside a
  per-request handler, so every request now pays it. Flagged.
- **Bounded/batched fix (positive control)** — the same
  unbounded-cardinality shape as the N+1 case, but the per-item remote
  call is replaced with a single batched call; the domain is implicated
  and this capability traces the call path, confirming the batching holds.
  `clean`.
- **Constant-size loop over a small fixed list** — a call is added inside
  a loop, but the loop iterates a fixed, small, compile-time-bounded
  four-element list; base reasoning confirms the bound and no further
  tracing is warranted. `clean`.
- **No call-path/hot-path relevance at all** — a constant's value changes
  in a module the file's own header comment documents as no longer
  imported anywhere in the codebase, so there is no call path, loop, or
  hot path left for the change to affect. `clean`.

The three `clean` cases are deliberately distinct from each other, the
same discipline the precedent Security, Distributed Systems, and Database
/ Migration deepening corpora use for their own "stays quiet" reasons: the
non-executed-config-constant case fails Activation condition 1 (no
material Performance / scale signal exists at all to reason about), the
constant-size-loop case satisfies condition 1 but fails condition 2 (the
domain is implicated but the loop's bound is evidence-shown to be fixed
and small, so bounded base reasoning already suffices), and the
batched-fix case satisfies both conditions and the capability *does* trace
the call path, but confirms the replacement is genuinely a single batched
call rather than a multiplied one — so a regression in any one of the
three distinct "stay quiet" reasons is caught even if the other two stayed
correct.

Per Issue #187's non-goals, this corpus contains no cross-domain
composition fixture (that is
[#85](https://github.com/amirbena/code-review-skill/issues/85)'s job,
which may reuse this corpus's single-domain fixtures as inputs) and adds
no new severity/evidence semantics.

## Cases

| File | Outcome shape | A correct review must… | Decision |
|---|---|---|---|
| [`performance-deepening-n-plus-one-remote-call-in-loop.yaml`](performance-deepening-n-plus-one-remote-call-in-loop.yaml) | N+1 remote call inside a loop | report one **P1**: a single batched inventory call is replaced by one call per order, over a docstring-documented unbounded order count (an optional missing-regression-test note is also acceptable) | `changes-required` |
| [`performance-deepening-nested-unbounded-scan-quadratic.yaml`](performance-deepening-nested-unbounded-scan-quadratic.yaml) | nested scan over unbounded input (accidental O(n^2)) | report one **P1**: a set-based membership check is replaced by a linear scan against a growing list, turning an O(n) merge into O(n*m) over two documented unbounded inputs (an optional missing-regression-test note is also acceptable) | `changes-required` |
| [`performance-deepening-blocking-io-request-hot-path.yaml`](performance-deepening-blocking-io-request-hot-path.yaml) | blocking I/O moved into a request hot path | report one **P1**: a blocking disk read that ran once at startup and was cached is moved inside the per-request handler (an optional missing-regression-test note is also acceptable) | `changes-required` |
| [`performance-deepening-batched-fix-bounded-clean.yaml`](performance-deepening-batched-fix-bounded-clean.yaml) | same logic with a bounded/batched fix | report **nothing required** — the capability traces the call path and confirms the batching is genuine (an optional note on regression-test coverage is also acceptable) | `clean` |
| [`performance-deepening-constant-size-loop-clean.yaml`](performance-deepening-constant-size-loop-clean.yaml) | constant-size loop over a small fixed list | report **nothing** — base reasoning confirms the bound is fixed and small; no deeper tracing warranted | `clean` |
| [`performance-deepening-non-executed-config-constant-not-implicated-clean.yaml`](performance-deepening-non-executed-config-constant-not-implicated-clean.yaml) | change with no call-path/hot-path relevance at all | report **nothing** — the domain is not materially implicated | `clean` |

Per-case provenance and a one- or two-sentence rationale also live in each
fixture's `metadata` block (`source`, `tags`, `rationale`) and in the
header comment.

## Validation

[`../../../../tests/unit/benchmark/test_performance_deepening_corpus.py`](../../../../tests/unit/benchmark/test_performance_deepening_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
used for the worked example and every other corpus. It never defines a
second one, and asserts: the sub-corpus stays small and documented; every
required outcome shape is present; every case pins an explicit `decision`
consistent with its required findings; every flagged case's required
finding is `P1`; every strictly clean case carries no findings at all; and
every finding's anchor resolves inside its own case's patch or base.
Matching a reviewer's output to these expectations and scoring it are out
of scope here (Issues #41 / #52 / #54). Peer review of the expected
findings themselves happens on the pull request.
