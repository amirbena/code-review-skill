# Publication-Mode Benchmark Corpus

Repository-development artifact for GitHub Issue
[#316](https://github.com/amirbena/code-review-skill/issues/316), a
focused benchmark/workbench fixture set proving that `github-pr-review`'s
canonical PASSIVE / SEMI / ACTIVE publication semantics — introduced by
[#314](https://github.com/amirbena/code-review-skill/issues/314)
(`skills/github-pr-review/policies/review-action-authorization.md`) —
cannot regress unnoticed at the end-to-end publication-boundary level:
mode resolution, publication intent, formal-action selection, actual
side-effect presence/absence, semi/active semantic equivalence, the
self-review boundary, and the review-publication-only authority boundary.

This corpus does **not** redesign #314's publication semantics — see that
policy's own "Migration from the pre-#314 model" section for the product
decision this benchmark only *proves*, never re-derives.

## Why this is not a `benchmark-case/v1` corpus

Unlike the corpora under [`../`](../README.md) (each a self-contained
inline patch plus expected review findings), this boundary's inputs and
expectations are not a diff and a set of findings — they are a publication
mode, a reviewed HEAD/independence/permission fact set, and a structural
publication outcome (a resolved mode, a formal event, a "would publish"
preview, and the GitHub-bound artifact — or its absence).
[`../../fixture-format.md`](../../fixture-format.md)'s `expected` block has
no field for any of that. Rather than stretch that closed schema, this
corpus follows the same test-only, data-driven reference-fixture pattern
[`../delegation-spawn/README.md`](../delegation-spawn/README.md) and
[`../reviewer-brief/README.md`](../reviewer-brief/README.md) already
established for domains the schema does not fit:

- [`../../../../tests/reference/benchmark/publication_mode_fixtures.py`](../../../../tests/reference/benchmark/publication_mode_fixtures.py) —
  one `PublicationModeCase` per required outcome shape, each a
  zero-argument `run()` closure that exercises the *single* reference
  model,
  [`../../../../tests/reference/review/review_action_authorization.py`](../../../../tests/reference/review/review_action_authorization.py)
  (`resolve_mutation_outcome` / `normalize_intent`), plus
  `emit_publication_artifact`, which constructs the actual GitHub-bound
  publication artifact a submitted or withheld outcome would produce (or
  proves none is constructed) — mirroring
  [`review-output.md`](../../../../skills/github-pr-review/policies/review-output.md),
  "Batched review construction and submission" (one review submission of
  `body` + inline comments + `event`, or the narrower self-review
  informational `COMMENT`).
- [`../../../../tests/unit/benchmark/test_publication_mode_corpus.py`](../../../../tests/unit/benchmark/test_publication_mode_corpus.py) —
  runs every case's `run()` and asserts its actual outcome matches the
  declared expectation, plus corpus-completeness checks (every required
  category), the malformed-fixture rejection suite, and dedicated
  cross-case assertions (semi/active equivalence, the PR #297 regression
  shape, the artifact-level authority boundary, phrasing robustness).

This corpus is **not** a duplicate of
[`../../../../tests/unit/review/test_review_action_authorization.py`](../../../../tests/unit/review/test_review_action_authorization.py),
which #314 already landed as an extensive unit suite against the same
reference model, including its own PR #297-style regression test
(`ActiveRequestIsSufficientAuthorization`). That suite is *why* the
boundary holds; this corpus is the declarative, metadata-bearing
**benchmark** layer #316 asks for, and it is the only place that inspects
the *constructed GitHub-bound publication artifact itself* — not only the
`MutationOutcome` the resolver returns — satisfying #316's mandatory
"Publication-artifact verification" requirement: a caller-facing sentence
saying nothing was posted is not sufficient evidence on its own.

## Evaluation style

Every comparison in this corpus is a **deterministic structural
assertion** — resolved mode, formal event, "would publish" event, and the
emitted-or-absent artifact's own `kind`/`event`/`body`/`inline_comments`
fields — never an LLM/rubric score. The one exception is the bounded
"invocation phrasing robustness" category, which normalizes a small,
closed set of natural-language phrasings (the canonical examples from
`review-action-authorization.md`, "Natural-language publication intent",
plus their close synonyms) to a canonical mode; it is explicitly **not** a
general NL-parser benchmark (#316 non-goal). This corpus is disjoint from
the finding-precision/recall/severity metrics
([#41](https://github.com/amirbena/code-review-skill/issues/41)) and from
every other domain corpus — it never touches a finding's content, only
publication-boundary structure.

## Categories and required outcome shapes

| Category | Required shapes |
| --- | --- |
| `passive` | clean and blocking reviews both return their verdict to the caller and emit **no** GitHub-bound artifact at all |
| `semi` | runs the same decision path as `active` and computes the same intended event (`would_publish`); never emits an artifact; a case that regresses to `would_publish == NONE` (degrading into ordinary `passive` behavior) fails |
| `active` | clean → `APPROVE` reaches the publication boundary as a `formal_review` artifact; blocking → `REQUEST_CHANGES` does; no second activation phrase is ever consulted |
| `regression_297` | the stable, named PR #297-shape fixture: explicit `ACTIVE` + clean review + reasoned `APPROVE` + a caller otherwise allowed to publish + no second activation phrase → `publication = true`, formal action = `APPROVE`; must never resolve to `WITHHELD` for a missing-activation reason |
| `mode_invariant` | for equivalent review input, `passive` → `publication = false`; `semi` → `publication = false` with intent computed; `active` → `publication = true`; `semi.would_publish == active.event` for the same input |
| `self_review` | across all three modes, no formal event is ever produced on the reviewer's own work; only `active` self-review publishes the canonical contract's explicitly-allowed informational `COMMENT` artifact — `passive`/`semi` self-review publish nothing at all |
| `authority_boundary` | the artifact an `active` publication constructs carries only the fields in `GITHUB_PUBLICATION_CAPABILITIES` — never a file-edit/patch/commit/push/merge/repository-settings/unrelated-issue-or-PR-mutation/sandbox/spawn capability; checked structurally against the artifact's own dataclass shape, not by simulating [#301](https://github.com/amirbena/code-review-skill/issues/301)'s mutation-executor internals |
| `phrasing` | a small, bounded set of equivalent invocation phrasings (canonical documented examples plus close synonyms) resolve to the correct canonical mode without a magic second activation phrase |

Every case's category, covered requirement tags, and declared expectation
live in its `PublicationModeCase` definition in
`publication_mode_fixtures.py` — this table is a map, not a second source
of truth.

## Related security boundary

[#301](https://github.com/amirbena/code-review-skill/issues/301) (the
`AUTH-###` capability ladder) is related — the `authority_boundary`
category proves `active` publication never widens into that ladder's later
stages — but this corpus has **no implementation dependency** on #301 and
does not benchmark its mutation-executor internals, per #316's own scope.

## Focused selection

Run this corpus alone, independently of the rest of the benchmark suite:

```sh
python3 -m unittest tests.unit.benchmark.test_publication_mode_corpus
```
