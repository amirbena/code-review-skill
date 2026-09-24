# Review Result — Schema Model

Repository-development design record for
**[#67](https://github.com/amirbena/code-review-skill/issues/67)**: the
first machine-readable serialization of a review's output, expressed as one
JSON Schema plus one validating example.

The result is a **projection of semantics that already have canonical
owners** — finding fields, severity → decision derivation, reviewed-SHA
state, and finding identity. This record fixes the *representation* and
names each owner; it defines no finding, decision, or identity rule of its
own. Where this record and an owner appear to differ, the owner wins and
this record is the bug.

Not packaged: no packaged Skill resource depends on this record, the
schema, or the example (see [`../../AGENTS.md`](../../AGENTS.md), "Packaged
Skills are independent of repository-level instructions").
`github-pr-review` emits one on explicit request; local emission is pending — see section 7.

## 1. Files

| File | Role |
| --- | --- |
| [`review-result.schema.json`](review-result.schema.json) | The one source of truth for the document's shape (JSON Schema draft-07): field names, types, enums, required-ness. |
| [`examples/review-result.example.json`](examples/review-result.example.json) | One blocking review that validates against the schema and is consistent with the owners below. |
| [`../../tests/reference/review/review_result.py`](../../tests/reference/review/review_result.py) | Test-only validator: shape against the schema, then cross-field consistency delegated to the owners' reference models. |

## 2. Representation decisions

The choices below set precedent for every later consumer of review output.
Each is stated once here; the schema is their executable form.

| Decision | Choice | Why |
| --- | --- | --- |
| **Schema dialect** | JSON Schema draft-07, no external validator dependency. | Matches [`../review-telemetry/`](../review-telemetry/README.md); the repository validates with a small in-tree subset. |
| **Field naming** | `snake_case`, derived from the canonical label (`evidence location` → `evidence_location`, `follow-up` → `follow_up`). | Matches the existing schemas and keeps each key traceable to its `finding.md` label. |
| **Enum representation** | Strings, never numeric codes. Values that already have a canonical spelling keep it verbatim: severity `P0`/`P1`/`P2`, `confidence`, `runtime_validation`, `completeness`, `coverage`. | A serialized value should read as the concept it names, and canonical spellings cannot drift from their owners. |
| **Decision values** | `derived` ∈ {`clean`, `blocking`}; `outcome` ∈ {`clean`, `blocking`, `incomplete`}. | [`severity.md`](../../shared/policies/severity.md) names the two derived results Skill-neutrally ("clean/approved", "blocking"); the Skill labels are renderings (section 4). No canonical machine code existed. |
| **Structure** | One document; `findings` is an inline array of self-contained finding objects; review-level facts sit beside it. | A result is consumed whole; references between arrays would add a join with no benefit at review scale. |
| **Absent vs `null`** | Required keys are always present. A value that is legitimately unknown or not applicable at *review* level is `null` (`prior_reviewed_sha` at a chain root, `reviewed_head_sha` with no committed head). An optional *finding* field with no value is **omitted**, never `null`. A field with a canonical default (`confidence`, `runtime_validation`, `fix_location_resolved`) is always present and carries the default explicitly. | Explicit state facts cannot be mistaken for "not recorded"; optional prose fields stay out of the way; a canonical default is never inferred from a missing key. |
| **Unknown keys** | Rejected (`additionalProperties: false`) at every object. | An added field is a schema change, which is versioned under [`schema-versioning.md`](schema-versioning.md). |

## 3. Field → canonical owner

The schema carries the same pointer in each field's `$comment`; a test keeps
those pointers resolving.

| Result field(s) | Canonical owner |
| --- | --- |
| `findings[].id`, `severity`, `title`, `location`, `evidence`, `impact`, `fix`, `follow_up`, `details`, `evidence_location`, `affected_locations`, `contextual_evidence`, `capability`, `defect_kind` | [`shared/templates/finding.md`](../../shared/templates/finding.md) — "Fields" and "Optional and surface-specific fields" |
| `findings[].fix_location_resolved` | [`shared/templates/finding.md`](../../shared/templates/finding.md) — "Fix/action location, evidence location, publication" ("No silent promotion"). `finding.md` defines this state only as the trailing `location` annotation `_(evidence location; fix/action location unresolved)_`; the key name is introduced by this schema (matching the test-only `finding_contract.py`) as that annotation's serialization. `false` means the annotation applies. |
| `findings[].severity` meaning; `decision.derived`; `counts` | [`shared/policies/severity.md`](../../shared/policies/severity.md) — P0/P1/P2 and "Decision derivation (mechanical)" |
| `findings[].evidence` bar | [`shared/policies/evidence.md`](../../shared/policies/evidence.md) |
| `findings[].fix` guidance | [`shared/policies/remediation-guidance.md`](../../shared/policies/remediation-guidance.md) |
| `findings[].runtime_validation` | [`shared/policies/runtime-validation.md`](../../shared/policies/runtime-validation.md) — "Targeted validation of a suspected finding" |
| `findings[].confidence` | [`../finding-confidence/finding-confidence-model.md`](../finding-confidence/finding-confidence-model.md) |
| `findings[].identity` | [`../findings/finding-stable-identity.md`](../findings/finding-stable-identity.md) (construction, effective identity, matching eligibility); matching in [`../findings/finding-matching-strategy.md`](../findings/finding-matching-strategy.md) |
| `reviewed_state.*` | [`../findings/reviewed-sha-state-contract.md`](../findings/reviewed-sha-state-contract.md) |
| `coverage`; `decision.outcome` | [`shared/policies/review-stopping-criteria.md`](../../shared/policies/review-stopping-criteria.md) — "Labeling" |
| `summary` | [`shared/templates/review-summary.md`](../../shared/templates/review-summary.md) — "What changed" |
| `skill` | [`skills/local-code-review/SKILL.md`](../../skills/local-code-review/SKILL.md), [`skills/github-pr-review/SKILL.md`](../../skills/github-pr-review/SKILL.md) |

Two naming notes. The issue text lists a `remediation` field; the canonical
finding contract has `impact` and `fix`, and `fix` is the field that carries
remediation guidance, so the result uses those two. And `id` is the
review-local label (`F1`); cross-review identity is `identity.stable_id`.

## 4. Decision codes

`decision.derived` is the single mechanical decision. `decision.outcome` is
what the review presents, and differs from it only when coverage is
`incomplete`.

| Machine value | Local rendering | GitHub rendering |
| --- | --- | --- |
| `clean` | `REVIEW CLEAN` | `Approve` |
| `blocking` | `CHANGES REQUIRED` | `Request Changes` |
| `incomplete` (outcome only) | `REVIEW INCOMPLETE` | `REVIEW INCOMPLETE` |

A serialized `clean` never means "no findings": P2 findings still appear in
`findings` (`severity.md`).

## 5. What the schema does not encode

The schema is shape only. These are checked by the test-only validator, each
delegating to the owner's reference model instead of restating the rule:

| Check | Delegates to |
| --- | --- |
| `counts` equals the tally of `findings` by severity | severity tally in `severity.md` |
| `decision.derived` equals the derivation over the findings | `tests/reference/review/decision_semantics.py` |
| `decision.outcome` equals `derived` unless coverage is `incomplete` | `tests/reference/review/review_stopping_criteria.py` |
| `confidence` does not contradict `runtime_validation` | `tests/reference/review/finding_confidence.py` |
| finding `id`s are unique within one review; `prior_reviewed_sha` never names the reviewed head | `finding.md` (`id`), reviewed-SHA contract section 5 |

`identity.stable_id` is deliberately **not** required to be unique within a
review: the identity contract mints non-matchable findings deterministically
and lets distinct findings that reduce to the same descriptor share a value
([`finding-stable-identity.md`](../findings/finding-stable-identity.md) §7,
[`finding-identity-requirements.md`](../findings/finding-identity-requirements.md)
§6 "No global-uniqueness claim"), so the result does not assert otherwise.

A drift test also pins each schema enum and the identity token format to the
same reference models, so a value cannot change in an owner without the
schema failing.

## 6. Deliberately not in this version

| Left out | Why |
| --- | --- |
| Finding lifecycle state (`OPEN` / `RESOLVED`, events) | Owned by [`finding-lifecycle-contract.md`](../findings/finding-lifecycle-contract.md); a per-review result carries identity, not cross-review state. |
| Always-on process classifications (change-risk depth, repository-expansion decisions, partitioning) | Not named by [#67](https://github.com/amirbena/code-review-skill/issues/67); a later addition is a versioned schema change. |
| Reviewed-state persistence fields (provenance marker, associated evidence reference) | They belong to a *written* record; the record may point at a result, the result does not embed its own storage metadata. |
| Non-graded outcomes other than `incomplete` (`JIRA CONTEXT UNRESOLVED`, `NO NEW DELTA`, passive reviews) | No machine code exists for them yet; adding one is a versioned extension. |
| Rendering-only finding fields (source annotation on `location`, implementation prompt) | Presentation, not result content (`finding.md`). |

## 7. Boundaries

| Concern | Owner |
| --- | --- |
| Versioning policy and compatibility rules for `schema_version` | [`schema-versioning.md`](schema-versioning.md) ([#68](https://github.com/amirbena/code-review-skill/issues/68)) |
| Skill wiring and runtime emission of a result | [#69](https://github.com/amirbena/code-review-skill/issues/69), [#70](https://github.com/amirbena/code-review-skill/issues/70) |
| Consumers of the result | [#71](https://github.com/amirbena/code-review-skill/issues/71) |
| Parent capability | [#44](https://github.com/amirbena/code-review-skill/issues/44) |

`github-pr-review` emits the result on explicit request, returned to the
caller only, with PR-specific field population owned by its
[`structured-output.md`](../../skills/github-pr-review/policies/structured-output.md)
([#70](https://github.com/amirbena/code-review-skill/issues/70)). Until
[#69](https://github.com/amirbena/code-review-skill/issues/69) lands,
`local-code-review` still produces only its existing Markdown output, and
[`finding.md`](../../shared/templates/finding.md)'s note that a
machine-readable renderer would be "another projection of the same fields"
is what this schema is the first instance of.
