# Relationship-Recall Benchmark Corpus

Repository-development artifact for GitHub Issue
[#602](https://github.com/amirbena/code-review-skill/issues/602) (R2 of
epic [#600](https://github.com/amirbena/code-review-skill/issues/600)). A
focused sub-corpus of
[`benchmark-case/v2`](../../../runtime_platform/benchmark/fixture-format.md)
fixtures, plus a class map and a recorded baseline, that measure whether the
**current search-only reviewer** reaches the correct review conclusion when
that conclusion depends on a relationship outside the diff.

It scores the **review outcome** — correct finding, correct no-finding,
missed, wrong — through the existing runner and matcher. It never scores
whether a search found an edge. It adds no provider, changes no review
behavior, and defines no second validator: every case is validated by
[`benchmark_fixture.py`](../../../runtime_platform/benchmark/reference/benchmark_fixture.py)
and indexed in [`corpus-index.json`](../../corpus-index.json). Like the rest
of [`../`](../README.md) it is not packaged into either Skill archive.

## Relationship classes

Each class has a positive, a control, and an unresolvable case, or a recorded
reason it is not measurable. Cases that
[`../repository-intelligence/`](../repository-intelligence/README.md)
(#129) and [`../analogue-placement-pattern/`](../analogue-placement-pattern/README.md)
(#328) already cover are reused by reference, not duplicated. Cases owned by
this directory carry the `relrecall-` prefix.

| Class | Positive | Control (resolves, changes nothing) | Unresolvable |
|---|---|---|---|
| Consumer of a changed callable | [`repo-intel-python-call-site-caller-null-deref`](../repository-intelligence/repo-intel-python-call-site-caller-null-deref.yaml) | [`repo-intel-python-control-compatible-caller-no-finding`](../repository-intelligence/repo-intel-python-control-compatible-caller-no-finding.yaml) | [`repo-intel-python-dynamic-dispatch-safe-failure`](../repository-intelligence/repo-intel-python-dynamic-dispatch-safe-failure.yaml) |
| Affected test not linked by naming | [`relrecall-affected-test-stale-assertion-unlinked-name`](relrecall-affected-test-stale-assertion-unlinked-name.yaml) | [`relrecall-affected-test-still-holds-control`](relrecall-affected-test-still-holds-control.yaml) | [`relrecall-affected-test-external-cases-unresolvable`](relrecall-affected-test-external-cases-unresolvable.yaml) |
| Implementation / interface | [`repo-intel-typescript-interface-contract-implementer-break`](../repository-intelligence/repo-intel-typescript-interface-contract-implementer-break.yaml) | [`relrecall-interface-optional-member-implementers-compatible-control`](relrecall-interface-optional-member-implementers-compatible-control.yaml) | [`relrecall-interface-config-registered-implementers-unresolvable`](relrecall-interface-config-registered-implementers-unresolvable.yaml) |
| Architectural analogue | [`analogue-placement-status-label-duplication-missing-key`](../analogue-placement-pattern/analogue-placement-status-label-duplication-missing-key.yaml) | [`analogue-placement-test-file-split-clean`](../analogue-placement-pattern/analogue-placement-test-file-split-clean.yaml) | [`relrecall-analogue-pattern-source-outside-repository-unresolvable`](relrecall-analogue-pattern-source-outside-repository-unresolvable.yaml) (**baseline: not observed**, execution error) |
| Cross-partition relationship | not measurable | not measurable | not measurable |

[`repo-intel-python-config-consumer-stale-import`](../repository-intelligence/repo-intel-python-config-consumer-stale-import.yaml)
is a second consumer-class positive and is run with the baseline but not part
of the class map.

### Cross-partition: not measurable

A change is partitioned only at **≥ 1200 changed lines or ≥ 60 changed
files** ([`large-pr-partitioning.md`](../../../shared/policies/large-pr-partitioning.md)).
A hand-authored inline fixture cannot reach that threshold without becoming a
synthetic bulk patch, which the corpus
[selection principle](../README.md#selection-principle) rejects. The
[`risk-depth/`](../risk-depth/README.md) corpus already makes the same
choice and pins the threshold arithmetic against the reference model rather
than a fixture. A cross-partition case is not measurable by this corpus; it
needs a runner that can supply a large `repo_ref` change.

The recorded baseline over the six `relrecall-` cases is in
[`baseline.md`](baseline.md). It is a targeted pre-enrichment baseline, not a
statistical sample, and one case is explicitly **not observed**.

## Selection principle

- **The expected finding sits outside the diff.** A positive case's diff
  reads as unobjectionable on its own; the defect is in an unchanged file
  supplied through `input.base`.
- **A control proves breadth is not a finding.** The relationship resolves
  and is compatible, so the correct output is no finding.
- **An unresolvable case proves the review does not invent.** The relationship
  cannot be established from the repository (inputs, implementers, or the
  analogue live outside it), so the correct output is no finding.
- **`exhaustive` completeness** on every case, so an unexpected finding in
  either direction is a failure. Optional findings carry only a missing-test
  note, as elsewhere in the corpus.

## What the baseline can and cannot express

The current system has three terminal outcomes for a case: a finding, no
finding, or an error. It has **no way to express an unresolved relationship**.
`repository-expansion.md` and `review-stopping-criteria.md` treat
"insufficient evidence" as a complete outcome, so a relationship that was
checked and found absent and one that could not be established both end as
"no finding". An unresolvable case is therefore scored as a correct
no-finding when the review reports nothing, and that score cannot tell a
review that looked and could not resolve from one that never looked. The
fixtures pin the correct *conclusion*; whether the gap was *visible* is not
asserted here and is added once
[#601](https://github.com/amirbena/code-review-skill/issues/601) defines the
vocabulary.

## Validation

[`test_relationship_recall_corpus.py`](../../../tests/unit/benchmark/test_relationship_recall_corpus.py)
loads every fixture through the single reference validator and asserts the
class map above: every named case exists, each positive carries a required
finding, each control and unresolvable case carries none, and the
not-measurable class stays recorded with its reason. The corpus index is
regenerated with
`python3 runtime_platform/benchmark/scripts/build_benchmark_index.py` and
checked by the existing index tests.
