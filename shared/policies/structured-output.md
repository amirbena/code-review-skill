# Policy — Structured Review Result (opt-in)

An opt-in, machine-readable rendering of the review that has **already**
been finalized. It is one more projection of the same findings, coverage,
and mechanical Decision the human report renders — never a second review,
never a source of a finding, severity, or decision of its own. Currently
consumed by `local-code-review` only.

## Activation

The option `structured_review_result` (boolean, default `false`) is
normalized per [`invocation-options.md`](invocation-options.md). When it
resolves `false`, this policy is not loaded and the report is exactly the
default report. When it resolves `true`, the Skill renders the human report
**unchanged** and then appends the result below. The option is
output-only: scope, inspection, evidence, findings, severity,
deduplication, coverage, and the Decision are identical on and off.

## Placement and form

After the report's trailing Review Metadata / Review scope contract,
append exactly one section:

```text
### Structured Review Result
```

followed by exactly one fenced `json` block holding one JSON object — no
comments, no trailing commas, no second document. The block is generated
from the finalized review, after the verdict-consistency check; if that
check withheld the report, or the review is ungraded
(`JIRA CONTEXT UNRESOLVED`), emit no block and state one line
`Structured review result not emitted: <reason>`. Never publish, stream,
or write it to a file: it is returned inside the same single report.

## Document shape

Unknown keys are forbidden at every object. Required keys are always
present; an optional finding field with no value is **omitted**, never
`null`.

| Key | Value |
| --- | --- |
| `schema_version` | the string `"1.0.0"` |
| `skill` | `"local-code-review"` |
| `reviewed_state` | object, below |
| `coverage` | `"complete"` or `"incomplete"` — the report's Coverage |
| `decision` | `{ "derived", "outcome" }`, below |
| `counts` | `{ "p0", "p1", "p2" }` — integer tally of `findings` by severity |
| `summary` | the report's "What changed" prose, non-empty |
| `findings` | every finding in report order, **including P2 on a clean review**; `[]` when none |

`reviewed_state` — all keys required:

| Key | Value |
| --- | --- |
| `repository` | `owner/name` from the upstream remote URL when one exists, otherwise the repository directory name |
| `base_branch` | the review base branch (Review Metadata) |
| `base_sha` | full lowercase hex SHA of the review base, or `null` |
| `merge_base_sha` | full hex SHA of the merge base of base and HEAD, or `null` |
| `reviewed_head_sha` | Local HEAD's full hex SHA **only when the whole reviewed target is committed** (staged, unstaged, and untracked categories all empty); otherwise `null`, because a SHA does not identify uncommitted content and must not claim it does |
| `reviewer_identity` | `null` unless the runtime established a reviewer identity |
| `completeness` | `"full"` |
| `prior_reviewed_sha` | `null` — a stateless review never reads prior state |

