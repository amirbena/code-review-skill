# Benchmark Fixture Format

Repository-development contract for GitHub Issue
[#50](https://github.com/amirbena/code-review-skill/issues/50). It defines
**one canonical machine-readable format for a single benchmark case** — the
fixed shape a corpus of cases
([#51](https://github.com/amirbena/code-review-skill/issues/51)) is written
in and a runner
([#52](https://github.com/amirbena/code-review-skill/issues/52)) executes
against, so review-quality results compare across runs instead of drifting
with an ad-hoc format. Parent capability:
[#40](https://github.com/amirbena/code-review-skill/issues/40).

Like [`../findings/`](../findings/README.md) and
[`../runtime-parallelism.md`](../runtime-parallelism.md), this is a
repository-development doc: **not** packaged into either Skill archive, and
no packaged Skill resource depends on it. It reuses the shared review
vocabulary — it does not define a parallel review model.

## Canonical invariant

> **A benchmark fixture describes what a correct review of one input must contain — never how a runner executes it, and never how results are scored.**

Every rule below is an elaboration of that sentence. Where a rule appears to
describe runner or scoring behavior, re-read it: the fixture only *states
the expectation*; comparing a reviewer's output against it, tolerating
noise, weighting categories, and aggregating pass rates are all downstream
concerns owned elsewhere (see §13).

## 1. Terminology and ownership

- **Finding** — one actionable review result in the shared shape of
  [`../../shared/templates/finding.md`](../../shared/templates/finding.md).
  This contract references that shape; it does not redefine a finding.
- **Severity** — exactly one of `P0` / `P1` / `P2`, defined by
  [`../../shared/policies/severity.md`](../../shared/policies/severity.md).
  A fixture states an *expected* severity per finding; it does not restate
  the P0/P1/P2 definitions.
- **Decision** — the mechanical `clean` / `changes-required` outcome that
  [`../../shared/policies/severity.md`](../../shared/policies/severity.md),
  "Decision derivation (mechanical)," derives from a finalized finding set.
  `clean` is that policy's `REVIEW CLEAN` / `Approve`; `changes-required`
  is its `CHANGES REQUIRED` / `Request Changes`. The tokens are
  Skill-neutral because a benchmark case is Skill-neutral.
- **`location_intent`** — the closed scope enum
  `line` / `symbol` / `file` / `cross-file` / `repository`, reused verbatim
  from [`../findings/finding-matching-strategy.md`](../findings/finding-matching-strategy.md)
  §2 (the finding-matching descriptor). A fixture's expected locations are
  expressed with it so the corpus and any later benchmark
  expected-vs-produced matcher share one location model.
- **`MATCH` / `NO MATCH` / `AMBIGUOUS` vocabulary** — the three-valued
  match result described in
  [`../findings/finding-matching-strategy.md`](../findings/finding-matching-strategy.md).
  That document is **completed stateful-re-review finding-*identity*
  research** (GitHub Issue
  [#59](https://github.com/amirbena/code-review-skill/issues/59), closed):
  it decides whether a finding in one review continues a finding from an
  earlier review of the same evolving change. It is **not** the owner of
  benchmark *expected-vs-produced* matching. This contract borrows only its
  vocabulary and its defect-continuity + site-continuity discipline as
  reusable prior art, and deliberately records **enough expected-finding
  identity/location information to make later matching measurable** (§8)
  **without** implementing any matcher. Which roadmap issue owns the
  benchmark matcher is stated in §13.

This contract does **not** define: the corpus (#51), the runner (#52),
regression reporting
([#53](https://github.com/amirbena/code-review-skill/issues/53)), scoring /
metrics / retrieval thresholds / aggregate quality
([#41](https://github.com/amirbena/code-review-skill/issues/41)), or
profile/risky fixture selection
([#47](https://github.com/amirbena/code-review-skill/issues/47) /
[#48](https://github.com/amirbena/code-review-skill/issues/48)).

## 2. Representation

**One benchmark case is one YAML document (one `.yaml` file).** YAML is
already the repository's structured-data format (Skill metadata, issue
templates) and `PyYAML` is already a dev dependency — no new dependency is
introduced. YAML also carries comments, which a hand-authored corpus and a
worked example need.

- The document MUST decode (via a YAML 1.1 safe loader) to a mapping.
- Keys are the literal strings defined below. The schema is **strict**: an
  unknown key anywhere is a rejection (§11), so a future field can never be
  silently ignored by an older reader or masked by a typo.
- Scalars are plain YAML scalars; multi-line strings (patches, file
  contents, claims) use block scalars.
- A validator consumes the already-decoded structure. A JSON document with
  the same structure is equally valid input — the format is the structure,
  not the serialization — but `.yaml` is the on-disk convention.

## 3. Schema identity and versioning

Every fixture carries an explicit format identifier:

```yaml
format: benchmark-case/v1
```

- `format` is `benchmark-case/v<major>`. This document defines `v1`.
- A reader implements a **fixed set** of major versions. Encountering any
  other value — absent, malformed, or a version it does not implement — is
  a hard rejection (§11). A reader MUST NOT parse an unrecognized version
  under another version's rules, "best-effort" it, or downgrade it.
  **Fail closed.**
- `format` is validated **before any other field is read**, so an old case
  is never reinterpreted under new rules.
- A breaking change to the meaning or requiredness of any field increments
  `<major>` and leaves existing `benchmark-case/v1` cases readable only by
  a `v1` reader. Additive, backward-compatible clarifications may be made
  within `v1` only if every previously valid `v1` fixture stays valid and
  its meaning is unchanged.

## 4. Top-level fields

| Key | Required | Type | Purpose |
|---|---|---|---|
| `format` | yes | string | Schema identity and version (§3). |
| `id` | yes | string | Stable case identity (§5). |
| `title` | yes | string | One-line human summary of the case. |
| `input` | yes | mapping | The benchmark input under review (§6). |
| `expected` | yes | mapping | The expected review outcome (§7–§9). |
| `metadata` | no | mapping | Optional, closed-key annotations (§10). |

No other top-level key is permitted.

## 5. Case identity

`id` is a lowercase kebab-case slug (`^[a-z0-9]+(?:-[a-z0-9]+)*$`), unique
within the corpus.

- It is the **stable join key**: a runner (#52) keys per-case results on
  it, and regression reporting (#53) refers to a case by it across runs.
- It is **immutable once assigned**. Renaming a case's `id` creates a new
  case and orphans its history; a case whose input or expectations change
  materially SHOULD get a new `id` rather than silently redefining an old
  one.
- Each expected finding additionally carries its own within-case `key`
  (§8), so a specific expectation is addressable as `(<id>, <key>)`.

## 6. Benchmark input (`input`)

`input` is a mapping. It MUST contain **exactly one** of:

| Key | Type | Meaning |
|---|---|---|
| `patch` | string | A self-contained unified diff (`git apply`-compatible), with enough context lines to be reviewed on its own. |
| `repo_ref` | mapping | A reference to real external state (§6.2). |

### 6.1 Inline patch (`patch`)

- `patch` is the full unified diff for the case.
- `base` (optional) is a mapping of repo-relative POSIX path → pre-image
  file contents, giving a runner the minimal tree the patch applies onto
  when diff context alone is insufficient. `base` is only valid alongside
  `patch`.

### 6.2 Repository reference (`repo_ref`)

A mapping with:

- `repo` — `owner/name` (required).
- exactly one of `pr` (positive integer) or `commit` (non-empty string
  SHA/ref).
- `base` (optional) — a **non-empty string** branch/ref the delta is taken
  against, when it is not the referenced repo's default. A present-but-empty
  or non-string `base` is rejected, matching the optional-string convention
  used everywhere else in this contract.

`repo_ref` names *what* to review. Whether a runner supports patch inputs,
reference inputs, or both first is #52's decision; `v1` fixes the shape of
both so the corpus is not blocked on that choice.

### 6.3 Review context (`input.context`)

Optional free-form string passed to the reviewer as review context
(requirements, ticket text, an ADR excerpt), mirroring
[`../../shared/policies/review-context.md`](../../shared/policies/review-context.md).
Present only for cases that deliberately test context-aware review.

## 7. Expected outcome (`expected`)

`expected` is a mapping with:

| Key | Required | Type | Purpose |
|---|---|---|---|
| `findings` | yes | list | Expected findings (§8). MAY be empty — an empty list is the correct shape for a no-op / clean case. |
| `findings_completeness` | no | enum | `exhaustive` (default) or `at-least` (§9). |
| `decision` | no | enum | `clean` or `changes-required`. |

`decision` is **derivable** from the required findings' severities and is
therefore optional. When present it is an explicit cross-check and MUST be
consistent with the mechanical derivation in
[`../../shared/policies/severity.md`](../../shared/policies/severity.md): a
case has `changes-required` exactly when at least one **required** finding
(§8) can only be satisfied at `P0`/`P1`; otherwise `clean`. Optional
findings never affect it. An inconsistent `decision` is a rejection (§11).

## 8. Expected finding specification

Each entry in `expected.findings` is either a **single expected finding**
or an **`any_of` group**. Both kinds of entry carry:

| Field | Required | Meaning |
|---|---|---|
| `key` | yes | Within-case kebab-case slug, unique across the case (including `any_of` members). Immutable, like `id` (§5). |
| `match` | no | `required` (default) or `optional` (§9). **Entry-level only** — an `any_of` member is not itself an entry and does not carry `match` (§8.4). |

### 8.1 Single expected finding

Additional fields:

| Field | Required | Meaning |
|---|---|---|
| `severity` | yes | `P0`/`P1`/`P2`, **or** a list of ≥ 2 distinct such values to permit severity variance (§9). |
| `location` | yes | Structured expected location (§8.3). |
| `claim` | yes | A short normalized cause → faulty-behavior sentence (the `behavioral_claim` shape of [`../findings/finding-matching-strategy.md`](../findings/finding-matching-strategy.md) §2). Documentation and a future-matcher target; **not** string-equality matched in `v1`. |
| `defect_kind` | no | Narrow defect-class slug (e.g. `sql-injection`). Concrete purpose: category-level slicing for #41 / profile fixtures #47. |
| `alternatives` | no | Non-empty list of acceptable **restatements of this same defect** (§8.2). |

### 8.2 `alternatives` — one defect, several acceptable descriptions/locations

Each `alternatives` entry is a partial spec narrowing at least one of
`location`, `claim`, `defect_kind` — **same sub-schemas and validation as
the primary** (a `location` follows §8.3; a `defect_kind` follows the same
kebab-slug rule as §8.1); every field is optional but the entry as a whole
must narrow at least one. The expectation is satisfied when a reviewer
finding matches the **primary spec or any one alternative**. `alternatives`
does **not** make the finding optional — for a `required` entry, one of
{primary, …alternatives} must still be reported — and an alternative never
carries its own `match` (§8.4).

### 8.3 `location` sub-schema

| Field | Required | Meaning |
|---|---|---|
| `location_intent` | yes | Closed enum `line` / `symbol` / `file` / `cross-file` / `repository` (§1). |
| `path` | yes unless `location_intent` is `repository` | Repo-relative POSIX path. |
| `symbol` | no | Enclosing qualified symbol, when known. |
| `anchor` | no | A short verbatim substring of the post-image at/near the defect site. This is the measurable hook: a later benchmark expected-vs-produced matcher (§13) can check that a reviewer's reported location resolves to code containing `anchor`, **without** this contract implementing matching. |
| `lines` | no | `{ start, end }` (1-based, `start ≤ end`) in the **post-image**. **Advisory only** — never the binding identity, because line numbers move (see [`../findings/finding-identity-requirements.md`](../findings/finding-identity-requirements.md) §4.3). |

### 8.4 `any_of` group — genuinely alternative acceptable findings

```yaml
- key: <group-key>
  match: required        # or optional
  any_of:
    - { key: …, severity: …, location: …, claim: … }
    - { key: …, severity: …, location: …, claim: … }
```

An `any_of` group holds ≥ 2 member specs, each a full single expected
finding (§8.1) with its own `key` and `severity`. The group is satisfied
when a reviewer finding matches **exactly one** member. Members may
legitimately differ in defect, location, `defect_kind`, and severity —
this is for cases where two *different* findings are each a correct read of
the same code. `any_of` groups do not nest, and a group carries its
members rather than its own `severity`/`location`/`claim`.

`match` is set **once, on the group entry**, and governs the whole group
(`required` — one member must be reported; `optional` — reporting one
member is not a false positive and reporting none is not a miss). An
individual `any_of` member **does not carry its own `match`**: members are
mutually acceptable defect outcomes, not independently opt-in/opt-out
findings. A member's `defect_kind` is validated exactly as a primary
spec's (§8.1) — same slug rule, no separate vocabulary. This mirrors
`alternatives` (§8.2), which are likewise governed by their containing
entry's `match` and never carry one of their own.

## 9. Representing acceptable variance

Variance is expressed **only** through the four typed constructs below.
There is **no free-text escape hatch** — no "notes", no prose "the
reviewer might also say…". If a form of acceptable variance cannot be
expressed with these constructs, that is a gap to close in a future
`format` version, not a reason to add unstructured text.

| # | Situation | Construct | A reviewer output is correct when… |
|---|---|---|---|
| 1 | One **required** defect, multiple acceptable descriptions/locations | a single entry with `alternatives` (§8.2) | it reports a finding matching the primary spec **or** any alternative — exactly once. |
| 2 | Genuinely **alternative** acceptable findings (different defects, any one acceptable) | an `any_of` group (§8.4) | it reports a finding matching **exactly one** member. |
| 3 | **Optional** finding | `match: optional` on the entry (single or group) | reporting it (matching the spec) is not a false positive; **not** reporting it is not a miss. |
| 4 | **Severity variance** explicitly permitted | `severity` as a list of ≥ 2 distinct values | its severity for that finding is **any one** listed value. A scalar `severity` means that exact value only. |

These compose: an `any_of` member may itself carry a `severity` list; an
`optional` entry may carry `alternatives` and/or a `severity` list.

**What keeps arbitrary output from counting as correct:**

- `findings_completeness: exhaustive` (**default**) — the union of {all
  `required` entries, all `optional` entries, every `alternatives` spec,
  every `any_of` member} is the **complete** set of acceptable findings.
  Any reviewer finding outside that union is an **unexpected finding**.
- `findings_completeness: at-least` — unexpected findings are tolerated
  (for inherently noisy real-`repo_ref` cases), but every `required` entry
  must still be satisfied. This is the **only** knob that loosens
  exhaustiveness, it is explicit per case, and it never downgrades a
  `required` entry to optional.

Classifying a reviewer finding as matching a given spec, and turning
"unexpected finding" / "missed required finding" into a score, are the
runner's and #41's job — not the fixture's.

## 10. Optional metadata (`metadata`)

`metadata` is a **closed** mapping; every key has a concrete downstream
purpose. Unknown keys are rejected (§11).

| Key | Type | Concrete purpose |
|---|---|---|
| `source` | string | Provenance — `crafted`, or a URL to the real PR/commit a case was derived from. Corpus auditing (#51). |
| `tags` | list | Subset of `correctness` / `security` / `quality` / `no-op` / `regression` / `concurrency` / `performance`, no duplicates. Category slices for #41 and profile/risky fixtures (#47/#48). |
| `rationale` | string | 1–3 sentences on why this case earns a corpus slot. Feeds #51's case-selection rationale record. |

No field for scoring weights, pass/fail thresholds, retrieval cutoffs,
runner configuration, timing, or model identity — those are out of scope
(§13) and MUST NOT be added to `metadata` to smuggle them in.

## 11. Fail-closed validation

A conforming validator **rejects the whole fixture** (no partial
acceptance, no coercion) on any violation of this contract. Each rejection
is a hard error. The cases below are the **representative** set — a
validator also enforces the other constraints stated throughout this
document (for example the non-empty requirement on `alternatives`,
`metadata.tags`, and every optional string such as `location.symbol`,
`location.anchor`, and `input.context`; the `{ start, end }`-only shape of
`lines`; and the type rules for `repo_ref` members). Those sections remain
authoritative; this list is not exhaustive.

1. `format` is absent, not a string, or not an implemented
   `benchmark-case/v<major>` — checked first, before any other field.
2. The top level is not a mapping, or any mapping in the fixture
   (`input`, `repo_ref`, `expected`, a finding, a `location`, an
   `alternatives` entry, `metadata`) contains an unknown key.
3. A required field is missing or has the wrong type: `id`, `title`,
   `input`, `expected`; per finding `key`, `claim`, `location`, and
   `severity` (or, for a group, `any_of`); per `location` its
   `location_intent`, and `path` unless `location_intent` is `repository`.
4. `input` does not contain exactly one of `patch` / `repo_ref`; or
   `base` appears without `patch`; or `repo_ref` lacks `repo`, does not
   have exactly one of `pr` / `commit`, or carries a present-but-empty or
   non-string `base`.
5. `id`, a finding `key`, or a `defect_kind` is not a kebab-case slug; or
   two findings (including `any_of` members) share a `key`; or a `key` is
   used both as a standalone entry and inside an `any_of` group.
6. A `severity` value is outside `{P0, P1, P2}`; or a `severity` list has
   fewer than 2 entries, a duplicate, or a non-severity value.
7. `location_intent` is outside the closed enum; or `lines` is present
   without integer `start`/`end` satisfying `1 ≤ start ≤ end`.
8. `findings_completeness` is neither `exhaustive` nor `at-least`; or
   `expected.findings` is not a list; or `decision` is present and neither
   `clean` nor `changes-required`.
9. An `any_of` group has fewer than 2 members, nests another group, or
   carries its own `severity` / `location` / `claim`.
10. `metadata` carries an unknown key, an unknown or duplicated `tags`
    value, or an empty `tags` list.
11. `decision` is present and contradicts the decision mechanically
    derived from the required findings' severities (§7).

A validator that implements `v1` and is handed a `v2` fixture rejects it
under rule 1 — it never falls back to `v1` parsing.

## 12. Worked example

[`examples/example-case.yaml`](examples/example-case.yaml) is a complete,
validated `benchmark-case/v1` fixture. It is a crafted single-file Python
patch that introduces a SQL-injection sink and a user-controlled
filesystem path and adds no tests. It exercises every §9 construct:

- `sqli-user-lookup` — a **required** `P0` finding with an `alternatives`
  entry: the same injection is acceptable reported on the f-string or on
  the `conn.execute(query)` call (variance #1).
- `unsafe-export-path` — an **`any_of` group**: the path handling is
  acceptable reported either as `path-traversal` (`P0`) or as
  `missing-input-validation` (`P1`) — different defects, either correct
  (variance #2).
- `missing-security-test` — an **optional** finding whose severity may
  acceptably be `P1` or `P2` (variance #3 + #4 composed).
- `findings_completeness: exhaustive` and an explicit
  `decision: changes-required` consistent with the two blocking required
  entries.

The automated check that this example parses and validates, plus the
negative cases for the §11 rejection rules, lives in
[`../../tests/unit/test_benchmark_fixture.py`](../../tests/unit/test_benchmark_fixture.py),
exercising the test-only reference validator
[`../../tests/reference/benchmark_fixture.py`](../../tests/reference/benchmark_fixture.py)
(not runtime logic, not packaged).

## 13. Scope boundaries

| Not defined here | Owner |
|---|---|
| The benchmark corpus and case-selection rationale record | [#51](https://github.com/amirbena/code-review-skill/issues/51) |
| The runner: executing the review path per case, capturing produced findings/severities, comparing them against a fixture's expectations (the per-case expected-vs-produced comparison structure), emitting per-case results, single-case vs. whole-corpus runs | [#52](https://github.com/amirbena/code-review-skill/issues/52) |
| Regression reporting across runs (seeded-regression detection) | [#53](https://github.com/amirbena/code-review-skill/issues/53) |
| The expected-vs-produced **match relation** itself — deciding when a produced finding satisfies an expected spec, an `alternatives` restatement, or an `any_of` member — together with false-positive / false-negative accounting, precision/recall, retrieval thresholds, and aggregate quality metrics | [#41](https://github.com/amirbena/code-review-skill/issues/41) |
| Profile-specific and risky-change fixture selection | [#47](https://github.com/amirbena/code-review-skill/issues/47) / [#48](https://github.com/amirbena/code-review-skill/issues/48) |
| The P0/P1/P2 definitions and the decision derivation | [`../../shared/policies/severity.md`](../../shared/policies/severity.md) |
| The finding field shape | [`../../shared/templates/finding.md`](../../shared/templates/finding.md) |

**On the benchmark matcher.** No current roadmap issue is *solely* a
"benchmark expected-vs-produced matcher": the capability is split above —
#52 owns capturing produced findings and the per-case comparison
structure, #41 owns the match relation and the FP/FN quality metrics that
make it measurable. A dedicated matcher component is therefore **not
separately assigned**, and epic
[#40](https://github.com/amirbena/code-review-skill/issues/40) would add a
child issue for one only if #52 and #41 together prove insufficient — none
is required today. GitHub Issue
[#59](https://github.com/amirbena/code-review-skill/issues/59) is **closed
stateful-re-review finding-*identity* research** and is **not** an owner
here; [`../findings/finding-matching-strategy.md`](../findings/finding-matching-strategy.md)
is referenced by this contract only as reusable prior-art vocabulary
(`MATCH` / `NO MATCH` / `AMBIGUOUS`) and matching discipline
(defect-continuity + site-continuity), never as benchmark roadmap
ownership.

## Status and canonical home

**This document is the authoritative contract** for the benchmark fixture
format until a later issue installs an equivalent schema alongside the
runner (#52) or in another canonical home. At that point this document
becomes the design record: it MUST link to the canonical schema and MUST
NOT keep evolving the format independently — exactly as
[`../findings/finding-identity-requirements.md`](../findings/finding-identity-requirements.md)
describes for its own eventual installation.

The test-only reference validator
[`../../tests/reference/benchmark_fixture.py`](../../tests/reference/benchmark_fixture.py)
mirrors this document for regression coverage. It is not packaged and is
not the runner.
