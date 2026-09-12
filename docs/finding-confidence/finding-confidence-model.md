# Finding Confidence Model

Repository-development design record for **[#178](https://github.com/amirbena/code-review-skill/issues/178)**.
Not packaged; explanatory. It is the canonical home for the unified
`confidence` field — its closed value set, the entry criteria for each value,
how the runtime-evidence states from
[#128](https://github.com/amirbena/code-review-skill/issues/128) and the
authoritative/informational provenance from
[#118](https://github.com/amirbena/code-review-skill/issues/118) map onto the
one field, and the rule that a lower value never weakens the evidence bar,
the severity, or the review decision. The packaged
[`shared/templates/finding.md`](../../shared/templates/finding.md) defines the
field and references this document by name; it does not restate this table.

The test-only reference model is
[`../../tests/reference/review/finding_confidence.py`](../../tests/reference/review/finding_confidence.py);
its derivation corpus is exercised by
[`../../tests/unit/review/test_finding_confidence.py`](../../tests/unit/review/test_finding_confidence.py)
and the documentation contract by
[`../../tests/policy/review/test_finding_confidence_docs.py`](../../tests/policy/review/test_finding_confidence_docs.py).

## 1. Problem and goal

A finding today is effectively binary: reported or not. The reviewer's
epistemic state, though, varies. A defect confirmed by a bounded runtime
reproduction (#128), a credible static finding, a concern that hinges on an
external contract the reviewer could not inspect, and a case where a specific
piece of caller context was missing are all "reported", and a consumer
cannot tell them apart. Worse, #128 and #118 each introduced their own
state vocabulary — `reasoned` / `runtime-confirmed` / `attempted-inconclusive`
for runtime evidence, `authoritative` / `informational` for context
provenance — and nothing unifies them into a single field a machine consumer
can read.

The goal is a finding contract that carries **one** explicit,
machine-readable confidence / evidence-state field, with a small closed set
of values, consistent across both Skills, that represents epistemic state
**without** weakening the evidence bar and **without** inventing a
probability score or an "AI confidence %".

It is **never a probability score**: not a numeric score, not a per-finding
risk model, not an "AI confidence %", and not a second decision path. It is a
label.

## 2. The closed value set

`confidence` is exactly one of the following. The set is closed; a Skill
never emits any other value.

| Value | Meaning | Entry criteria |
| --- | --- | --- |
| `confirmed` | The defect is not in doubt — the evidence directly demonstrates the incorrect behavior. | A targeted runtime reproduction returned `runtime-confirmed` (#128); **or** static code evidence directly demonstrates the incorrect behavior (the "confirmed defect" label in [`evidence.md`](../../shared/policies/evidence.md)); **or** an authoritative contextual source (#118 — a `requirement`, `acceptance_criteria` entry, `accepted_decision`, or `repository_policy`) is the proof that a stated contract is violated **and** the code evidence shows the violation. |
| `credible` | A plausible failure mode is supported by concrete evidence, but the defect is not directly demonstrated. | The finding meets the "credible engineering risk" bar in [`evidence.md`](../../shared/policies/evidence.md) on its static evidence, and none of the more specific values below applies. **This is the default** (see §5) and the floor: every reported finding is at least `credible`. |
| `runtime-validation-unavailable` | The finding was a genuine candidate for a targeted runtime check, one was attempted, and it could not conclude. | The finding was eligible for targeted validation per [`runtime-validation.md`](../../shared/policies/runtime-validation.md), "Eligibility", a reproduction was attempted, and the run was `attempted-inconclusive` (boundary unavailable or unverifiable, budget exceeded, unsafe, artifact-leak check failed, or an ambiguous result) — and no independent basis makes it `confirmed`. |
| `external-contract-unvalidated` | The finding is credible on the code in view, but its correctness turns on the behavior of an external contract the reviewer could not inspect within the review boundary. | The reviewer can name a specific external dependency whose semantics decide the finding — a third-party API's documented behavior, an out-of-repo service, a schema owned elsewhere — and could not validate it read-only within the review. The unvalidated assumption is stated in the finding. |
| `insufficient-context` | The reviewer has concrete code evidence of a problem, but a bounded, material piece of caller-supplied context needed to fully characterize it was missing. | A specific contextual question is unresolved — the `REPORT_AMBIGUITY` outcome of the [contextual-evidence model](../review-context/contextual-evidence-model.md) §7, where it is material to this finding — and the finding still independently meets the `credible` bar on its own code evidence. It is **never** a way to report a finding that does not clear that bar (see §6). |

## 3. Reconciliation — one field, not three overlapping ones

`confidence` is the finding's **single machine-readable epistemic-state
field**. The two fields introduced by #128 and #118 remain, but as
**provenance detail only** — they record *what was done* and *what informed
the finding*, not an independent verdict on how sure the reviewer is:

- **`runtime validation`** (#128) keeps recording which targeted reproduction
  ran (an existing repository test, or a minimal generated check) and its
  bounded pass/fail evidence. Its `reasoned` / `runtime-confirmed` /
  `attempted-inconclusive` values stay as the runtime-specific detail, but
  the finding's epistemic state is now expressed once, in `confidence`, by
  the fixed mapping below. There is no contradiction: the `runtime
  validation` line says what happened in the sandbox; `confidence` says the
  resulting epistemic level.
- **`contextual evidence`** (#118) keeps listing which caller-supplied
  context informed the finding. The authoritative-vs-informational typing of
  each source stays owned by the
  [contextual-evidence model](../review-context/contextual-evidence-model.md)
  and is **not** a second epistemic field: an authoritative source that
  proves a violation the code exhibits contributes `confirmed`; an
  unresolved authoritative question contributes `insufficient-context`;
  informational context contributes nothing to `confidence`.

### Mapping table

| Source signal | Contribution to `confidence` |
| --- | --- |
| `runtime validation` = `runtime-confirmed` | `confirmed` |
| `runtime validation` = `attempted-inconclusive` | `runtime-validation-unavailable` |
| `runtime validation` = `reasoned` (default) | no contribution |
| code evidence directly demonstrates the defect ([`evidence.md`](../../shared/policies/evidence.md), "confirmed defect") | `confirmed` |
| code evidence supports a plausible failure mode ([`evidence.md`](../../shared/policies/evidence.md), "credible engineering risk") | `credible` |
| authoritative contextual source is the proof of a violation the code exhibits | `confirmed` |
| authoritative contextual question unresolved (`REPORT_AMBIGUITY`, material to the finding) | `insufficient-context` |
| informational contextual source | no contribution |
| finding's correctness turns on an unvalidated external contract | `external-contract-unvalidated` |

## 4. Deterministic derivation order

When more than one signal applies, `confidence` is the first match in this
order:

1. any signal contributes `confirmed` → **`confirmed`**;
2. else a targeted run was attempted and inconclusive →
   **`runtime-validation-unavailable`**;
3. else the finding's correctness turns on an unvalidated external contract →
   **`external-contract-unvalidated`**;
4. else a bounded, material contextual question is unresolved →
   **`insufficient-context`**;
5. else → **`credible`**.

`confirmed` always wins. The three "open question" values rank by how
directly the unresolved basis bears on the finding; the reviewer records the
single value naming the most decision-relevant one. `credible` is the floor
and the tie-break.

## 5. Default

When a Skill does not compute `confidence` for a finding, the value is
**`credible`**. Every reported finding has already cleared the
"credible engineering risk" bar of
[`evidence.md`](../../shared/policies/evidence.md), so `credible` is the
correct, non-weakening default — it asserts exactly what reporting the
finding already asserts, and nothing more. A finding is never emitted with an
absent or unknown `confidence`.

## 6. Confidence never lowers the bar, the severity, or the decision

This is the load-bearing invariant.

- **The evidence bar is unchanged.** Every reported finding still
  independently meets [`evidence.md`](../../shared/policies/evidence.md):
  concrete repository evidence, and the confirmed-defect / credible-risk /
  optional-improvement labeling. A `confidence` below `confirmed` is an
  annotation on a finding that has **already** cleared that bar; it is never
  a licence to report one that has not. `insufficient-context` in particular
  never converts a speculative hunch into a reportable finding — the code
  evidence must stand on its own first.
- **Severity is unchanged.** `confidence` never calculates, raises, lowers,
  or overrides the P0/P1/P2 severity derived from impact per
  [`severity.md`](../../shared/policies/severity.md). `confirmed` does not
  escalate a P2; `insufficient-context`, `external-contract-unvalidated`,
  and `runtime-validation-unavailable` do not de-escalate a P1 and do not
  suppress a finding.
- **The decision is unchanged.** The mechanical `REVIEW CLEAN` /
  `CHANGES REQUIRED` (or `Approve` / `Request Changes`) derivation in
  [`severity.md`](../../shared/policies/severity.md), "Decision derivation
  (mechanical)", runs exactly once over the finalized findings and never
  reads `confidence`. There is no second decision path.
- **Identity is unchanged.** `confidence` never changes a finding's
  identity, its deduplication, or its cross-review matching. Two renderings
  of one finding carry the same `confidence`; a re-review may legitimately
  move a finding's `confidence` (e.g. a later targeted run confirms it)
  without that being a new finding.

## 7. Output

- **Machine-readable output.** `confidence` is a required field of the #67
  review-output schema when that schema lands, alongside `severity`,
  `location`, `evidence`, and the rest — one value from §2, defaulting to
  `credible` per §5. It is **always** carried there, regardless of the
  human-surface suppression below. #178 defines the field and its values;
  #67 wires it into the schema document and #68 versions it.
- **Human-readable output.** `confidence` renders on the finding only when it
  is **not** the `credible` default, **and** it is omitted from human output
  when it would only repeat a `Runtime validation` line already shown — a
  `runtime-confirmed` line present alongside `confidence` `confirmed`, or an
  `attempted-inconclusive` line alongside `confidence`
  `runtime-validation-unavailable` (the two lines would carry the same
  epistemic fact). It still renders when the value adds something that line
  does not: a `confirmed` established by static or contextual evidence,
  `external-contract-unvalidated`, or `insufficient-context`. This is the
  same "optional fields render only when they add information" rule the
  finding template already applies to `runtime validation`'s `reasoned`
  default. On the full rendering it is its own line after `Evidence` (and
  after any `Runtime validation` line); on the GitHub inline surface it folds
  into the `Evidence:` prose. See
  [`shared/templates/finding-rendering.md`](../../shared/templates/finding-rendering.md).

## 8. Non-goals

- **No numeric probability or "AI confidence %" scoring.** The value set is
  five named states, nothing else.
- **`insufficient-context` is not a speculation channel.** It annotates a
  finding that already meets the evidence bar; it never lowers it (§6).
- **No change to severity derivation or the review decision** (§6).
- **No new retrieval, execution, or mutation capability.** #178 adds one
  finding field and this model as reviewer discipline. It does not add
  context retrieval, does not change what runtime validation may run, and
  grants no mutation.

## 9. Smallest useful first implementation

1. **This model** — the closed value set (§2), the reconciliation of the
   #128 and #118 states onto the one field (§3), the derivation order (§4),
   the default (§5), and the non-weakening invariant (§6) — consumed as
   reviewer discipline.
2. **One packaged field** — the optional **confidence** field and its
   rendering contract on
   [`shared/templates/finding.md`](../../shared/templates/finding.md), so the
   epistemic state is real in output, not only designed.
3. **Reference-level cross-links** — from
   [`runtime-validation.md`](../../shared/policies/runtime-validation.md) and
   the [contextual-evidence model](../review-context/contextual-evidence-model.md)
   to this document; no value set or table duplicated into packaged policy.

**Deferred** (named here so scope stays fixed):

- the #67 machine-readable output schema document itself, and its
  versioning (#68);
- any per-finding numeric or probabilistic scoring;
- runtime that automatically resolves an `external-contract-unvalidated`
  assumption by fetching the external contract.

## 10. Relationship to existing canonical policies

- [`evidence.md`](../../shared/policies/evidence.md) owns the code-evidence
  bar and the confirmed-defect / credible-risk / optional-improvement
  labeling. `confidence` sits on top of that bar and never relaxes it.
- [`runtime-validation.md`](../../shared/policies/runtime-validation.md) owns
  the `reasoned` / `runtime-confirmed` / `attempted-inconclusive` runtime
  state. This model maps that state onto `confidence` (§3) and does not
  redefine it.
- The [contextual-evidence model](../review-context/contextual-evidence-model.md)
  owns the authoritative/informational typing and the resolution outcomes.
  This model consumes them (§3) and does not redefine them.
- [`severity.md`](../../shared/policies/severity.md) owns severity and the
  mechanical decision derivation; §6 does not touch it.
- [`shared/templates/finding.md`](../../shared/templates/finding.md) owns the
  finding contract; the **confidence** field is defined there and described
  here.
