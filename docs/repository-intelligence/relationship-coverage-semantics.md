# Relationship Coverage Semantics

Repository-development design record for
**[#601](https://github.com/amirbena/code-review-skill/issues/601)** (child R1 of
epic #600). Not packaged; explanatory. The normative rules live in the packaged
[`repository-expansion.md`](../../shared/policies/repository-expansion.md),
"Relationship outcomes and unresolved relationships"; this record holds the
decision rationale, the rejected alternative, and the worked examples, and does
not restate those rules.

## 1. Problem

"Insufficient evidence" is a valid, complete terminal outcome
([`repository-expansion.md`](../../shared/policies/repository-expansion.md),
[`review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md),
[#129 §9](repository-intelligence-model.md)). A relationship that was checked
and found absent and one that could not be established therefore read the same,
and the second could pass as full coverage.

## 2. Coverage decision

| Option | Verdict |
| --- | --- |
| **A. Visibility-only disclosure** — coverage semantics unchanged; an `unresolved` relationship renders in a **Context gaps** section. | **Chosen.** |
| **B. Amend the closed incomplete-trigger set** with a fifth trigger for unresolved relationships. | **Rejected.** |

Why B is rejected:

- It would make `REVIEW INCOMPLETE` fire for ordinary reviews of dynamic,
  reflective, or unsupported-language code, where ambiguity is the normal case
  ([#129 §9](repository-intelligence-model.md), worked example 4). Status
  enforcement can treat `REVIEW INCOMPLETE` as non-passing, so a bounded,
  deterministic limit would start blocking merges.
- It would reverse "insufficient evidence is a valid terminal outcome", which
  #87, #129, and `review-stopping-criteria.md` all rely on.
- The epic requires review to work unchanged with no relationship capability
  present; under B that case would always be incomplete.

Accepted trade-off: `coverage: complete` means every required pass reached its
own stop condition, not that every relationship was resolved. The gap is carried
by the Context gaps section instead. Revisit only if the R5 comparison (#605)
shows readers missing the disclosure. This path needs maintainer sign-off.

## 3. Presentation and the existing models

- **Human surface:** optional Context gaps section in
  [`review-summary.md`](../../shared/templates/review-summary.md), omitted when
  nothing is unresolved, never a finding.
- **Machine surface:** a sibling `relationships` list with a per-relationship
  `outcome` inside the existing `repository_expansion` subordinate metadata;
  not nested under `triggers`, since `affected_test` is not an expansion
  trigger and has no ring. No new top-level model.
- **`confidence` (#178):** unchanged, no new value. `insufficient-context`
  remains the per-finding signal; Context gaps is the review-level signal and
  also covers relationships that produced no finding.
- **Unchanged:** stop-at-first-ring, the ring ceiling by change-risk depth,
  finding severity, identity, and the Decision rules.

## 4. Initial relationship classes

| Class | Review need that justifies it | Evidence |
| --- | --- | --- |
| `caller_consumer` | Callers and config/contract consumers decide whether a changed behavior breaks something the diff does not show. | #129 worked examples 1 and 3; `benchmark/corpus/repository-intelligence/` |
| `implementation_interface` | An untouched implementer can silently violate a changed interface. | #129 worked example 2 |
| `affected_test` | Tests that depend on changed behavior are only found by tracing, and a missed one reads as "tests are fine". | [`affected-test-analysis.md`](../../shared/policies/affected-test-analysis.md) (#160) |

Out of scope until a later contract adds them: architectural analogue and
relevant dependency (dependency overlaps #181 and cross-repository #133). A
`tested-by` or analogue relationship *kind* is an R3 (#603) extension of the
#129 closed model, not decided here.

## 5. Worked examples

Each class walks every outcome.

| Class | `resolved_relevant` | `resolved_none` | `unresolved` |
| --- | --- | --- | --- |
| `caller_consumer` | `get_user` now returns `None`; `charge_user` still assumes it raises → finding, edge carries `path:line`. | Public helper renamed; direct ring-1 search ran over the repo and finds no references → listed nowhere, not a gap. | `BaseHandler.process` is reached through `HANDLERS[kind]()`; `kind` is request data → Context gap, reason `ambiguous dispatch`. |
| `implementation_interface` | `Cache.get` narrowed; untouched `InMemoryCache` still returns `null` → finding. | Interface changed; ring 2–3 search lists the implementers and all already updated → no gap. | Interface implemented in a language the host search cannot parse → Context gap, reason `unsupported language shape`. |
| `affected_test` | Changed rounding rule; `test_totals.py` asserts the old value → finding. | Changed behavior; test search ran and no test references the symbol → no gap. | Changed behavior reached only through a fixture factory the test search cannot follow → Context gap, reason `test-to-symbol link not traceable`. |

In every `unresolved` cell, coverage stays `complete`, severity and the Decision
are unchanged, and the review does not say the relationship was checked.

## 6. Packaging and wiring

Packaged (existing files only, so no manifest or `skill.yaml` change):
`repository-expansion.md`, `review-stopping-criteria.md`,
`shared/templates/review-summary.md`, and the two Skill report templates
(subordinate-metadata line plus a Context gaps note). Guarded by
[`test_relationship_coverage_docs.py`](../../tests/policy/review/repository_intelligence/test_relationship_coverage_docs.py);
the existing `tests/policy/review/repository_intelligence/` suites stay green
with no pinned decision amended.

No retrieval mechanism, provider, or index is introduced; those are R3–R6 under
#600.
