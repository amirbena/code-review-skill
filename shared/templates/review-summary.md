# Shared Template — Human-Facing Review Summary

The canonical shape of the **human-facing review body**, shared by both
Skills: `local-code-review`'s own `templates/local-review-report.md` and
`github-pr-review`'s own `templates/external-review-summary.md`. Each
Skill renders this shape for its own delivery surface — a returned
report vs. a published GitHub review body — but the section order and
hierarchy do not diverge, so both Skills read as two delivery modes of
the same Code Review Agent standard.

This is the primary output. It is written for the engineer receiving the
review, not for an orchestrator consuming machine state — see "Machine
metadata is subordinate" below.

## Canonical shape

```markdown
## Code Review

**Result: <emoji> <short human result label>**

<one or two sentences: overall assessment, merge/proceed safety, and the most
important concern or attention point; include scope only when useful>

### What changed
<concise, concrete summary of what the change implements and its intent>

### What was done well
- **<theme>:** <concrete, evidence-backed strength>
- **<theme>:** <concrete, evidence-backed strength>

### Findings
<only when findings exist; for each finding: either its full rendering (per
  [`finding.md`](finding.md), "Canonical full rendering") when this is
  its one authoritative location, or its summary-pointer rendering (per
  [`finding.md`](finding.md), "Canonical summary-pointer rendering") when
  its full form was already published at another location (e.g. a GitHub
  inline comment) — never both. Findings use the compact, field-oriented
  contract in [`finding.md`](finding.md) — a scannable block per finding,
  not a multi-paragraph essay; a longer `Details` field only for the
  cases [`finding.md`](finding.md), "When a longer explanation is
  justified" allows.

### Requirement coverage
<only when an authoritative task contract activates
  [`requirement-coverage.md`](../policies/requirement-coverage.md): overall
  `complete` / `incomplete`, followed by every requirement's identifier,
  status, source citation, concrete evidence, and explanation>

### Validation
- <one entry per selected command, or an explicit no-command entry, using
  exactly `executed`, `skipped`, `failed`, or `unavailable`; include the exact
  command, declaration source, scope/justification, observed evidence, and a
  reason where applicable>
- <one entry per attempted targeted per-finding validation: the targeted
  finding id, the `executed` / `failed` / `skipped` / `unavailable` outcome,
  the resulting finding validation state, and bounded run evidence; a
  disproving run is recorded here even though it raises no finding>

### Decision
**<decision label>**

<one-sentence rationale tied to the findings above>
```

### Heading is a per-Skill override point

The `## Code Review` line above is this shared shape's **default**
heading — the exact value `local-code-review` renders unchanged in its
own `templates/local-review-report.md` (not linked from here: this
shared template is packaged standalone into every consuming Skill's own
archive, and must never depend on another Skill's directory existing
alongside it — see [`finding-rendering.md`](finding-rendering.md),
"Location source annotation" for the same packaging constraint). A
consuming Skill may override **only this one heading line** for its own
delivery surface, without forking any other part of this shape:
`github-pr-review` overrides it to `## Review Summary` in its own
`templates/external-review-summary.md`, consistently for every rendered
case (clean, findings, fallback, and the self-review informational
`COMMENT`) and for both the structured and the `human_review_output`
senior-voice rendering below. This is the **only** override point this
shared shape defines — every other section, its order, and its content
rules stay identical across both Skills. A Skill that declares no
override renders the default heading shown above; this paragraph is
additive documentation and changes no Skill's rendered output by itself.

## Section rules

- **Result** — states the outcome in plain language immediately, e.g.
  `✅ Review Clean` or `⚠️ Changes Requested`. A reader must never have to
  infer the outcome from counts. **Result and Decision render the same
  single, already-finalized decision value** — per
  [`severity.md`](../policies/severity.md), "Decision derivation
  (mechanical)," that value is derived exactly once, after findings are
  finalized, and both sections present it; neither is a second,
  independently-derived outcome. A published report contains exactly one
  such value throughout — never a Result that disagrees with the Decision
  section, never a provisional Result later replaced by a corrected one,
  and never correction prose narrating that an earlier rendering was
  wrong.
- **Opening assessment** — immediately says whether the change is safe to
  merge/proceed and names the highest-priority concern or reviewer attention
  point. Avoid mechanical “reviewed N files” boilerplate when it adds no
  useful context.
- **What changed** — a concrete implementation summary, not a diff dump.
- **What was done well** — only concrete, evidence-backed strengths.
  Omit the section (or keep it to one line) rather than invent generic
  praise when nothing specific stands out.
- **Empty sections** — omit optional sections that add no information. A clean
  review normally needs only the result/opening assessment, a compact change
  summary when useful, validation, and the final decision; do not repeat “no
  findings” in multiple sections.
