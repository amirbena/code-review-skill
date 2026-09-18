# Decision-Derivation Benchmark

Repository-development artifact for GitHub Issue
[#450](https://github.com/amirbena/code-review-skill/issues/450). This is
a focused [`benchmark-case/v2`](../../fixture-format.md) sub-corpus that
proves the **reverse direction** of the mechanical severity → decision
path defined in
[`../../../../shared/policies/severity.md`](../../../../shared/policies/severity.md),
"Decision derivation (mechanical)": a **P2-only, or empty, finding set
must always render `REVIEW CLEAN` (`Approve` on GitHub) — never
`CHANGES REQUIRED` (`Request Changes`)**.

## Why this corpus exists

[#350](https://github.com/amirbena/code-review-skill/issues/350) proves
the normal-path direction end-to-end against the real packaged Skill: a
real P0/P1 finding must never render a clean verdict. Nothing proved the
opposite direction until now.
[#449](https://github.com/amirbena/code-review-skill/issues/449) (closed,
fixed by PR #452, "Require an explicit P0/P1 tally before rendering the
review decision") was a real production instance of exactly that
reverse-direction failure: a P2-only review rendered `CHANGES REQUIRED`
because a finding's own strongly-worded recommendation was allowed to
influence the rendered outcome. #449's fix is already in place (the
mechanical P0/P1 tally is now a required precondition of rendering a
decision); this corpus is the end-to-end regression guard that keeps that
fix proven against the real packaged Skill, not just at the pure-function
level.

**At the time this corpus was written, [#350](https://github.com/amirbena/code-review-skill/issues/350)
had not yet landed any fixture**, so there is no sibling `benchmark-case/v2`
directory for it to sit alongside per the issue's own phrasing ("alongside
#350's fixture(s)"). Rather than invent a placeholder directory for #350's
future opposite-polarity cases, this corpus is scoped to #450's own
requirement only, under its own directory named for the domain both issues
share (mechanical decision *derivation*, as opposed to
[`../verdict-consistency/`](../verdict-consistency/README.md)'s downstream
*rendering-consistency* domain — see "Distinguishing this corpus" below).
When #350 lands, its blocking-direction fixtures belong in this same
`decision-derivation/` directory (same domain, opposite polarity), not a
second directory — this README should be updated at that point to
document both directions side by side, the same way sibling corpora
document multiple outcome shapes in one place.

## Why this *is* a `benchmark-case/v2` corpus

Unlike [`../verdict-consistency/`](../verdict-consistency/README.md) (which
starts from an already-finalized decision and a downstream signal, with no
patch and no finding — a data-driven reference-fixture corpus), this
corpus is about **derivation correctness**: does reviewing a *real code
change* end-to-end through the packaged Skill produce the right findings
and the right mechanically-derived decision? That is exactly what
`benchmark-case/v2` (self-contained inline patch + expected findings +
expected decision) is for, per
[`../../fixture-format.md`](../../fixture-format.md) — the same format
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
- **Each case still expects `decision: clean`.** The point of this corpus
  is that severity, not wording or finding count, is the only thing that
  can move the decision — see
  [`../../fixture-format.md`](../../fixture-format.md) §7's mechanical
  derivation and §11 rule 11's fail-closed check that a fixture's own
  `decision` is consistent with it.
- **Deliberately reuses one small fictional domain** (a `reports/` export
  helper and an `admin/` dashboard helper) across the cases, the same way
  sibling sub-corpora reuse a narrow domain to stay small while still
  isolating each outcome shape.
- **Intentionally small.** Three cases are the smallest representative set
  for #450's three named outcome shapes; this is not a general P2-finding
  quality corpus (that breadth is the root corpus's and
  [`../candidate-finding-validation/`](../candidate-finding-validation/README.md)'s
  job).

## Cases

| File | Outcome shape | A correct review must… | Decision |
|---|---|---|---|
| [`dd-p2-only-mild-wording.yaml`](dd-p2-only-mild-wording.yaml) | P2-only, plain wording | report **one P2** (a duplicated constant) and still return `clean` | `clean` |
| [`dd-p2-only-urgent-wording.yaml`](dd-p2-only-urgent-wording.yaml) | P2-only, deliberately urgent/blocking-sounding wording (#449's regression shape) | report **one P2** whose claim text reads as urgent ("CRITICAL", "must be fixed before merge", "blocking violation") and still return `clean` — wording never independently produces a blocking decision | `clean` |
| [`dd-zero-findings-clean.yaml`](dd-zero-findings-clean.yaml) | zero findings | report **nothing** and return `clean` | `clean` |

Per-case provenance and rationale also live in each fixture's `metadata`
block (`source`, `tags`, `rationale`).

## Distinguishing this corpus

- **From [#350](https://github.com/amirbena/code-review-skill/issues/350)
  (opposite polarity).** #350 proves a real P0/P1 finding must never
  render clean — the forward direction. This corpus proves the reverse: a
  P2-only or empty finding set must never render blocking. A regression in
  #350's (future) fixtures means a real defect got waved through; a
  regression here means a non-blocking or absent finding got blocked
  anyway — the exact #449 failure mode.
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
python3 scripts/benchmark/run_benchmark.py --corpus-dir docs/benchmark/corpus/decision-derivation
python3 -m unittest tests.unit.benchmark.test_decision_derivation_corpus
```

## On Skill coverage (local-code-review and github-pr-review)

`benchmark-case/v2`'s `expected.decision` vocabulary is deliberately
Skill-neutral (`clean` / `changes-required` — see
[`../../fixture-format.md`](../../fixture-format.md) §1): `clean` is
`local-code-review`'s `REVIEW CLEAN` **and** `github-pr-review`'s
`Approve` event, per
[`../../../../shared/policies/severity.md`](../../../../shared/policies/severity.md),
"Decision derivation (mechanical)". Every fixture here is written against
that shared vocabulary, not against either Skill's surface wording, so it
states the same expectation for both Skills by construction.

The real end-to-end run this corpus's unit test drives
(`tests/unit/benchmark/test_decision_derivation_corpus.py`, via
`scripts/benchmark/benchmark_review_adapter.ProductionReviewerAdapter`)
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

## Validation

[`../../../../tests/unit/benchmark/test_decision_derivation_corpus.py`](../../../../tests/unit/benchmark/test_decision_derivation_corpus.py)
loads every fixture here through the single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
— it never defines a second one — and asserts: the three named outcome
shapes are present; every fixture's required findings are `P2` only (no
`P0`/`P1` anywhere in this corpus, since that is the opposite-polarity
concern #350 owns); every fixture's `decision` is the mechanically
consistent `clean`; and the urgent-wording fixture's `claim` text actually
carries alarming/blocking-sounding language, so the case cannot silently
regress into an unremarkable P2. The same test module also drives every
fixture through the real packaged Skill end-to-end via
`ProductionReviewerAdapter` — gated on the same `check_runtime_available`
preflight
[`test_production_adapter_e2e.py`](../../../../tests/unit/benchmark/test_production_adapter_e2e.py)
uses, so the real-runtime path fails loudly with a clear reason rather
than being silently skipped or fabricating a result — and asserts the
rendered decision derived from the real produced findings
(`tests/reference/review/decision_semantics.derive_decision`) is
`Decision.CLEAN` for every case. Peer review of the expected findings
themselves happens on the pull request.
