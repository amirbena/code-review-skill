# Engineering Design Deepening Regression Fixture Corpus

Repository-development artifact for GitHub Issue
[#750](https://github.com/amirbena/code-review-skill/issues/750), a small
deterministic fixture corpus for the Engineering Design Review capability
delivered by [#749](https://github.com/amirbena/code-review-skill/issues/749)
under parent [#747](https://github.com/amirbena/code-review-skill/issues/747).
It is a **focused sub-corpus** of
[`benchmark-case/v2`](../../../runtime_platform/benchmark/fixture-format.md)
fixtures: functional and regression validation, not measurement. The
capability is specified in
[`../../../shared/policies/engineering-design-deepening.md`](../../../shared/policies/engineering-design-deepening.md)
and designed in
[`../../../docs/engineering-design-review/engineering-design-review-contract.md`](../../../docs/engineering-design-review/engineering-design-review-contract.md)
(§7.3, §8, §17); the expectations here must stay consistent with both.

Every case is a self-contained inline `patch` plus its `base` pre-image, so
the corpus runs without network access. Like the rest of
[`../`](../README.md) it is **not** packaged into either Skill archive and
is consumed only by this repository's own test suite, through the single
reference validator
[`../../../runtime_platform/benchmark/reference/benchmark_fixture.py`](../../../runtime_platform/benchmark/reference/benchmark_fixture.py)
(never a second one). It adds no runner, lane, schedule, or gate; the cases
are picked up by the existing comprehensive lane through programmatic corpus
discovery.

## Selection principle

The set is representative, not exhaustive: the six case types the issue
names, plus the three cases the contract (§17) makes testable (T2, an
unverified claim, a typo-only edit). Each case isolates one outcome so a
regression in any one is unambiguous. Design-only findings stay `P2`;
only the case where code contradicts an accepted decision is `P1`, because
its impact is real.

| File | Outcome shape | A correct review must… | Decision |
|---|---|---|---|
| [`…-ack-before-persist-loses-events.yaml`](engineering-design-deepening-ack-before-persist-loses-events.yaml) | credible architectural risk | report one **P2**: acknowledge-before-persist cannot meet the document's own no-loss goal | `clean` |
| [`…-claim-contradicted-by-repository.yaml`](engineering-design-deepening-claim-contradicted-by-repository.yaml) | claim about existing code contradicted | report one **P2**: the handler the design relies on has no deduplication | `clean` |
| [`…-code-contradicts-accepted-adr.yaml`](engineering-design-deepening-code-contradicts-accepted-adr.yaml) | implementation contradicts an accepted decision (T1) | report one **P1**: direct ledger insert bypasses the service the accepted ADR requires | `changes-required` |
| [`…-self-declared-accepted-grants-nothing.yaml`](engineering-design-deepening-self-declared-accepted-grants-nothing.yaml) | self-declared acceptance (T2) | report one **P2**: the new ADR is a proposal that contradicts an accepted one unacknowledged | `clean` |
| [`…-preference-only-alternative-clean.yaml`](engineering-design-deepening-preference-only-alternative-clean.yaml) | preference-only candidate | report **nothing** | `clean` |
| [`…-acknowledged-tradeoff-clean.yaml`](engineering-design-deepening-acknowledged-tradeoff-clean.yaml) | trade-off the document acknowledges | report **nothing** | `clean` |
| [`…-missing-sections-not-a-finding-clean.yaml`](engineering-design-deepening-missing-sections-not-a-finding-clean.yaml) | missing information | report **nothing**, and no Context gap | `clean` |
| [`…-unverified-claim-no-finding-clean.yaml`](engineering-design-deepening-unverified-claim-no-finding-clean.yaml) | claim about an unreachable (API-only) unchanged file | report **nothing** and not imply the claim was verified | `clean` |
| [`…-typo-only-adr-edit-inert-clean.yaml`](engineering-design-deepening-typo-only-adr-edit-inert-clean.yaml) | non-activation | report **nothing**: a spelling fix changes no decision | `clean` |

## Evaluation dimensions

| Dimension | Pinned by |
|---|---|
| Required-finding detection | the four positive cases, one required finding each |
| False-positive behavior | the five negative cases with `findings: []` |
| Severity stays evidence-driven | design-only findings are `P2`; only the code-vs-accepted-ADR case is `P1`; none is `P0` |
| Evidence quality | each `claim` names the design anchor and the contradicting repository or ADR evidence |
| Existing contracts unchanged | the existing corpora and policy tests, unchanged |

## Results and limitations

- **Fixture validity.** All nine cases parse and validate through the single
  reference validator, resolve every anchor inside their own patch or base,
  and are indexed under the new `engineering-design` capability value; this
  is asserted by
  [`../../../tests/unit/benchmark/test_engineering_design_deepening_corpus.py`](../../../tests/unit/benchmark/test_engineering_design_deepening_corpus.py).
- **No live reviewer run is recorded here.** Authoring this corpus ran no
  benchmark harness (Issue #750 non-goal), so recall, false-positive rate,
  and baseline comparison are **not measured**. They come from the next
  comprehensive-lane run, which discovers this directory automatically; file
  a focused follow-up for any genuine defect it surfaces.
- **Context gaps and the Reasoning check are not directly assertable.**
  `benchmark-case/v2` has no key for an expected Context gap or Reasoning
  check. The missing-information case pins the observable part (no finding);
  that no Context gap is emitted for missing information, and that Context
  gaps and the Reasoning check are unchanged, is asserted by the policy tests
  for #749. This corpus records no evidence that either needs to change.
- **API-only reach is approximated.** The unverified-claim case omits the
  claimed file from both patch and base, which is what an API-only review
  sees for an unchanged path. It does not exercise a real adapter.
- **Supersession (T3) and resolved-thread (T4) cases are not included.** The
  set stays small; expand only with evidence that it is insufficient.

## Validation

[`../../../tests/unit/benchmark/test_engineering_design_deepening_corpus.py`](../../../tests/unit/benchmark/test_engineering_design_deepening_corpus.py)
loads every `*.yaml` here through the reference validator and asserts the set
stays small and documented, the positive cases carry one required finding with
the expected severity and decision, the negative cases carry no finding and
decide `clean`, and no case is `P0`.