- **Findings** — the aggregate view. Every P0/P1/P2 finding is
  represented exactly once, in exactly one authoritative form (full or
  summary-pointer — never both), per
  [`finding.md`](finding.md), "Rules," and rendered with the compact,
  field-oriented finding contract in [`finding.md`](finding.md) so the
  per-finding shape and this summary read as one coherent contract. This
  section does not repeat implementation detail already covered under
  "What changed." Omit the section completely on a clean review; the opening
  assessment and Decision already communicate that result.
- **Validation** — reports only what was actually observed (tests run,
  packaging performed, links checked, etc.). Runtime validation uses the
  shared [`runtime-validation.md`](../policies/runtime-validation.md)
  contract: every selected command is explicitly `executed`, `skipped`,
  `failed`, or `unavailable`, with exact command and reason/evidence;
  non-execution is never a pass. A **targeted per-finding** validation is
  recorded here too — the targeted finding id, the same
  `executed` / `failed` / `skipped` / `unavailable` outcome, and the
  resulting finding validation state (`runtime-confirmed` /
  `attempted-inconclusive`, or a disproving run that raised no finding).
  Targeted validation state never changes a finding's severity or the
  Decision. It rolls up, together with any contextual-evidence provenance,
  into the finding's single `confidence` value per
  [`finding.md`](finding.md), "Confidence and evidence state" — which is
  likewise presentation/provenance only and never changes severity or the
  Decision.
- **Requirement coverage** — conditional and distinct from Findings. It is
  absent when no authoritative task contract was supplied. When present it
  follows [`requirement-coverage.md`](../policies/requirement-coverage.md),
  appears before Validation, and never changes severity or Decision. It is a
  semantic invariant across findings, clean, structured, and human-style
  renderings: presentation may be condensed, but no active coverage result or
  requirement may be discarded.
- **Decision** — an unambiguous label plus one sentence tying it to the
  findings. Never leave the reader to compute the outcome from raw P0/P1/P2
  counts. The decision itself is derived mechanically from blocking
  severities per [`severity.md`](../policies/severity.md), "Decision
  derivation (mechanical)" — it is never an independent judgment call
  that can contradict that derivation, and a non-blocking finding (P2)
  never produces a blocking decision no matter how strongly it is
  recommended.

## Concise human-style summary (opt-in)

When the invocation selects `human_review_output` (per
[`../policies/invocation-options.md`](../policies/invocation-options.md),
"`human_review_output` phrasings"), the **final human-facing summary** is
rendered in a concise senior-engineer voice **instead of** the structured
canonical shape above. Everything upstream is unchanged: the same
investigation, the same evidence-backed findings, the same P0/P1/P2
severities, the same mechanically derived decision, and — for
`github-pr-review` — the same GitHub review state, the same set of inline
findings at the same locations, and the same optional machine-readable
status. Only the wording of this final summary differs (and, where a
Skill also publishes inline review findings, the wording of those when
the companion option `human_inline_findings` is on — see "Companion
inline rendering (`human_inline_findings`)" below).

The concise form reads like a short review note a strong engineer would
leave by hand:

- a one- or two-sentence opening that says whether the change is safe to
  merge / proceed and names the single biggest concern;
- **what's good** — a sentence or two of concrete, specific praise (omit
  if nothing specific stands out);
- **what's concerning** / **what to change** — the findings that need
  action, in prose, each still carrying its `P0` / `P1` / `P2` label when
  it is referenced;
- **requirement coverage** — when analysis was active, the overall signal and
  every requirement/status remain visible in concise prose; omit it when
  coverage was inert;
- an apparently intentional trade-off may be raised as a question
  ("was returning `null` to the caller here deliberate?") rather than
  asserted as a defect.

It **excludes** internal review-process language and investigation
metadata entirely — review mode, base/head SHAs, file or finding counts,
action mode, parallel-worker / aggregation wording, and the subordinate
machine-metadata block are all left out of this comment. It does not
restate a finding's full `Evidence` / `Impact` / `Fix` block when that
detail is already published elsewhere (e.g. a GitHub inline comment).

This is presentation only. It never changes finding detection, severity
classification, finding identity or deduplication, re-review semantics,
the blocking / non-blocking decision, or — where a Skill has them — the
GitHub review-state selection and publication ordering. Mode on and mode
off produce identical findings and severities (and, for `github-pr-review`,
identical GitHub review state and machine-readable status), and differ
only in the text of this final summary — and, when `human_inline_findings`
is on, in the wording of the inline findings, which stay the same
findings at the same locations. Requirement-coverage content is likewise
unchanged. When the option is off (the default), the
structured canonical shape above is used unchanged.

### Companion inline rendering (`human_inline_findings`)

