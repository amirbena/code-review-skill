# Specialist-Depth Composition Benchmark Corpus

Repository-development artifact for GitHub Issue
[#85](https://github.com/amirbena/code-review-skill/issues/85), child of
epic [#47](https://github.com/amirbena/code-review-skill/issues/47). This
is a **focused sub-corpus** of [`benchmark-case/v2`](../../fixture-format.md)
fixtures pinning the **architecture-level** activation/composition
contract [`specialist-depth.md`](../../../../shared/policies/specialist-depth.md)
(#82) already defines — not the correctness of any single domain
capability's reasoning, which the domain fixture corpora below already
own.

Every case conforms to [`../../fixture-format.md`](../../fixture-format.md)
and is a self-contained inline `patch` plus its `base` pre-image, so the
corpus runs without network access. Like the rest of
[`../`](../README.md) and [`../../`](../../README.md) this is **not**
packaged into either Skill archive and no packaged Skill resource depends
on it — it is consumed only by this repository's own test suite, through
the single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
(never a second one).

## Selection principle

- **One case per way #82's composition contract can play out**, mirroring
  [`specialist-depth.md`](../../../../shared/policies/specialist-depth.md)'s
  own worked examples Case A through Case G verbatim: zero capabilities
  engaging, exactly one, several composing, a superficial signal that
  must not force activation, semantic evidence triggering activation with
  no expected file type, cascading activation bounded by
  [`repository-expansion.md`](../../../../shared/policies/repository-expansion.md)
  (#87), and review depth never by itself expanding required remediation
  ([`remediation-scope-boundary.md`](../../../../shared/policies/remediation-scope-boundary.md),
  #258).
- **Reuse over re-derivation.** Cases B, C (in part), D, F (in part), and
  G reuse the shape of an existing single-domain corpus's own fixture
  (Security #271, Database/Migration #186, Performance #187) as the
  integration input, exactly as Issue #85's Scope requires — this corpus
  proves activation/composition/boundedness, not domain correctness a
  moved-in fixture already covers. Case A and Case E have no existing
  single-domain equivalent to reuse (a "nothing is implicated" case and a
  "no expected file type" case are architecture-level shapes, not domain
  ones) and are this corpus's own minimal fixtures.
- **`exhaustive` completeness.** Every case uses the default
  `findings_completeness: exhaustive`, so an unexpected finding — for
  example a capability engaging that the case's evidence does not
  warrant — is itself a corpus failure.
- **Intentionally small.** One case per required outcome shape (Cases
  A–G), not a combinatorial sweep across all five deepening capabilities.

## Fixture-level scope: what a `benchmark-case/v2` fixture cannot pin

Exactly as [`../risk-depth/README.md`](../risk-depth/README.md) and
[`../repository-intelligence/README.md`](../repository-intelligence/README.md)
already establish for their own mechanisms: `benchmark-case/v2`'s schema
is closed (see [`../../fixture-format.md`](../../fixture-format.md) §2)
and has no field for "which capabilities engaged" — only
`expected.findings` and `expected.decision`. Unlike risk-based review
depth (a deterministic catalog computed from concrete signals, see
[`change-risk-signals.md`](../../../../shared/policies/change-risk-signals.md)),
specialist-depth activation is an evidence-driven reasoning judgment with
no equivalent computable reference model — the same reason the five
domain-deepening sub-corpora below have no reference-model scenario file
of their own either. So the corpus fixture pins the **expected finding
outcome** a correct review must produce; how many required findings of
which `defect_kind`s are present, which the test suite below asserts per
case, is what stands in as the observable proxy for "which capability
engaged and how many did."

## Cases

| File | Composition shape (specialist-depth.md) | A correct review must… | Decision |
|---|---|---|---|
| [`specialist-depth-composition-case-a-zero-capabilities-base-reasoning-complete.yaml`](specialist-depth-composition-case-a-zero-capabilities-base-reasoning-complete.yaml) | Case A — zero capabilities engage; base reasoning stays complete | report only the ordinary base-level guard-inversion defect; the bounded per-item comprehension must not trigger performance deepening | `changes-required` |
| [`specialist-depth-composition-case-b-one-capability-security-confused-deputy.yaml`](specialist-depth-composition-case-b-one-capability-security-confused-deputy.yaml) | Case B — exactly one capability engages | report the confused-deputy P0 (reusing #271's fixture); no other capability's finding appears | `changes-required` |
| [`specialist-depth-composition-case-c-multiple-capabilities-database-and-performance.yaml`](specialist-depth-composition-case-c-multiple-capabilities-database-and-performance.yaml) | Case C — multiple independently-warranted capabilities compose | report both the missing-backfill P1 and the N+1 P1 in one unified review, neither gating the other | `changes-required` |
| [`specialist-depth-composition-case-d-superficial-signal-suppressed-clean.yaml`](specialist-depth-composition-case-d-superficial-signal-suppressed-clean.yaml) | Case D — a superficial file/path signal does not force activation | report nothing; a migrations/ path alone is not evidence | `clean` |
| [`specialist-depth-composition-case-e-semantic-evidence-without-expected-file-type.yaml`](specialist-depth-composition-case-e-semantic-evidence-without-expected-file-type.yaml) | Case E — semantic evidence triggers deepening with no expected file type | report the cache-shape coexistence defect even though no `.sql` file or migration directory is touched | `changes-required` |
| [`specialist-depth-composition-case-f-cascading-activation-bounded.yaml`](specialist-depth-composition-case-f-cascading-activation-bounded.yaml) | Case F — cascading activation, bounded by #87 | report both the index-removal P1 and the resulting hot-path scan P1, the second surfaced only by tracing the first one hop | `changes-required` |
| [`specialist-depth-composition-case-g-remediation-scope-unaffected-by-depth.yaml`](specialist-depth-composition-case-g-remediation-scope-unaffected-by-depth.yaml) | Case G — depth never by itself expands required remediation | report the one required, narrowly-scoped blocking-lock P1; the broader repo-wide lint observation stays `optional` | `changes-required` |

Per-case provenance and a one- or two-sentence rationale also live in each
fixture's `metadata` block (`source`, `tags`, `rationale`) and in the
header comment.

## Related sub-corpora

This corpus does not repeat, and is not repeated by, the single-domain
deepening corpora it reuses fixtures from:
[`../security-deepening/`](../security-deepening/README.md) (#271),
[`../distributed-systems-deepening/`](../distributed-systems-deepening/README.md)
(#272), [`../database-migration-deepening/`](../database-migration-deepening/README.md)
(#186), [`../performance-deepening/`](../performance-deepening/README.md)
(#187), and
[`../dependency-supply-chain-deepening/`](../dependency-supply-chain-deepening/README.md)
(#188). Each of those owns its own domain-correctness fixtures
exclusively; this corpus owns only the cross-capability
activation/composition/boundedness shapes those corpora's own tests
explicitly defer to it (see, for example, each domain corpus's
`test_no_cross_domain_composition_case_present` test).

## Validation

[`../../../../tests/unit/benchmark/test_specialist_depth_composition_corpus.py`](../../../../tests/unit/benchmark/test_specialist_depth_composition_corpus.py)
loads every `*.yaml` here through the same single reference validator
[`../../../../tests/reference/benchmark/benchmark_fixture.py`](../../../../tests/reference/benchmark/benchmark_fixture.py)
used everywhere else in this corpus (it never defines a second one), and
asserts: the sub-corpus stays small and documented; all seven required
cases are present; every case pins an explicit `decision` consistent with
its required findings; Case A's required finding carries no
domain-specific `defect_kind`; Cases B/C/E/F/G's required findings carry
the domain-specific `defect_kind`s the composition shape requires, in the
counts that shape requires (one for B, two independent ones for C, one
with no expected file type for E, two cascaded ones for F, exactly one
required plus one explicitly optional for G); and Case D and Case G's
optional/absent findings never become required. Matching a reviewer's
output to these expectations and scoring it are out of scope here (Issues
#41 / #52 / #54). Peer review of the expected findings themselves happens
on the pull request.
