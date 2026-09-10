# Contextual Evidence Model

Repository-development design record for **[#118](https://github.com/amirbena/code-review-skill/issues/118)**.
Not packaged; explanatory. It is the canonical home for the typed
contextual-evidence model and its authority / resolution rules — the packaged
[`shared/policies/review-context.md`](../../shared/policies/review-context.md),
[`shared/policies/review-evidence.md`](../../shared/policies/review-evidence.md),
and [`shared/templates/finding.md`](../../shared/templates/finding.md)
reference this document by name and do not restate its matrix or tables.
Two follow-on issues consume it without redefining it:
[#176](https://github.com/amirbena/code-review-skill/issues/176)
(requirement / acceptance-criteria coverage) and
[#178](https://github.com/amirbena/code-review-skill/issues/178) (unified
finding confidence / evidence-state field).

The test-only reference model is
[`../../tests/reference/context_evidence.py`](../../tests/reference/context_evidence.py);
its regression corpus and the worked examples below are exercised by
[`../../tests/unit/test_context_evidence.py`](../../tests/unit/test_context_evidence.py)
and [`../../tests/policy/test_context_evidence_docs.py`](../../tests/policy/test_context_evidence_docs.py).

## 1. Problem and goal

A reviewer can read a diff correctly and still reach the wrong conclusion
because it has no disciplined way to use *authoritative context*: the real
requirement, an accepted design decision, prior implementation feedback,
repository policy, or the knowledge that a risk pre-dates the reviewed
change. Caller-supplied context today is defined only as an input *shape*
(see [`review-context.md`](../../shared/policies/review-context.md), "Input
form"); nothing states how much authority a given piece of context carries or
how it should influence a finding.

The goal is **not** generic retrieval-augmented review or ingestion of
arbitrary organizational knowledge. It is to make review decisions traceable
to the specific evidence that justifies them, and to stop a low-authority
source (an informal chat message, say) from silently overriding an explicit
requirement or an approved design decision.

## 2. Where contextual evidence sits

[`review-context.md`](../../shared/policies/review-context.md) already names
four concepts: the **review target** (never widened), **review context**,
**repository context**, and **existing review evidence**.
*Contextual evidence* is a typing of the material that arrives as **review
context** and, where relevant, the authoritative parts of **existing review
evidence** — the requirement, decision, policy, feedback, or history a
finding can be attributed to. It never becomes a review target, never widens
one, and never overrides actual code on *what the code currently does* (the
code-first evidence hierarchy in
[`review-context.md`](../../shared/policies/review-context.md), "Evidence
hierarchy", is unchanged).

## 3. The typed evidence model

Every piece of contextual evidence a review uses is one of the types below.
Each is marked **authoritative** (it can establish what "correct" or "in
scope" means for the change, and a finding may rest on a violation of it) or
**informational** (it can focus attention, add background, or corroborate,
but cannot by itself establish a requirement, a decision, or a finding).

| Type | Authority | Definition | Entry criteria |
| --- | --- | --- | --- |
| `requirement` | authoritative | An explicit statement of what the change must accomplish — a ticket requirement, a written spec line, a stated constraint or invariant. | Supplied as review context and stated as a requirement, not as discussion or a suggestion. |
| `acceptance_criteria` | authoritative | Explicit pass/fail conditions the change is expected to satisfy. | Supplied as review context and phrased as pass/fail conditions. |
| `accepted_decision` | authoritative | A design decision that was actually agreed — an accepted ADR/HLD, a resolved design thread, an unambiguous resulting direction, or a direct maintainer conclusion. | Meets the "Settled decisions" bar in [`review-evidence.md`](../../shared/policies/review-evidence.md): explicit conclusion or accepted artifact, not one reviewer's opinion. |
| `repository_policy` | authoritative | A convention or invariant the *target repository itself* declares — its `AGENTS.md` / `CLAUDE.md` hierarchy, an in-repo policy the repository treats as canonical. | Discovered per [`repository-instructions.md`](../../shared/policies/repository-instructions.md); it is the target repo's own stated rule, not an external preference. |
| `implementation_feedback` | informational | Review comments, PR suggestions, or prior reviewer remarks about how the change should be done. | A comment or suggestion that has **not** been ratified into an `accepted_decision` (see §4). |
| `historical_context` | informational | Background on why code is shaped as it is, or what a prior change did — commit history, an older ticket, a past incident writeup. | Explanatory background, not a current requirement or decision. |
| `pre_existing_risk_note` | informational | A statement that a particular risk or defect already exists in the codebase independent of the reviewed change. | A concrete note about existing behavior; still subject to [`evidence.md`](../../shared/policies/evidence.md), "Findings beyond the changed lines". |
| `informal_discussion` | informational | Slack / chat / hallway-style discussion, exploratory back-and-forth, an unresolved suggestion, or one side of an unfinished disagreement. | Any discussion that has not reached an explicit, recorded conclusion. |

The set is closed. Material that does not fit a type is treated as
`informal_discussion` (the most conservative classification) until it does.

## 4. `implementation_feedback` is informational unless ratified

Review feedback, PR comments, and suggestions are **`implementation_feedback`
(informational)** and are **not** equivalent to an `accepted_decision`. They
become authoritative only when the repository carries explicit evidence the
feedback was accepted or ratified — an accepted ADR/HLD, a settled-decision
thread per [`review-evidence.md`](../../shared/policies/review-evidence.md),
"Settled decisions", or a direct maintainer conclusion. At that point the
**accepted artifact or decision is the authoritative evidence**, cited as an
`accepted_decision`; the feedback comment that prompted it is not promoted in
place. A reviewer never infers ratification from the feedback existing, from
it being upvoted, or from it being old.

## 5. Authority and trust rules

- **An informational source can never override an authoritative one.**
  `informal_discussion`, `implementation_feedback`, `historical_context`, and
  `pre_existing_risk_note` cannot override, narrow, or reinterpret an
  explicit `requirement`, `acceptance_criteria` entry, or `accepted_decision`.
  They may add context, corroborate, or motivate a closer look. Concretely:
  informal discussion must not silently override an explicit requirement or
  an approved design decision.
- **Newer explicit maintainer clarification supersedes stale earlier
  discussion.** A later, direct statement of intent from a maintainer wins
  over an older contradictory one; ordinary later discussion does not reopen
  a settled decision (see
  [`review-evidence.md`](../../shared/policies/review-evidence.md)). Such a
  direct maintainer conclusion is classified as an `accepted_decision` per
  §3 ("a direct maintainer conclusion"), not as `informal_discussion` — this
  is not an informational source overriding an approved decision, it is a
  newer authoritative one superseding an older one. An ordinary reviewer's
  PR comment does not carry this weight (it is `implementation_feedback`
  until ratified).
- **Actual code always wins on what currently happens.** Contextual evidence
  describes *intended* behavior and *scope*; it never substitutes for reading
  the implementation, and it never converts "the context says X" into "X is
  implemented."
- **Authority to establish one kind of conclusion is not authority to
  establish another.** A maintainer clarification is maintainer-only; an
  ordinary reviewer statement is `implementation_feedback` until ratified;
  automated / bot output is informational corroboration only (this mirrors
  [`review-evidence.md`](../../shared/policies/review-evidence.md), "Comment
  authorship: human review vs. automation output").

This is a small authority/inference discipline, not a trust-scoring system:
no per-author reputation weighting, no bot allowlists, no numeric scores.

## 6. `repository_policy` versus an explicit `requirement` — deterministic

When an explicit `requirement` (or `acceptance_criteria` entry) conflicts
with a `repository_policy` — the target repository's own declared invariant
or convention:

1. **If an existing repository contract already defines the precedence, that
   contract governs and is cited.**
   [`review-context.md`](../../shared/policies/review-context.md), "Precedence
   when scope sources disagree", already states that a tracker ticket cannot
   license violating the target repository's own `AGENTS.md` / `CLAUDE.md`
   rules or a safety invariant. Where that applies, the repository policy
   constrains the implementation and the reviewer says so.
2. **Otherwise, report the conflict** (`REPORT_CONFLICT`, §7) — state the
   requirement, state the repository policy, show the evidence on each side,
   and let the reader judge. The reviewer does **not** silently pick whichever
   source is ranked higher when no contract settles it.

The model defers to existing contracts where they exist and reports the
conflict where they do not; it never invents a new global priority order.

## 7. Resolution rules for conflicting / stale / ambiguous / non-authoritative evidence

Given the contextual evidence relevant to a potential finding, the reviewer
reaches exactly one of these outcomes:

| Outcome | When | Effect on the review |
| --- | --- | --- |
| `USE_AUTHORITATIVE` | One authoritative source clearly governs and nothing of equal authority contradicts it. | The review uses it for scope/intent reasoning; a violation is a finding at its independently derived severity. |
| `REPORT_CONFLICT` | Two authoritative sources contradict each other, or an explicit requirement conflicts with a repository policy and no existing contract settles it (§6). | Report the conflict with the evidence on each side; do not silently pick a side. Not itself a blocking finding unless one side is independently violated. |
| `REPORT_AMBIGUITY` | An authoritative source is too vague to decide the point, or a requirement is missing where one was expected. | Report the ambiguity where it is material to a finding; never invent the missing requirement or guess intent. |
| `TREAT_AS_INFORMATIONAL_ONLY` | The only support for a point is an informational source (§3), or authorship/ratification cannot be established. | It may focus attention or corroborate; it cannot by itself establish a requirement, a decision, or a finding. |
| `DISREGARD_STALE` | An authoritative source is contradicted by newer explicit maintainer clarification, or by the repository architecture it predates, such that it no longer describes current intent. | Set it aside for governing purposes; note the supersession only if it materially affects the reasoning shown. |

A material conflict or ambiguity that cannot be resolved from the evidence is
**reported**, never silently resolved.

## 8. Provenance-aware findings

A finding is always attributable to **code evidence** (what the
implementation actually does, per
[`evidence.md`](../../shared/policies/evidence.md)). It may additionally carry
**provenance**: the contextual-evidence entries that informed it — recorded
when that context is *why the finding is attributable to this change*, or is
the authoritative evidence that a `requirement` / `acceptance_criteria` /
`accepted_decision` is violated.

Provenance is rendered on the finding via the optional **contextual
evidence** field in
[`shared/templates/finding.md`](../../shared/templates/finding.md),
"Contextual evidence and provenance". It is shown only when it materially
explains why the behavior is incorrect or risky — not on every finding, and
never as a second, duplicate listing of the finding (this is the existing
"Tracing findings back to context" rule in
[`review-context.md`](../../shared/policies/review-context.md), given one
stable field).

### Severity and provenance are distinct

- **Authoritative contextual evidence may supply the evidence needed to
  establish a violation.** That an `acceptance_criteria` entry or an
  `accepted_decision` is contradicted is a fact about the change; that fact
  feeds the finding's **independently derived** severity per
  [`severity.md`](../../shared/policies/severity.md) exactly as any code
  evidence would. Severity still comes from actual impact, never from the
  context's own wording, emphasis, or the fact that a ticket called something
  "critical".
- **The provenance metadata itself never moves severity.** The recorded list
  of which contextual entries informed a finding does not calculate, raise,
  lower, or override severity, and does not change the finding's identity,
  its deduplication, or the mechanical decision derivation. Evidence can
  justify a severity; the provenance annotation cannot move one.

## 9. Using authoritative context for scope / intent validation

Where authoritative context makes it possible, the review reasons explicitly
about whether the delta implements the requested outcome — the
"Scope-boundary reasoning" already in
[`review-context.md`](../../shared/policies/review-context.md), now grounded
in typed evidence:

- **Required behavior missing** — a `requirement` or `acceptance_criteria`
  entry the change was expected to satisfy is not implemented (evidence: the
  absence in the diff and the surrounding code).
- **Implementation contradicts acceptance criteria** — the change does
  something an `acceptance_criteria` entry forbids, or fails a stated pass
  condition.
- **Implementation contradicts an accepted decision** — the change
  accidentally violates or regresses an `accepted_decision` (a considered,
  evidenced departure with new evidence is not a finding — see
  [`review-evidence.md`](../../shared/policies/review-evidence.md), "Settled
  decisions").
- **Unrelated scope expansion** — the change also does something outside the
  requested scope; a finding only when it carries real risk or violates a
  stated non-goal.

This narrows attention *within* the review target; it never widens the
target, and the existing scope-explosion guard in
[`review-context.md`](../../shared/policies/review-context.md), "Scope
discipline: no scope explosion", still applies.

## 10. Introduced-versus-pre-existing attribution

Contextual evidence helps attribute a finding as **introduced by the reviewed
change** or **pre-existing**:

- A `historical_context` or `pre_existing_risk_note` entry, corroborated by
  the code as it stood before the change (blame, surrounding untouched code,
  a prior commit), supports classifying a defect as **pre-existing** — not
  charged to this change, and reported only if the change *introduces,
  activates, exposes, breaks, or materially affects* it, per
  [`evidence.md`](../../shared/policies/evidence.md), "Findings beyond the
  changed lines".
- Absent such corroboration, a `pre_existing_risk_note` is
  `TREAT_AS_INFORMATIONAL_ONLY`: the reviewer still verifies against the code
  whether the reviewed delta introduced the condition. An informational note
  cannot, by itself, move a defect the change introduced into the
  "pre-existing, not our problem" bucket.
- When attribution genuinely cannot be determined from the evidence, the
  finding says so rather than guessing.

## 11. Worked examples

Each example is also a row in the reference corpus
([`../../tests/unit/test_context_evidence.py`](../../tests/unit/test_context_evidence.py)),
asserted to classify exactly as documented here.

### Worked example 1 — acceptance criterion unmet → provenance-attributed finding

```text
Context supplied:
  acceptance_criteria — "A record is validated before every write path."
Delta:
  Adds a bulk-update path that persists rows without calling the validator.
Code evidence:
  bulk_update() writes directly via repo.save_all(); the validate() call
  present on the single-write path is absent here.
Resolution: USE_AUTHORITATIVE (the acceptance criterion governs).
Finding: P1 — "Validation is bypassed on the bulk-update path".
  Provenance (contextual evidence): acceptance_criteria — "validated before
  every write path". Severity P1 is derived from the actual impact
  (unvalidated writes reach storage), not from the wording of the criterion.
```

### Worked example 2 — informal discussion contradicts an accepted decision

```text
Context supplied:
  accepted_decision — ADR 0007: "All idempotency keys are UUIDv7, generated
  server-side."
  informal_discussion — a Slack message: "let's just let clients pass their
  own keys, simpler".
Delta:
  Adds a client-supplied `idempotency_key` request field, used verbatim.
Resolution: the Slack message is informal_discussion and cannot override the
  ADR -> the ADR governs. Because the two sources disagree on the design
  point, the disagreement is noted (REPORT_CONFLICT is not required here: an
  informational source does not create a genuine authority conflict — it is
  simply disregarded as an override).
Finding: P1 — "Client-supplied idempotency keys violate ADR 0007".
  Provenance: accepted_decision — ADR 0007. The Slack message is named only
  as the apparent motivation, not as justification.
```

### Worked example 3 — risk that pre-dates the change

```text
Context supplied:
  pre_existing_risk_note — "The report exporter has always been O(n^2) on
  row count; out of scope for this ticket."
Delta:
  Changes the exporter's output format; does not touch the row-iteration
  loop.
Code evidence:
  git blame shows the nested loop unchanged for 2 years; the diff touches
  only the serializer.
Resolution: DISREGARD_STALE does not apply; the note is corroborated by the
  code -> attribute the performance issue as PRE_EXISTING.
Outcome: not reported as a finding of this review — the change neither
  introduces nor materially affects it. (If the format change had increased
  per-row work inside that loop, it would be reported as introduced.)
```

### Worked example 4 — requirement conflicts with repository policy, no contract settles it

```text
Context supplied:
  requirement — ticket: "Log the full request body on every 4xx for
  debugging."
  repository_policy — target repo AGENTS.md: "Never log raw request bodies;
  they may contain PII."
Resolution: an existing contract *does* settle this — review-context.md
  "Precedence when scope sources disagree": a ticket cannot license violating
  the target repo's own stated rules -> repository_policy governs.
Finding: P1 — "Change logs raw request bodies, violating the repo's
  no-PII-in-logs policy". Provenance: repository_policy (AGENTS.md).
  (Had there been no such repo rule and instead two contradictory
  authoritative requirements, the outcome would be REPORT_CONFLICT.)
```

### Worked example 5 — unratified implementation feedback

```text
Context supplied:
  implementation_feedback — a PR comment: "you should use the cache here".
Delta:
  Does not add caching.
Resolution: the comment is implementation_feedback and was never ratified
  into an accepted_decision -> TREAT_AS_INFORMATIONAL_ONLY.
Outcome: not a finding. The absence of caching is reported only if it
  independently causes a correctness or performance problem the code
  evidence demonstrates.
```

### Worked example 6 — two authoritative sources genuinely contradict

```text
Context supplied:
  acceptance_criteria — "Deleting an account removes all of its rows
  synchronously before the request returns."
  accepted_decision — ADR 0012: "Account deletion is asynchronous; the
  request returns once the tombstone is written."
Delta:
  Implements a background deletion job.
Resolution: two authoritative sources contradict on the same design point
  and no newer maintainer clarification settles it -> REPORT_CONFLICT.
Outcome: report the conflict with the evidence on each side; do not pick a
  side. Not itself a blocking finding unless one side is independently
  violated with its own code evidence.
```

### Worked example 7 — authoritative source too vague to decide the point

```text
Context supplied:
  requirement — ticket: "Handle errors gracefully."
Delta:
  Swallows a specific downstream 5xx and returns an empty list.
Resolution: the requirement does not say what "gracefully" means for this
  path -> REPORT_AMBIGUITY.
Outcome: report the ambiguity where it is material to a finding; do not
  invent the missing requirement. If the swallowed error causes a concrete
  defect the code demonstrates, that defect is reported on its own code
  evidence, not on the vague requirement.
```

### Worked example 8 — accepted decision superseded by newer maintainer clarification

```text
Context supplied:
  accepted_decision — ADR 0005: "All timestamps are stored as epoch
  milliseconds."
  accepted_decision — later, in the PR thread, the maintainer states
  directly: "We moved to RFC 3339 strings in ADR 0018; 0005 is superseded."
  (A direct maintainer conclusion is an accepted_decision per §3, not
  informal_discussion — an ordinary PR comment would not carry this weight.)
Delta:
  Stores timestamps as RFC 3339 strings.
Resolution: a newer accepted_decision (the maintainer's direct conclusion /
  ADR 0018) contradicts the older accepted decision -> DISREGARD_STALE for
  ADR 0005.
Outcome: no finding against the delta for following ADR 0018. Note the
  supersession only if it materially affects the reasoning shown.
```

## 12. Preventing precision loss

Retrieved / supplied context is a precision risk if it is allowed to lower
the bar for reporting. The model prevents that as follows:

- **Context focuses attention and supplies provenance; it never lowers the
  evidence bar.** Every finding still requires concrete code evidence and the
  confirmed-defect / credible-risk / optional-improvement labeling of
  [`evidence.md`](../../shared/policies/evidence.md). "The context says so" is
  not evidence that the code does so.
- **Informational sources cannot create findings.** A finding cannot rest
  solely on `informal_discussion`, unratified `implementation_feedback`,
  `historical_context`, or a `pre_existing_risk_note`
  (`TREAT_AS_INFORMATIONAL_ONLY`).
- **Severity is never imported from a source's wording.** It is derived from
  actual impact; a ticket calling something "critical" does not make a
  finding P0 (§8).
- **Stale or ambiguous context yields a note, not a finding.**
  `REPORT_CONFLICT`, `REPORT_AMBIGUITY`, and `DISREGARD_STALE` produce
  reported observations, not blocking findings, unless a side is
  independently violated with its own evidence.
- **No manufactured findings for thoroughness.** The scope-explosion guard
  and "do not manufacture findings to appear thorough" rules
  ([`review-scope.md`](../../shared/policies/review-scope.md),
  [`evidence.md`](../../shared/policies/evidence.md)) are unchanged;
  context narrows attention within the target, it does not turn the review
  into a requirements or architecture audit.
- **Provenance is additive, not a second decision path.** Recording which
  contextual evidence informed a finding does not add a decision label or a
  severity input.

Net effect: authoritative context can only *raise* precision (catch a real
missing requirement, attribute a defect correctly) and provenance makes the
reasoning auditable; neither can introduce a finding the code evidence does
not support.

## 13. Smallest useful first implementation

The smallest slice that delivers the capability:

1. **This typed model** — the eight evidence types, their
   authoritative/informational marking, the authority rules (§5–§6), and the
   five resolution outcomes (§7) — consumed as **reviewer discipline** over
   context the caller already supplies.
2. **One packaged field** — the optional **contextual evidence** field and
   its rendering contract on
   [`shared/templates/finding.md`](../../shared/templates/finding.md), so a
   finding's provenance is real in output, not only designed.
3. **Reference-level cross-links** from
   [`review-context.md`](../../shared/policies/review-context.md) and
   [`review-evidence.md`](../../shared/policies/review-evidence.md) to this
   document — no matrix or table duplicated into packaged policy.

**Deferred to later issues** (named here so scope stays fixed):

- source adapters — Jira, GitHub Issues/PR comments, Slack, ADR ingestion;
- automatic PR↔Issue discovery (linkage stays whatever the caller states);
- a machine-readable provenance block in review output — waits on the #67
  output schema; #178's unified confidence / evidence-state field is now
  defined (the [finding-confidence model](../finding-confidence/finding-confidence-model.md))
  and rolls this model's authoritative/informational typing into one
  `confidence` value without redefining it;
- any runtime that retrieves, resolves, infers, or auto-attaches contextual
  evidence during a review.

## 14. Runtime boundary

[#118](https://github.com/amirbena/code-review-skill/issues/118) adds the
optional finding field, its rendering contract, and this model as discipline.
It introduces **no** automatic context retrieval, resolution, inference, or
attachment; it grants **no** new capability (no mutation, no network beyond
what [`review-context.md`](../../shared/policies/review-context.md) already
permits read-only); it does **not** change how context is supplied — still
the existing caller-supplied path in
[`review-context.md`](../../shared/policies/review-context.md), "Input form".
The reviewer records provenance for context it was already given.

## 15. Relationship to existing canonical policies

- [`review-context.md`](../../shared/policies/review-context.md) owns the
  four concepts, the code-first evidence hierarchy, scope-boundary reasoning,
  the scope-explosion guard, and "Tracing findings back to context". This
  document types the *review-context* material and makes the authority
  ordering explicit; it does not restate those rules.
- [`review-evidence.md`](../../shared/policies/review-evidence.md) owns
  classification of **prior review evidence**, the "Settled decisions" bar,
  and the comment-authorship authority rule. `accepted_decision` and the
  ratification rule in §4 build directly on it.
- [`evidence.md`](../../shared/policies/evidence.md) owns the code-evidence
  bar and "Findings beyond the changed lines"; §10 attribution stays inside
  it.
- [`severity.md`](../../shared/policies/severity.md) owns severity and the
  mechanical decision derivation; §8 does not touch it.
- [`shared/templates/finding.md`](../../shared/templates/finding.md) owns the
  finding contract; the **contextual evidence** field is defined there and
  described here.