`human_review_output` re-voices this summary. Where a Skill also publishes
**inline** review findings (`github-pr-review`), the companion option
`human_inline_findings` re-voices those to match — a short heading that
keeps the `P0` / `P1` / `P2` severity and names the finding, then compact
prose in place of the `Evidence:` / `Impact:` / `Fix:` labelled block
(see [`finding.md`](finding.md), "Canonical human inline rendering") — so
a senior-mode review is coherent end to end. Its default is derived:
`explicit_value ?? human_review_output`, so enabling senior mode enables
it too; it is set explicitly only to opt out (structured inline block
under a concise summary) or to opt in on its own. Same presentation-only
guarantee: the inline findings keep their detection, severity, identity,
deduplication, evidence, remediation, decision, canonical fix/action
location, and publication anchor; only the inline wording changes. See
[`../policies/invocation-options.md`](../policies/invocation-options.md),
"`human_inline_findings` derived default and phrasings".

### Density, de-duplication, and voice tightening (`github-pr-review` only)

This subsection is an explicit, opt-in extension that only
`github-pr-review` applies to its own rendering — both the structured
shape and the senior voice above — per its own `policies/review-output.md`
and `templates/external-review-summary.md` (not linked from here for the
same packaging reason as the heading override above: this shared
template must not depend on another Skill's directory existing
alongside it), which state exactly where and how it applies. It is
additive documentation, inert for any consumer that does not opt into it:
`local-code-review` does not reference this subsection, and its own
report format, density, and senior-voice wording (per its own
`templates/local-review-report.md`, "Concise human-style output
(opt-in)") are unaffected and unchanged by it.

- omit a section entirely when it would add no information, rather than
  rendering it with placeholder or boilerplate content;
- never restate the diff — describe what changed and why, not a
  line-by-line narration of the patch;
- never narrate file-by-file inspection or reproduction mechanics beyond
  what the `Validation` / [`runtime-validation.md`](../policies/runtime-validation.md)
  contract already records — the reader needs the result, not a
  transcript of the review process;
- never repeat the same evidence in more than one place across the
  summary line, a fallback full finding, and its inline comment — each
  fact appears once, in its one authoritative location;
- let the output's length scale with the number and complexity of
  findings, never with the number of available template sections — a
  two-finding review and a ten-finding review do not carry the same
  fixed scaffolding;
- there is **no numeric word or line cap** — concision comes from cutting
  restatement and process narration, never from truncating evidence,
  impact, or fix;
- read like a concise human review: natural short paragraphs, minimal
  headings, no evidence repeated across sections, and no meta-commentary
  about the review process itself (no "I reviewed file X then file Y",
  no narrating that a reproduction was attempted beyond the Validation /
  runtime-validation record) — while every existing evidence/rigor
  guarantee (the same findings, severities, decision, and anchors) stays
  exactly as specified elsewhere in this shape and in
  [`finding.md`](finding.md).

## Machine metadata is subordinate

Internal/orchestration state (reviewed HEAD or base/head SHAs, raw
P0/P1/P2 counts, a normalized machine decision code, internal finding
identifiers, the deterministic `standard` / `elevated` / `deep`
change-risk depth and its activating signals per
[`../policies/change-risk-signals.md`](../policies/change-risk-signals.md),
the fired repository-expansion triggers and rings reached per
[`../policies/repository-expansion.md`](../policies/repository-expansion.md),
or other automation state) is never part of the primary human-facing body
above. Where publishing it is genuinely useful to a
caller or automation, append it after the human-facing body, clearly
subordinate — always last, always visually secondary to the Result →
... → Decision body above it.

The **one exception to consumer-gating** below is the pair of always-on
process classifications: the change-risk depth per
[`../policies/change-risk-signals.md`](../policies/change-risk-signals.md)
and the repository-expansion decisions per
[`../policies/repository-expansion.md`](../policies/repository-expansion.md).
Both are always emitted in this subordinate block — on every review,
including a clean `standard` review with no signals and no fired
expansion trigger — never as a finding and never in a way that implies a
verdict. Every other field stays consumer-gated.

This shared template fixes *that* the metadata is subordinate and
appended last; it does not fix the concrete markup used to render it.
Each consuming Skill's own template owns that choice for its own
delivery surface — see
`local-code-review`'s own `templates/local-review-report.md` (native
Markdown, since its delivery surface is a returned report read directly
in a terminal/chat, where a collapsible section provides no benefit) and
`github-pr-review`'s own `templates/external-review-summary.md` (a
collapsible `<details>` block, since its delivery surface is a rendered
GitHub review body where GitHub natively supports collapsing it). Do not
publish machine metadata merely because it is available — include only
fields with a genuine downstream consumer (orchestration, automated
re-review, audit), plus the always-present change-risk classification
noted above. If nothing else needs it, the block still carries that
classification and nothing more, rather than padding the review with
other unused state.

One field is **conditional on activation rather than consumer-gated**:
whether [`../policies/large-pr-partitioning.md`](../policies/large-pr-partitioning.md)
activated for this change and, when it did, the partitions built and any
cross-partition duplicate/consolidation aggregation found. It is rendered
only when partitioning activated; a change that stayed under that
policy's diff-size threshold carries no partitioning line at all — it is
not part of the always-on pair above, and its absence on an ordinary
review is not an omission.