`decision.derived` is `"blocking"` when any P0/P1 is present, else
`"clean"` ([`severity.md`](severity.md), "Decision derivation
(mechanical)"). `decision.outcome` equals `derived`, except
`"incomplete"` when coverage is `incomplete`
([`review-stopping-criteria.md`](review-stopping-criteria.md), "Labeling").
Rendered labels map `clean` → `REVIEW CLEAN`, `blocking` → `CHANGES
REQUIRED`, `incomplete` → `REVIEW INCOMPLETE`; a serialized `clean` never
means "no findings".

## Finding object

Serialized from the finalized finding in
[`../templates/finding.md`](../templates/finding.md), one key per field,
`snake_case`:

| Key | Required | Value |
| --- | --- | --- |
| `id` | yes | the review-local `F<n>` label |
| `severity` | yes | `"P0"`, `"P1"`, or `"P2"` |
| `title`, `evidence`, `impact`, `fix` | yes | the finding's text, non-empty |
| `location` | yes | the canonical location **without** the trailing source-category or unresolved-fix annotation |
| `fix_location_resolved` | yes | `false` exactly when the unresolved-fix annotation applies, else `true` |
| `runtime_validation` | yes | `"reasoned"` (default), `"runtime-confirmed"`, or `"attempted-inconclusive"` |
| `confidence` | yes | `"credible"` (default), `"confirmed"`, `"runtime-validation-unavailable"`, `"external-contract-unvalidated"`, or `"insufficient-context"` |
| `identity` | yes | `{ "stable_id", "matching_eligible" }`, below |
| `evidence_location`, `follow_up`, `details`, `capability` | no | only when populated (`details` regardless of the detail-presentation option) |
| `affected_locations` | no | array of `{ "location", "note" }`, at least two, only on a consolidated finding |
| `contextual_evidence` | no | array of non-empty strings, only when provenance exists |
| `defect_kind` | no | lowercase kebab-case slug, only when a narrow class applies |

The implementation prompt and the source-category annotation are
rendering-only and are never serialized. `confidence` must not contradict
`runtime_validation` (a `runtime-confirmed` finding is `confirmed`).

## Finding identity

`identity.stable_id` is `fid_v1_` followed by the first 32 lowercase hex
characters of the SHA-256 of a canonical serialization of the finding's
descriptor. Compute the digest with a shell hashing command
(`shasum -a 256` or equivalent); never write a value you did not compute.
The construction is a pure function of the inputs below — never of
severity, the `F<n>` ordinal, the HEAD SHA, discovery order, or other
findings.

**Tokenizer.** Over a source fragment: outside string literals delete
`/* … */` and `#`-to-end-of-line comments (`//` is **not** a comment);
delete ASCII control characters; collapse whitespace runs. Emit, in order:
identifiers (`[A-Za-z_][A-Za-z0-9_]*`), numbers (`\d+(\.\d+)?`), quoted
string literals verbatim, maximal runs of operator characters
(`- + * / % = ! < > & | ^ ~ .`), and single brackets. Never emit `,` or
`;`. Preserve order, multiplicity, and case.

**Descriptor fields**, in this order. `ABSENT` = the facet legitimately
does not apply; `UNCLASSIFIABLE` = present but not reducible without
guessing. Never guess a value.

| Field | Construction |
| --- | --- |
| `repository` | `reviewed_state.repository` |
| `location_intent` | `line`, `symbol`, `file`, `cross_file`, or `repository` by the canonical `location`'s precision; none fits → `UNCLASSIFIABLE` |
| `path` | repository-relative, `/` separators, no leading `./` or `/`, no `.`/`..` segment; `ABSENT` for `cross_file`/`repository` or no usable path |
| `symbol` | the enclosing qualified named definition (chain joined with `.`) read from the reviewed source; `ABSENT` when it cannot be named |
| `construct` | `statement`, `declaration`, `call`, `expression`, `config_key`, `section`, or `block`; none fits → `UNCLASSIFIABLE` |
| `anchor_tokens` | tokenizer over the smallest source/config fragment that demonstrates the defect, at the reviewed revision; empty list when there is none |
| `mechanism_key` | tokenizer over the source fragment naming the unsafe operation or violated invariant; no fragment → `UNCLASSIFIABLE` |
| `cause_key` / `behavior_key` | the finding's concise cause → faulty-behavior claim (no impact/fix/severity), case-folded and whitespace-collapsed, split at its first connective among ` so `, ` causing `, ` resulting in `, ` leads to `, ` which causes `, ` therefore `, ` -> `, ` → `; tokenizer over the left / right clause after trimming whitespace and trailing sentence punctuation. No connective or an empty side → `UNCLASSIFIABLE` |

**Serialization.** A string `s` → `len(s)` `\x1f` `s`; a token list `t` →
`len(t)` `\x1f` the tokens joined by `\x1f`; `ABSENT` → `\x00A`;
`UNCLASSIFIABLE` → `\x00U`. Emit each field as `<name>\x1d<encoded>`,
join the fields with `\x1e`, and prefix the whole with `v1\x1e`.

**`matching_eligible`** is `false` when any holds, else `true`: repository
unresolvable; `location_intent` is `UNCLASSIFIABLE`; `anchor_tokens` is
empty **and** `mechanism_key` is `UNCLASSIFIABLE`; none of `symbol`,
`mechanism_key`, `cause_key`, `behavior_key` is classified; or the
reviewed source needed for the anchor or mechanism could not be read. A
non-eligible finding still gets its deterministic `stable_id`. When in
doubt, `false`.

## Example

One blocking review of an uncommitted target (so `reviewed_head_sha` is
`null`), with one finding:

```json
{
  "schema_version": "1.0.0",
  "skill": "local-code-review",
  "reviewed_state": {
    "repository": "acme/payments",
    "base_branch": "main",
    "base_sha": "3f9c1e2a7b4d5c60918273645a1b2c3d4e5f6071",
    "merge_base_sha": "3f9c1e2a7b4d5c60918273645a1b2c3d4e5f6071",
    "reviewed_head_sha": null,
    "reviewer_identity": null,
    "completeness": "full",
    "prior_reviewed_sha": null
  },
  "coverage": "complete",
  "decision": { "derived": "blocking", "outcome": "blocking" },
  "counts": { "p0": 0, "p1": 1, "p2": 0 },
  "summary": "Adds bounded retries around the charge call.",
  "findings": [
    {
      "id": "F1",
      "severity": "P1",
      "title": "Retry loop reports a timed-out charge as successful",
      "location": "src/payments/retry.py:88",
      "fix_location_resolved": true,
      "evidence": "`charge_with_retry` falls through to `return ChargeResult.ok()` after every attempt times out.",
      "impact": "A charge that never completed is recorded as paid.",
      "fix": "Return a failure result when every attempt timed out.",
      "runtime_validation": "reasoned",
      "confidence": "credible",
      "identity": {
        "stable_id": "fid_v1_2c7a0d6b2c80a885a1752c05f15d70c0",
        "matching_eligible": true
      }
    }
  ]
}
```

The `stable_id` above is illustrative; a real value is always computed as
described in "Finding identity".

## Non-goals and ownership

- No new review semantics: every value is owned by the policy or template
  named in this file; this file owns only the serialization and its
  opt-in activation.
- No GitHub publication of the result (`github-pr-review` does not consume
  this policy), no persistence, and no cross-review lifecycle state.
- No change to the default report: with the option off, nothing here
  applies.
