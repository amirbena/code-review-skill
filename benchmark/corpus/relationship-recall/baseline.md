# Relationship-Recall Baseline (current search-only reviewer)

Pre-enrichment baseline for Issue
[#602](https://github.com/amirbena/code-review-skill/issues/602), recorded
for later comparison in
[#605](https://github.com/amirbena/code-review-skill/issues/605). The
machine-readable record is
[`baseline-observations.json`](baseline-observations.json).

**This is a targeted baseline over six hand-crafted fixtures, not a
statistical sample.** No relationship-recall rate, per-class rate, or
general claim about the reviewer follows from it, and none is made. Each
row is one observation of one case.

## Run inputs

| Input | Value |
|---|---|
| Repository commit | `66ad316315db6b581f27e312e595b415d38bcd47` (fixtures were uncommitted when run; their SHA-256 are in the JSON record) |
| Command | `python3 runtime_platform/benchmark/scripts/run_benchmark.py --corpus-dir benchmark/corpus/relationship-recall [--case-id <id>] --timeout 600` |
| Reviewer | `claude` 2.1.281 reading the packaged `local-code-review` Skill; runner-default model and effort, not pinned |
| Scoring | The existing runner, matcher and metrics ([`match-criteria.md`](../../../runtime_platform/benchmark/match-criteria.md), [`missed-and-incorrect-findings.md`](../../../runtime_platform/benchmark/missed-and-incorrect-findings.md)); no second validator |
| Result schema | The runner's own `run` / `metrics` output. `benchmark-result/v1` is not used: it seals scheduled lane runs over the full comprehensive corpus, and this is an ad hoc sub-corpus run |
| Repetitions | One execution per case. No repeated runs |

Reproducing a row means re-running the command for its case against the
recorded commit and fixtures. Model output is not deterministic, so a
re-run is a new observation, not a replay.

## Per-case observations

Outcome vocabulary: **correct** (expected conclusion reached), **wrong**
(a finding where the fixture expects none), **missed** (a required finding
absent), **not observed** (no valid review outcome).

| Case | Class / role | Outcome | Produced | Category |
|---|---|---|---|---|
| `relrecall-affected-test-stale-assertion-unlinked-name` | affected test, positive | correct | one P1 naming `tests/test_order_summary.py` and its stale assertion, anchored at the changed line in `app/shipping/rates.py` | scoring correction |
| `relrecall-affected-test-still-holds-control` | affected test, control | correct | one optional P2 missing-test note on the new express branch | expected behavior |
| `relrecall-affected-test-external-cases-unresolvable` | affected test, unresolvable | wrong | one P1 (`external-contract-drift`) that the externally loaded cases may be stale | genuine limitation |
| `relrecall-interface-optional-member-implementers-compatible-control` | interface, control | correct | no findings | expected behavior |
| `relrecall-interface-config-registered-implementers-unresolvable` | interface, unresolvable | wrong | one P1 that the narrowed contract cannot be validated against implementers loaded from `cache-plugins.json` | genuine limitation |
| `relrecall-analogue-pattern-source-outside-repository-unresolvable` | analogue, unresolvable | **not observed** | none; `reviewer-adapter-raised` | execution error |

Five valid observations and one unobserved case. No case was missed.

## Evidence boundaries

### Fixture and scoring corrections made before the canonical observation

- **Affected-test positive (scoring).** As run, the matcher scored a miss
  plus a false positive: the reviewer reported the stale test but anchored
  the finding at the changed production line, not the test file, and path
  is authoritative in matching. The fixture gained an `alternatives` entry
  accepting the same defect at `app/shipping/rates.py`; the claim must
  still correspond, so an unrelated finding at either location does not
  match. The recorded output was re-scored **offline** with that entry
  (0 false negatives, 0 false positives). It was not re-run.
- **Interface unresolvable (fixture).** The initial run raised a P0 because
  the base omitted `errors.ts`, so `RedisCache.ts` imported a file that did
  not exist. That run is contaminated and non-canonical. After adding
  `errors.ts`, the case was re-run once; the re-run is the canonical
  observation.
- **Analogue unresolvable (fixture), not observed.** The first run reported
  a P2 that `STATUS_LABELS` duplicates `DELIVERY_STATUSES`, because the
  fixture base still exposed `dispatcher.py`. That run is contaminated and
  non-canonical, and the earlier `KeyError` finding was likewise a fixture
  artifact. After removing `dispatcher.py` and the `KeyError` behavior, the
  corrected-fixture run returned `reviewer-adapter-raised`. That execution
  gives **no evidence about reviewer behavior**: it is not classified as
  correct, wrong, a miss, a false positive or a false negative, and nothing
  is inferred about what the reviewer would have produced. It was not
  repeated.

### Genuine current-reviewer limitation

Two valid observations are wrong in the same way. For the external test
cases and the config-registered implementers, the reviewer recognized that
the relationship could not be established from the repository and reported
that uncertainty as a P1 finding. The current system has no representation
of an unresolved relationship, so it cannot say "checked, could not
resolve" and escalates instead. This is the gap
[#601](https://github.com/amirbena/code-review-skill/issues/601) (#607)
has since defined the `unresolved` outcome for. These are baseline results
for the reviewer at `66ad316`, before #601, not fixture defects.

## Limitations

- **Consumer class: no live observation.** The consumer/caller cases are
  the existing `repository-intelligence` fixtures. They were run once in an
  earlier, broader pass, but that pass is not part of this baseline: the
  canonical baseline is the six cases above. Those outputs are optional
  research context only and are reused later by #605.
- **Cross-partition: not measurable here.** See the
  [class map](README.md#cross-partition-not-measurable).
- **Pre-#601 reviewer.** The observations describe the reviewer at
  `66ad316`, which could not express an unresolved relationship. See
  [what the baseline can and cannot express](README.md#what-the-baseline-can-and-cannot-express).
  #601 has since landed; assertions about unresolved-relationship visibility
  are now unblocked and are not part of this baseline.
- **Fixture hashes are run-time records.** `baseline-observations.json`
  stores each fixture's SHA-256 at run time. Fixture header comments and
  rationale text were reworded afterward (metadata only; no `input` or
  `expected` change), so the hashes are provenance, not a live pin.
- **Six cases, one observation each.** No rate, per-class rate or general
  relationship-recall claim.
- **Control cases show no discovery evidence.** A case with no findings
  does not show whether the relationship was found and found harmless or
  never looked at; the outcome is scored, discovery is not.
- **Contaminated runs are not counted.** The pre-correction interface and
  analogue runs are excluded from every figure above.
