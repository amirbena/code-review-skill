# Analogue-Based Placement-Pattern-Inference Corpus

Repository-development artifact for GitHub Issue
[#328](https://github.com/amirbena/code-review-skill/issues/328). Parent
capability: [#327](https://github.com/amirbena/code-review-skill/issues/327),
which extends
[`../../../../shared/policies/architectural-placement.md`](../../../../shared/policies/architectural-placement.md),
"Analogue-based responsibility/placement pattern inference," so a review
can infer an established but undocumented local responsibility/placement
pattern from analogous implementations and flag a materially consequential
deviation from it. This is a **focused sub-corpus** of
[`benchmark-case/v2`](../../fixture-format.md) fixtures that pin the
expected outcomes for that capability and keep it from regressing into a
disguised style-consistency checker.

Every case conforms to [`../../fixture-format.md`](../../fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of
[`../`](../README.md) and [`../../`](../../README.md) this is **not**
packaged into either Skill archive and no packaged Skill resource depends
on it — it is consumed only by this repository's own test suite, through
the single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py).

## What this corpus does *not* assert

Every fixture here illustrates the reasoning behavior — not a preferred
structure. **No fixture asserts that centralizing a status-label table,
splitting integration tests into one file per connector, or centralizing
auth-header construction is itself the canonically correct choice.** The
established local pattern in each fixture is inferred from repository
evidence tying it to a real architectural, ownership, lifecycle, or
integration boundary (see `architectural-placement.md`'s "Analogue-based
responsibility/placement pattern inference," step 3); the corpus tests
whether the reviewer can tell that boundary apart from cosmetic repetition,
never whether a specific decomposition or test-organization style wins.

## Selection principle

- **One case per required outcome shape** in Issue #328's scope, so a
  regression in any one is unambiguous:
  - a real, consequence-bearing deviation from an established but
    undocumented pattern — flagged, with the finding stating the actual
    consequence and violated boundary, never merely "does not match
    convention";
  - a differently organized but semantically valid alternative to a
    repeated structure, where the repetition is cosmetic and no meaningful
    boundary stands behind it — no finding;
  - several changed locations violating the same inferred pattern for the
    same reason — one consolidated finding with the sites named, per
    [`../consolidation/README.md`](../consolidation/README.md)'s #177
    model, not one finding per site;
  - two changed locations that share only a cosmetic resemblance to each
    other while violating two different inferred patterns with two
    different consequences — two separate findings, proving grouping is
    never automatic.
- **Deliberately reuses one small fictional domain** (sibling partner-
  integration packages `slack` / `teams` / `pagerduty` versus a new
  `webhook` package) across the cases, the same way the worked example and
  other sub-corpora reuse a narrow domain — this keeps the corpus small
  while still isolating each outcome shape.
- **Every flagged case's consequence is already manifest in the diff**
  (a real `KeyError`-producing missing key, a real auth-header omission, a
  real disagreement between two duplicated copies) rather than a
  hypothetical "could drift later" — satisfying the concrete-consequence
  bar in `architectural-placement.md` and the severity discipline in
  [`../../../../shared/policies/severity.md`](../../../../shared/policies/severity.md),
  "Repository conventions and severity": severity tracks the consequence
  (a real crash, a real auth failure), never the mere fact that an implicit
  convention was violated.
- **Intentionally small.** A representative set for each outcome shape
  named in #328's scope, not exhaustive coverage of every analogue shape.

## Cases

| File | Outcome shape | A correct review must… | Decision |
|---|---|---|---|
| [`analogue-placement-status-label-duplication-missing-key.yaml`](analogue-placement-status-label-duplication-missing-key.yaml) | real deviation, concrete consequence | report one **P1/P2**: the new connector inlines the status-label table instead of centralizing it like its siblings, and the inline copy omits a key every connector must support, so a real status crashes `render_status` | `changes-required` |
| [`analogue-placement-test-file-split-clean.yaml`](analogue-placement-test-file-split-clean.yaml) | repeated structure, valid alternative | report **nothing** — splitting one connector's tests across two files instead of one is a structural difference with no evidenced boundary behind the repeated one-file shape | `clean` |
| [`analogue-placement-status-label-duplication-consolidated.yaml`](analogue-placement-status-label-duplication-consolidated.yaml) | same violation, three sites, one reason | report **one** consolidated finding naming all three affected files — not three near-duplicate findings | `changes-required` |
| [`analogue-placement-distinct-boundaries-not-consolidated.yaml`](analogue-placement-distinct-boundaries-not-consolidated.yaml) | cosmetically similar, materially different defects | report **two** separate findings — a label-centralization deviation and an unrelated auth-header-centralization deviation, never merged under one duplication finding | `changes-required` |

Per-case provenance and a one- or two-sentence rationale also live in each
fixture's `metadata` block (`source`, `tags`, `rationale`).

## Validation

[`../../../../tests/unit/benchmark/test_analogue_placement_pattern_corpus.py`](../../../../tests/unit/benchmark/test_analogue_placement_pattern_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
used for the worked example and every other corpus — never a second one —
and asserts: the sub-corpus stays small and documented; every
required outcome shape is present; every case pins an explicit `decision`
consistent with its required findings; the flagged/consolidated/paired
cases each carry the expected number of required findings while the
control case carries none; and every finding's anchor resolves inside its
own case's patch or base. Matching a reviewer's output to these
expectations and scoring it are out of scope here (Issues #41 / #52 /
#54). Peer review of the expected findings themselves happens on the pull
request.
