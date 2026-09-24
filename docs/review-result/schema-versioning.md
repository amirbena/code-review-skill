# Review Result — Schema Versioning Policy

Repository-development design record for
**[#68](https://github.com/amirbena/code-review-skill/issues/68)**: how the
[review result schema](review-result.schema.json)
([#67](https://github.com/amirbena/code-review-skill/issues/67)) evolves
without silently breaking consumers. Not packaged into either Skill archive.

## 1. The version field

`schema_version` is a **required** top-level string,
`MAJOR.MINOR.PATCH` (three non-negative integers, no leading zeros, no
prerelease or build suffix). The schema pins it with `const`, so each
published schema revision accepts exactly the version it declares, and the
schema's `required` list includes it. The current value is `1.0.0`; the
schema file is the only place the current value is stated.

## 2. Compatible vs breaking changes

The rules are about **producers and consumers of the document**, judged
against a consumer that follows section 3.

| Change | Class | Bump |
| --- | --- | --- |
| Wording, `$comment`, or documentation fix; tightening a description with no change to accepted documents | Compatible | `PATCH` |
| Adding an **optional** property to any object | Compatible | `MINOR` |
| Adding a value to a closed enum a consumer only *reads* (for example a new `capability`) | Compatible | `MINOR` |
| Adding a **required** property | Breaking | `MAJOR` |
| Removing or renaming a property or enum value | Breaking | `MAJOR` |
| Changing a property's type, format, or nullability | Breaking | `MAJOR` |
| Changing the meaning of an existing field or value (including a change in its canonical owner that alters what the value means) | Breaking | `MAJOR` |
| Adding a value to an enum that drives a consumer's decision (`decision.outcome`, `severity`, `coverage`) | Breaking | `MAJOR` |
| Loosening a constraint on a field consumers read (for example widening a pattern or format) | Breaking | `MAJOR` |
| Loosening a constraint on a field consumers do not interpret | Compatible | `MINOR` |
| Tightening a constraint on existing fields | Breaking | `MAJOR` |

Because the schema sets `additionalProperties: false`
([`review-result-model.md`](review-result-model.md) section 2), an added
property is only "compatible" for a consumer that tolerates unknown keys
inside a version it does not know (section 3). A document is always
validated against the schema of **its own** `schema_version`, never a
newer one's.

A change to the meaning of a field is owned by that field's canonical
source, not by this policy: when a canonical owner changes a concept in a
way that alters what a serialized value means, that is a `MAJOR` bump here.

## 3. Consumer guidance

A consumer declares the `MAJOR` version it supports and the highest `MINOR`
it has been written against.

| Document's `schema_version` | Consumer behavior |
| --- | --- |
| Missing, not a string, or not `MAJOR.MINOR.PATCH` | **Fail closed**: reject the document as invalid. |
| Same `MAJOR`, `MINOR` ≤ supported | Accept and validate against that version's schema. |
| Same `MAJOR`, `MINOR` > supported | Accept **only** the fields it understands; ignore unknown keys and unknown values of read-only enums; do not fail. It must not treat the result as fully understood for anything it does not read. |
| Different `MAJOR` (higher or lower) | **Fail closed**: refuse to interpret the document and surface an unsupported-version error. Never guess, never partially interpret. |

`PATCH` never affects acceptance. Failing closed means no findings, decision,
or counts are consumed from an unsupported document — an unreadable result is
never rendered as a clean review. This mirrors the *spirit* of the
packaging manifest's fail-closed check (section 6) without sharing its
implementation.

The reference implementation of this table is
[`tests/reference/review/review_result_version.py`](../../tests/reference/review/review_result_version.py).

## 4. Deprecation and rollout

1. **Announce** a deprecation in the `MINOR` (or `MAJOR`) release that
   introduces the replacement, in the model record and release notes. The
   deprecated field stays valid and keeps its meaning.
2. **Overlap**: a deprecated field or value is removed only in the next
   `MAJOR`, and only after at least one full `MINOR` release in which both
   old and new forms were valid.
3. **Removal / any breaking change** ships as a new `MAJOR`, with an updated
   schema, example carrying the new version, and a migration note in this
   record.
4. **Producers** emit exactly one version per document — the highest they
   were written for. The repository does not maintain simultaneous emission
   of several versions.
5. **Rollout order**: consumers gain support for a new version before
   producers begin emitting it.

## 5. Not in scope

- **Multi-version runtime translation.** Nothing here upgrades or downgrades
  a document between versions; a consumer supports a `MAJOR` or refuses it.
- **A shared versioning architecture.** Review-result versioning is its own
  domain and is not coupled to any other artifact's version field.

## 6. Prior art (cited, not merged)

[`scripts/packaging/package_manifest.py`](../../scripts/packaging/package_manifest.py)
carries an integer `schema_version` in the packaging-manifest domain and
rejects an unsupported value. That precedent informed the fail-closed
stance in section 3. The two domains stay independent: different value
shape (integer vs. `MAJOR.MINOR.PATCH`), different rules, no shared code,
and a change to either version never implies a change to the other.
