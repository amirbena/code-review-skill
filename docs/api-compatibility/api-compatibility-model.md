# API / Contract Compatibility Model

Repository-development design record for **[#175](https://github.com/amirbena/code-review-skill/issues/175)**.
Not packaged; explanatory. It is the canonical home for the recognized
contract types and their diff-recognition signals, the per-change-shape
compatible / breaking / context-dependent classification with a worked
example, and the smallest useful first implementation. The packaged
[`shared/policies/review-scope.md`](../../shared/policies/review-scope.md),
"API / contract compatibility review," defines the operative rule a
reviewer actually applies and references this document by name; it does
not restate this document's rationale or worked examples.

The fixture corpus exercising the six change shapes below is
[`../benchmark/corpus/api-compatibility/`](../benchmark/corpus/api-compatibility/README.md)
([#184](https://github.com/amirbena/code-review-skill/issues/184)),
validated by
[`../../tests/unit/benchmark/test_api_compatibility_corpus.py`](../../tests/unit/benchmark/test_api_compatibility_corpus.py)
through the single reference validator
[`../../tests/reference/benchmark/benchmark_fixture.py`](../../tests/reference/benchmark/benchmark_fixture.py).
The prose-contract coverage for the packaged section itself is
[`../../tests/policy/review/test_review_scope_behavioral_heuristics.py`](../../tests/policy/review/test_review_scope_behavioral_heuristics.py).

## 1. Problem and goal

A change is sometimes only correct relative to a contract other code or
other systems depend on: an OpenAPI or JSON Schema document, a
protobuf/IDL definition, a public API request/response model, an
event/message schema, or a configuration contract read elsewhere.
Detecting that such a file changed is easy — the reviewer's harder problem
is reasoning about whether the change *breaks consumers*, and doing so
without either inventing a breakage claim the diff cannot support or
missing a break that is actually there.

The goal is a reviewer capability that explicitly reasons about backward
compatibility of a changed repository contract and classifies the change
as **compatible**, **breaking**, or **context-dependent**, backed by
evidence, tied to the existing severity and evidence model — no new
severity, no probability score — and that fails closed when the consumer
surface or contract intent cannot be established.

## 2. Recognized contract types and their diff-recognition signal

| Contract type | Diff-recognition signal |
| --- | --- |
| OpenAPI / REST API definition | A changed OpenAPI/Swagger document, or a changed request/response model or route annotation the framework derives one from. |
| JSON Schema | A changed `.json`/`.yaml` document using JSON Schema keywords (`properties`, `required`, `enum`, `$ref`, …), or a changed model whose serialization is governed by one. |
| protobuf / other IDL | A changed `.proto` (or other schema-IDL) file defining a message, service, or RPC contract. |
| Public API model / DTO | A changed class, struct, record, or interface that is part of a documented or externally consumed request/response shape — recognized by its role (crosses a service boundary), never by name or annotation alone. |
| Event / message schema | A changed definition of a message, event, or command payload published to a queue, topic, or webhook. |
| Configuration contract | A changed configuration schema or documented option set read by another service, job, or deployment. |

Recognition is a **diff-level signal that a contract may be in scope**,
never itself the finding: the change shape (§3) still has to be reasoned
about before anything is reported. A schema/IDL file changing, or a public
model's field set or type changing, is the trigger; a keyword or filename
match alone is never sufficient — the same discipline "Evidence is
semantic, not structural" in
[`review-scope.md`](../../shared/policies/review-scope.md) already applies
elsewhere in this policy.

## 3. Change shapes and their classification

| Change shape | Classification | Why |
| --- | --- | --- |
| Add optional field/property (or a new endpoint/message type) | **Compatible** | No existing consumer's expectations change; an absent field is exactly what "optional" already permits. |
| Remove field/property | **Breaking** | An existing consumer that reads it loses the value outright. |
| Optional narrowed to required | **Breaking** | It invalidates inputs an existing consumer already sends without the new requirement, without deleting anything. |
| Rename field/property (response or request) | **Breaking** | Breaking in both directions: existing readers of the old name stop finding it, and existing senders never learn the new one — a distinct failure shape from plain removal even though it rhymes with it. |
| Remove enum member | **Breaking** | No existing consumer can already tolerate a value it has never seen ceasing to exist — the deliberate asymmetric pair to "add enum member" below. |
| Add enum member | **Context-dependent** | Additive for a consumer that ignores unknown members; breaking for one with an exhaustive switch/case or closed-set validation. The diff alone cannot establish which kind of consumer exists — see §4. |
| Incompatible type change (widened/narrowed representation, changed value semantics) | **Breaking** (when it can produce a value an existing consumer's prior assumptions do not admit) | Reasoned per the concrete shape — for example a numeric type narrowed to a smaller range, or a string field repurposed to carry a different meaning, is breaking for the same reason field removal is: an existing consumer's assumption about the value stops holding. |
| Additive-compatible change not covered above (a new response header, a new optional query parameter, a widened numeric range) | **Compatible** | Same reasoning as the first row: nothing an existing consumer already relies on changes. |

### Worked example — the matched enum pair

`PaymentStatus` gaining a `refunded` member and `PaymentStatus` losing a
`failed` member are the same kind of edit (one enum member) on the same
enum, differing only in direction. Removing `failed` is unconditionally
**breaking** — no existing consumer can already tolerate a value ceasing
to exist. Adding `refunded` is **context-dependent** — a consumer with an
exhaustive `switch` over `PaymentStatus` breaks silently or loudly
depending on its own default case, while a consumer that reads the field
permissively is unaffected. A correct review's behavior turns on which
change shape occurred, not on "an enum changed" alone. This pair is
pinned exactly as
[`api-compat-add-enum-member-context-dependent.yaml`](../benchmark/corpus/api-compatibility/api-compat-add-enum-member-context-dependent.yaml)
and
[`api-compat-remove-enum-member-breaking.yaml`](../benchmark/corpus/api-compatibility/api-compat-remove-enum-member-breaking.yaml).

## 4. Fail-closed on unresolvable consumer intent

The fixture format has no separate "context-dependent" decision token —
only `clean` / `changes-required`, mechanically derived. For the "add
enum member" shape, and any other shape whose consequence turns on a
consumer property the diff does not reveal, the reviewer does not invent
a required breaking finding: **`decision: clean`, with at most an
optional finding** that names the specific unresolved question (for
example, "does any consumer treat `PaymentStatus` as a closed,
exhaustively-switched set?") rather than asserting a break the evidence
cannot support.

This mirrors, and does not replace, the fail-closed discipline already
used by "Architectural placement and execution-lifecycle fidelity" for
insufficient evidence: "insufficient evidence" is a valid terminal
outcome, not a license to speculate or to keep expanding context. It is
never resolved by retrieving another repository's consumer code — an
unresolved consumer surface stays unresolved (see
[`README.md`](README.md), "Non-goals").

## 5. Tie to the existing severity and evidence model

No new severity, finding category, or score is introduced. A
breaking-shape finding is labeled confirmed defect / credible engineering
risk exactly like any other finding
([`evidence.md`](../../shared/policies/evidence.md)) and classified per
[`severity.md`](../../shared/policies/severity.md) — the six breaking
cases in §3 are typically **P1**: a consumer-facing correctness break that
is not yet observable as a production incident. An optional ambiguity
note from §4 is typically **P2** or lower, and never on its own forces
`CHANGES REQUIRED` — the mechanical decision derivation in
[`severity.md`](../../shared/policies/severity.md) is unchanged and still
runs exactly once, over the finalized findings.

## 6. Smallest useful first implementation

1. **This model** — the recognized contract types (§2), the change-shape
   classification table with its worked example (§3), and the fail-closed
   rule (§4) — consumed as reviewer discipline.
2. **One packaged section** —
   [`shared/policies/review-scope.md`](../../shared/policies/review-scope.md),
   "API / contract compatibility review," so the capability is real in
   both Skills' review behavior, not only designed. It is wired as a depth
   owner of the existing "API / integration contracts" dimension in
   "Semantic change-implication reasoning," alongside — never
   replacing — "Affected-test / test-impact analysis" and "Architectural
   placement and execution-lifecycle fidelity"'s caller/callee-contract
   trigger.
3. **The fixture corpus** — already landed as
   [#184](https://github.com/amirbena/code-review-skill/issues/184),
   pinning the expected classification for each change shape in §3 ahead
   of this design record.

**Deferred** (named here so scope stays fixed):

- cross-repository contract retrieval to resolve an ambiguous consumer
  surface ([#133](https://github.com/amirbena/code-review-skill/issues/133));
- a dedicated schema-linter or SAST-style structural validator — this
  capability is semantic reasoning layered on the existing evidence model,
  never a second, competing tool;
- any per-finding numeric or probabilistic compatibility score.

**Rejected alternatives:**

- **A dedicated `context-dependent` fixture-format decision token**,
  distinct from the existing `clean` / `changes-required` pair, so an
  "add enum member"-shaped case could pin its ambiguity directly as a
  decision rather than as an optional finding under `clean`. Rejected: it
  would have required a fixture-format change ahead of, and independent
  of, this capability, duplicating a decision the mechanical severity
  model already expresses through the optional-finding / no-finding
  distinction — see [`fixture-format.md`](../benchmark/fixture-format.md)
  §7 and the #184 corpus README's own note on this exact question.
- **A standalone schema-diff script or tool** (invoked as a build/CI step
  to mechanically compute compatible/breaking) instead of reviewer
  prose. Rejected as the first implementation: it would require choosing
  and maintaining a parser per contract type (OpenAPI, protobuf, JSON
  Schema, ad hoc DTOs), duplicating existing schema-linter tooling this
  capability explicitly does not compete with (see
  [`README.md`](README.md), "Non-goals"), and would not generalize to a
  public API model or DTO with no machine-readable schema at all — the
  case reviewer semantic reasoning already covers uniformly.
- **Treating "enum member added" as unconditionally compatible** (the
  simplest possible rule, ignoring exhaustive-switch consumers).
  Rejected: it would silently under-report the #184
  `api-compat-add-enum-member-context-dependent.yaml` case's whole reason
  for existing — the matched add/remove pair is pinned specifically to
  show that "an enum changed" is not, by itself, a safe compatible/
  breaking signal.

## 7. Relationship to existing canonical policies

- [`review-scope.md`](../../shared/policies/review-scope.md), "Semantic
  change-implication reasoning," owns the "API / integration contracts"
  dimension this capability is one depth owner of; it does not redefine
  the dimension or its activation signal.
- [`review-scope.md`](../../shared/policies/review-scope.md),
  "Affected-test / test-impact analysis," and "Architectural placement and
  execution-lifecycle fidelity"'s caller/callee-contract trigger remain
  the depth owners for, respectively, dependent-test impact and call
  sites actually present in the diff; this capability is the depth owner
  for consumers that need not appear as a call site at all.
- [`evidence.md`](../../shared/policies/evidence.md) owns the code-evidence
  bar and the confirmed-defect / credible-risk labeling; §5 does not
  relax it.
- [`severity.md`](../../shared/policies/severity.md) owns severity and the
  mechanical decision derivation; §5 does not touch either.
