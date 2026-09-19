# Decision-Derivation Benchmark

Repository-development artifact for GitHub Issue
[#450](https://github.com/amirbena/code-review-skill/issues/450). This is
a focused [`benchmark-case/v2`](../../../../runtime_platform/benchmark/fixture-format.md) sub-corpus that
proves both directions of the mechanical severity → decision path defined
in
[`../../../../shared/policies/severity.md`](../../../../shared/policies/severity.md),
"Decision derivation (mechanical)":

- **reverse direction (#450):** a P2-only, or empty, finding set must
  always render `REVIEW CLEAN` (`Approve` on GitHub) — never
  `CHANGES REQUIRED` (`Request Changes`);
- **forward direction
  ([#350](https://github.com/amirbena/code-review-skill/issues/350)):** a
  P0/P1 finding must always render `CHANGES REQUIRED` (`Request Changes`)
  — never `REVIEW CLEAN` (`Approve`).

## Why this corpus exists

[#350](https://github.com/amirbena/code-review-skill/issues/350) proves
the normal-path (forward) direction end-to-end against the real packaged
Skill: a real P0/P1 finding must never render a clean verdict. It is the
cheapest, highest-signal check for the verdict-drift failure mode raised
by the review-reliability audit in
[`../../../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md`](../../../benchmark-measurement-architecture/benchmark-measurement-architecture-model.md)
§12.4 ("Benchmark proof"). It is proof only: it builds no enforcement
mechanism and changes nothing in a live review (the runtime boundary is
[`../verdict-consistency/`](../verdict-consistency/README.md)'s concern).

[#449](https://github.com/amirbena/code-review-skill/issues/449) (closed,
fixed by PR #452, "Require an explicit P0/P1 tally before rendering the
review decision") was a real production instance of the opposite,
reverse-direction failure: a P2-only review rendered `CHANGES REQUIRED`
because a finding's own strongly-worded recommendation was allowed to
influence the rendered outcome. #449's fix is already in place (the
mechanical P0/P1 tally is now a required precondition of rendering a
decision); #450's cases are the end-to-end regression guard that keeps
that fix proven against the real packaged Skill, not just at the
pure-function level.

Both directions live in this one directory because they share one domain
(mechanical decision *derivation*, as opposed to
[`../verdict-consistency/`](../verdict-consistency/README.md)'s downstream
*rendering-consistency* domain — see "Distinguishing this corpus" below).
Fixture-name prefixes tell them apart: `dd-blocking-*` is #350's, every
other `dd-*` fixture is #450's.

## Why this *is* a `benchmark-case/v2` corpus

Unlike [`../verdict-consistency/`](../verdict-consistency/README.md) (which
starts from an already-finalized decision and a downstream signal, with no
patch and no finding — a data-driven reference-fixture corpus), this
corpus is about **derivation correctness**: does reviewing a *real code
change* end-to-end through the packaged Skill produce the right findings
and the right mechanically-derived decision? That is exactly what
`benchmark-case/v2` (self-contained inline patch + expected findings +
expected decision) is for, per
[`../../fixture-format.md`](../../../../runtime_platform/benchmark/fixture-format.md) — the same format
[`../candidate-finding-validation/`](../candidate-finding-validation/README.md)
and the root corpus use.

## Selection principle

- **One case per required outcome shape** named in #450's scope:
  - a P2-only finding set described in ordinary review language
    (`dd-p2-only-mild-wording.yaml`);
  - a P2-only finding set whose finding carries deliberately strong,
    urgent, blocking-sounding wording — the direct regression shape of
    #449 — while its severity stays `P2`
    (`dd-p2-only-urgent-wording.yaml`);
  - an empty finding set (`dd-zero-findings-clean.yaml`).
- **One case per blocking severity (#350).** Each carries one
  unambiguous, unarguable defect and expects `decision: changes-required`:
  a textbook SQL injection (P0, `dd-blocking-p0-sql-injection.yaml`) and
  an inverted-operand functional bug (P1,
  `dd-blocking-p1-inverted-error-rate.yaml`, which permits `[P0, P1]` —
  both derive the same blocking decision). Each also carries an optional
  missing-test finding so a correct extra finding is not scored as
  unexpected.
- **The #450 cases expect `decision: clean`; the #350 cases expect
  `changes-required`.** The point of the corpus is that severity, not
  wording or finding count, is the only thing that can move the decision —
  see
  [`../../fixture-format.md`](../../../../runtime_platform/benchmark/fixture-format.md) §7's mechanical
  derivation and §11 rule 11's fail-closed check that a fixture's own
  `decision` is consistent with it.
- **Deliberately reuses one small fictional domain** (a `reports/` export
  helper and an `admin/` dashboard helper) across the cases, the same way
  sibling sub-corpora reuse a narrow domain to stay small while still
  isolating each outcome shape.
- **Intentionally small.** Three cases are the smallest representative set
  for #450's three named outcome shapes and two for #350's two blocking
  severities; this is not a general finding-quality corpus (that breadth is the root corpus's and
  [`../candidate-finding-validation/`](../candidate-finding-validation/README.md)'s
  job).

## Cases

| File | Outcome shape | A correct review must… | Decision |
|---|---|---|---|
| [`dd-p2-only-mild-wording.yaml`](dd-p2-only-mild-wording.yaml) | P2-only, plain wording | report **one P2** (a duplicated constant) and still return `clean` | `clean` |
| [`dd-p2-only-urgent-wording.yaml`](dd-p2-only-urgent-wording.yaml) | P2-only, deliberately urgent/blocking-sounding wording (#449's regression shape) | report **one P2** whose claim text reads as urgent ("CRITICAL", "must be fixed before merge", "blocking violation") and still return `clean` — wording never independently produces a blocking decision | `clean` |
| [`dd-zero-findings-clean.yaml`](dd-zero-findings-clean.yaml) | zero findings | report **nothing** and return `clean` | `clean` |
| [`dd-blocking-p0-sql-injection.yaml`](dd-blocking-p0-sql-injection.yaml) | unambiguous P0 (SQL injection) | report the **P0** and render the blocking Result and Decision | `changes-required` |
| [`dd-blocking-p1-inverted-error-rate.yaml`](dd-blocking-p1-inverted-error-rate.yaml) | unambiguous P1 (inverted division operands) | report the **P0/P1** and render the blocking Result and Decision | `changes-required` |

Per-case provenance and rationale also live in each fixture's `metadata`
block (`source`, `tags`, `rationale`).

## Distinguishing this corpus

- **#350 vs #450 (opposite polarity, same directory).** #350's
  `dd-blocking-*` cases prove a real P0/P1 finding must never render
  clean; #450's other cases prove a P2-only or empty finding set must
  never render blocking. A regression in #350's cases means a real defect
  got waved through; a regression in #450's means a non-blocking or absent
  finding got blocked anyway — the exact #449 failure mode.
- **From [`../verdict-consistency/`](../verdict-consistency/README.md)
  (#377/#378, downstream-consistency enforcement).** That corpus takes an
  **already-finalized, correct** mechanical decision as ground truth and
  asks whether a *downstream* rendered/submitted artifact is deliberately
  drifted away from it — a rendering/publication-boundary concern, with no
  patch and no finding. This corpus never starts from an already-correct
  decision; it asks whether the *derivation itself*, run against a real
  code change through the real packaged Skill, lands on the right decision
  in the first place. A regression in `verdict-consistency` means a
  correct decision was rendered or published incorrectly; a regression
  here means the decision itself was derived incorrectly.

## Running just this benchmark

```sh
python3 runtime_platform/benchmark/scripts/run_benchmark.py --corpus-dir docs/benchmark/corpus/decision-derivation
python3 -m unittest tests.unit.benchmark.test_decision_derivation_corpus
python3 -m unittest tests.unit.benchmark.test_blocking_verdict_corpus
```

`run_benchmark.py` scores findings against each fixture; the rendered
Result/Decision assertion below is what
`test_blocking_verdict_corpus` adds. It exits non-zero before touching any
case when the review runtime is unavailable, so a missing runtime is never
read as a clean result. See "Runtime availability" below for the unit
tests' equivalent.

## On Skill coverage (local-code-review and github-pr-review)

`benchmark-case/v2`'s `expected.decision` vocabulary is deliberately
Skill-neutral (`clean` / `changes-required` — see
[`../../fixture-format.md`](../../../../runtime_platform/benchmark/fixture-format.md) §1): `clean` is
`local-code-review`'s `REVIEW CLEAN` **and** `github-pr-review`'s
`Approve` event, per
[`../../../../shared/policies/severity.md`](../../../../shared/policies/severity.md),
"Decision derivation (mechanical)". Every fixture here is written against
that shared vocabulary, not against either Skill's surface wording, so it
states the same expectation for both Skills by construction.

The real end-to-end run this corpus's unit test drives
(`tests/unit/benchmark/test_decision_derivation_corpus.py`, via
`runtime_platform/benchmark/scripts/benchmark_review_adapter.ProductionReviewerAdapter`)
exercises `local-code-review` only — that adapter is, today, the only
production reviewer adapter this repository's benchmark tooling has for
any corpus (see its own module docstring), and no equivalent
`github-pr-review` production adapter exists yet. That is an existing gap
in the benchmark runtime, not one introduced by this corpus: no other
`benchmark-case/v2` corpus in this repository has a real end-to-end
`github-pr-review` run either. Extending the production adapter to also
drive `github-pr-review`'s approving-review-event path is future
benchmark-runtime work, not part of #450's scope (#450 does not touch
severity.md's derivation rule or the P0/P1/P2 model, and does not build a
second runtime adapter).

#350's proof has the same boundary. `local-code-review` is the only Skill
run live; `github-pr-review`'s non-approve outcome is covered at the
rendered-label level instead. The same check
(`benchmark_blocking_verdict.classify_rendered_label`) recognizes the
GitHub vocabulary (`Request Changes` / `REQUEST_CHANGES` as blocking,
`Approve` / `APPROVE` as clean), and the unit tests assert a P0/P1 finding
paired with an `Approve`/`APPROVE` signal is a violation. A live
`github-pr-review` run stays future benchmark-runtime work.

## Validation

[`../../../../tests/unit/benchmark/test_decision_derivation_corpus.py`](../../../../tests/unit/benchmark/test_decision_derivation_corpus.py)
loads every fixture here through the single reference validator
[`../../../../runtime_platform/benchmark/reference/benchmark_fixture.py`](../../../../runtime_platform/benchmark/reference/benchmark_fixture.py)
— it never defines a second one — and asserts, for the `dd-*` fixtures
that are not `dd-blocking-*`: the three named outcome
shapes are present; every fixture's required findings are `P2` only (the
`P0`/`P1` cases are #350's, below); every fixture's `decision` is the
mechanically consistent `clean`; and the urgent-wording fixture's `claim` text actually
carries alarming/blocking-sounding language, so the case cannot silently
regress into an unremarkable P2. The same test module also drives every
fixture through the real packaged Skill end-to-end via
`ProductionReviewerAdapter` — behind the shared runtime gate described
under "Runtime availability" below — and asserts the
rendered decision derived from the real produced findings
(`tests/reference/review/decision_semantics.derive_decision`) is
`Decision.CLEAN` for every case. Peer review of the expected findings
themselves happens on the pull request.

### Blocking-verdict validation (#350)

[`../../../../tests/unit/benchmark/test_blocking_verdict_corpus.py`](../../../../tests/unit/benchmark/test_blocking_verdict_corpus.py)
covers the `dd-blocking-*` fixtures through the same single validator. It
asserts each expects `changes-required` with a required P0/P1 finding,
that both severities are represented, that anchors occur in the patch, and
that each patch applies in an isolated workspace.

The rendered-verdict assertion is
[`../../../../runtime_platform/benchmark/reference/benchmark_blocking_verdict.py`](../../../../runtime_platform/benchmark/reference/benchmark_blocking_verdict.py)'s
`check_blocking_verdict`: when any produced finding is P0/P1, **both** the
report's `**Result:**` label and its `### Decision` label (extracted by
`benchmark_review_adapter.parse_rendered_outcome` from the adapter's
retained `last_report`) must not render clean. By default that is the
issue's "non-clean" bar: a clean, missing, or ambiguous label is a
violation, while the sanctioned non-clean outcomes (`REVIEW INCOMPLETE`,
and GitHub's informational `COMMENT` when a formal `REQUEST_CHANGES` is
withheld on own work) pass. `require_blocking=True` tightens that to the
blocking value itself; the live `local-code-review` class uses it, since
an incomplete review on these small patches is itself unexpected. The
severity → decision step reuses `decision_semantics.derive_decision` — no
second derivation path.

The live class runs each case through the real packaged Skill. Once the
runtime is available it fails, rather than passes, if a case errors or if
the reviewer produces no P0/P1 for these unambiguous defects — otherwise
the proof would be vacuous. A stub-CLI class exercises the same
adapter/runner/parser/check path without the runtime and proves a P0 paired
with `REVIEW CLEAN` fails the check.

### Runtime availability

Every live class in the benchmark unit tests (this corpus's two,
`test_production_adapter_e2e.py`) shares one gate,
`tests/support/benchmark_runtime.py`: it probes the runtime once, lazily,
through `check_runtime_available`. By default an unavailable runtime
**skips** with the reason printed, never a fabricated pass. Setting
`BENCHMARK_REQUIRE_RUNTIME=1` (or `true`/`yes`; `0`/`false` leave it off) turns that skip into an **error**, for
environments (such as a nightly lane) where a missing runtime must fail
the run rather than go unnoticed.
