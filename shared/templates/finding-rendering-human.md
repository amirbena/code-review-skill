# Shared Template — Human Finding Renderings

The opt-in senior/human projections of a finding: the **Senior voice
contract** and the two human renderings that apply it. This file is
**conditionally loaded** — only when `human_review_output` or
`human_inline_findings` is in effect for the invocation (see each Skill's
`SKILL.md`, "Required Policy Loading"). The structured renderings, the
severity-legend override, and the rendering rules are owned by
[`finding-rendering.md`](finding-rendering.md), which is always loaded; the
finding fields and quality contract are owned by [`finding.md`](finding.md).
Nothing here changes a finding's identity, severity, evidence bar, canonical
location, or the decision derivation.

## Senior voice contract

The **single owner** of the senior/human review voice — the prose rules
shared by every rendering that opts into `human_review_output` /
`human_inline_findings`: "Canonical human inline rendering" and
"Canonical human full rendering" below, and the review-summary prose in
[`review-summary.md`](review-summary.md), "Concise human-style summary
(opt-in)". Those three sites keep only their own surface-specific shape —
what fields exist, where the anchor comes from, what is inline vs.
full-body vs. summary prose — and link here instead of restating the
voice. This is **presentation only**: it changes no finding's detection,
severity, identity, deduplication, evidence/remediation requirement,
verdict derivation, placement/anchor, or publication authorization (see
[`finding.md`](finding.md)).

It reads the way a strong senior engineer would write the comment or
summary by hand — not a structured report with the field labels taken
off.

### Voice principles

1. **Lead with the defect or failure mode.** The heading (or opening
   sentence, in the summary) says what breaks and under what condition.
2. **Say why it matters in the repo's own terms** — the invariant, gate,
   or caller that gets hurt — not generic risk language.
3. **State each fact once.** Restatement is judged semantically, not
   lexically (see "Semantic restatement, not lexical" below): the title,
   evidence, impact, and fix don't repeat each other's substance.
4. **Separate required from optional.** The required correction
   direction is stated plainly; an implementation suggestion is marked
   optional (e.g. "one way: …"), never over-prescribed when several
   fixes would work.
5. **Tone follows severity.** `P0`/`P1` findings are decisive — no
   hedging, no question unless the uncertainty is genuine. `P2` findings
   are proportional, never artificially urgent.
6. **Short and direct by default; add context only when the finding needs
   it.** Length follows the finding's complexity — no fixed sentence or
   paragraph count is a default or a limit. A simple finding says what is
   wrong, why it matters, and what must change, and stops; extra
   explanation is added only where the finding needs it (the existing
   "longer explanation" exception each rendering below defines).
7. **No boilerplate.** Never "The evidence shows…", "The impact of this
   is…", "Consider changing…", or generic praise. Evidence, impact, and
   fix are carried in the prose, never announced by a sentence about
   itself.
8. **Same rigor as structured mode.** Senior voice is not fewer labels,
   longer prose, a friendlier tone, or more explanation — every
   mandatory-core field, the evidence bar, and uncertainty handling stay
   exactly as required.

### No dedicated praise slot

Senior/human output has **no dedicated praise slot**. Positive feedback
appears only when it is specific and materially useful; it is never
manufactured to fill a shape (a named praise section or line, a required
opening compliment, or similar). This matches the structured shape, where "What
was done well" is itself optional and evidence-only — senior voice does
not introduce a senior-only obligation the structured shape doesn't have.

### Required fixes are stated directly, not as first-person suggestions

A **required** correction is stated directly — what must become true —
never as a first-person suggestion (`I'd`, `I would`) or other hedging.
First-person framing is reserved for a genuinely **optional**
implementation suggestion; it is never the default, and never used on a
`P0`/`P1` finding's required fix. This mirrors the existing structured
`Fix` field, which is already declarative even where several
implementations would work — it states the required outcome, not the
reviewer's personally preferred implementation.

### Density, de-duplication, and voice tightening

These rules govern every senior-voice rendering — inline, full-body, and
the review-summary prose — for both Skills; they are not scoped to one
Skill or one surface:

- omit a section entirely when it would add no information, rather than
  rendering it with placeholder or boilerplate content;
- never restate the diff — describe what changed and why, not a
  line-by-line narration of the patch;
- never narrate file-by-file inspection or reproduction mechanics beyond
  what the `Validation` / [`../policies/runtime-validation.md`](../policies/runtime-validation.md)
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

### Semantic restatement, not lexical

"State each fact once" (principle 3) is judged by whether the prose after
a heading/title adds genuinely **new information** — evidence, the
triggering condition, the consequence, or the correction direction — not
by whether it repeats a noun phrase from the heading. A heading like `P2:
Retry eligibility logic is duplicated` followed by prose that also says
"retry eligibility" and "duplicated" is not a violation if the prose adds
the consequence and the fix. Conversely, a heading like `P1: Authorization
check is broken` followed by "The auth check doesn't work properly and
must be addressed" adds nothing despite sharing no noun phrase with the
heading — that **is** a violation. Judge restatement this way; do not
build or apply a mechanical noun-phrase-repetition check against the
heading.

## Canonical human inline rendering

An **opt-in** projection of the same fields onto a GitHub inline comment,
selected by `human_inline_findings` (see
[`../policies/invocation-options.md`](../policies/invocation-options.md),
"`human_inline_findings` derived default and phrasings" — its default is
derived from `human_review_output`). Used only by `github-pr-review`, and
only for the inline surface: `local-code-review` has no inline comments.
The summary-pointer rendering is never affected by either presentation
option. The full rendering in [`finding-rendering.md`](finding-rendering.md) has its own opt-in human projection —
selected by `human_review_output` directly, not by `human_inline_findings`
— defined next in "Canonical human full rendering." The voice itself —
what makes this read like a senior engineer's comment rather than a
relabelled structured block — is owned by "Senior voice contract" above;
this section states only the inline-surface shape:

```text
<severity>: <short, concrete finding — what is actually wrong>

<short, direct prose that carries the concrete problem and the evidence
for it, the engineering consequence when it is material or non-obvious,
and an actionable correction direction when one is useful; more context
only when the finding needs it. A genuine open question or trade-off is
phrased as a question, not asserted as a defect.>
```

Examples:

```text
P1: Paginated file listing stops after page 1

`list_files()` reads only the first page, so a large PR can reach a clean
review decision with files that were never seen. Exhaust the pagination
before permitting a clean decision.
```

```text
P2: Sync and async retry paths decide eligibility separately

`should_retry()` in the sync flow and the inline check in
`AsyncRunner.retry` already disagree on 429 handling. Move eligibility
into one helper that both paths call.
```

Rules — this is a re-voicing, not a weaker finding:

- follows the **Senior voice contract** above in full, including no
  dedicated praise slot and no first-person/hedging on a required fix;
- **severity stays visible first**, in the heading, as `P0` / `P1` /
  `P2` (e.g. `P2: …`, never `[P2] …`);
- the **mandatory core still holds** — What / Where / Evidence / Impact /
  Fix per "Finding quality contract". "Where" is the inline anchor the
  surface supplies (the canonical fix/action location, unchanged); the
  other four are carried by the prose instead of by labelled fields, and
  none may be dropped, softened to a vague gesture, or replaced by
  generic "consider improving this" language;
- **no meta-commentary about the review process** — no narrating that a
  file was inspected, that a reproduction was attempted, or restating
  investigation steps; the comment states the result, not the process
  that produced it;
- **evidence-based** per [`../policies/evidence.md`](../policies/evidence.md);
  genuine **uncertainty is preserved** as a question rather than asserted;
- a justified longer explanation ("When a longer explanation is
  justified") is folded into the prose as one extra short paragraph on
  the same visibility terms as `Details` elsewhere — never re-introduced
  as a `Details:` label;
- the finding's **identity, severity, deduplication, canonical
  fix/action location, evidence/detection location, and publication
  anchor are exactly those of the structured inline rendering in
  [`finding-rendering.md`](finding-rendering.md)** —
  structured and human inline are two renderings of one semantic
  finding, and the choice of rendering never moves the comment off the
  canonical fix/action location or into the review body (that is decided
  only by each Skill's placement policy, independent of voice);
- a **consolidated root-cause finding** still names every affected call
  path in the prose — the re-voicing never drops a manifestation site;
- a **`Follow-up`** identified per
  [`../policies/remediation-scope-boundary.md`](../policies/remediation-scope-boundary.md)
  is folded into the closing prose as a clearly separated sentence, never
  phrased as part of the required fix — the re-voicing changes wording
  only, never the underlying remediation-scope-boundary outcome.

## Canonical human full rendering

An **opt-in** projection of the same fields onto a finding rendered **in
full in the review body** rather than as a GitHub inline comment — used by
`github-pr-review` for a passive review's findings (passive has no inline
surface, so every finding is rendered this way) and for an active-review
finding with no valid inline anchor (see each Skill's own placement
policy). Selected directly by `human_review_output` (see
[`../policies/invocation-options.md`](../policies/invocation-options.md),
"`human_review_output` phrasings"), **not** by `human_inline_findings` —
that option is scoped to the GitHub inline surface only and is not
redefined by this section. `local-code-review` has no inline/body split
(every finding is already a body finding); it is unaffected and keeps its
own senior-voice summary wiring exactly as it stands today. The voice
itself is owned by "Senior voice contract" above; this section states
only the full-body-surface shape.

Unlike the inline rendering, this surface has no platform-supplied anchor,
so the finding's `id` and canonical `Location` are kept as their own line,
exactly as in the canonical full rendering; only the `Evidence` /
`Impact` / `Fix` block below them is re-voiced as senior-engineer prose,
the same way "Canonical human inline rendering" re-voices the inline
block:

```text
### <id> <severity>: <short, concrete title>

`<path>:<line-or-range>`

<short, direct prose that carries the concrete problem and the evidence
for it, the engineering consequence when it is material or non-obvious,
and an actionable correction direction when one is useful; more context
only when the finding needs it. A genuine open question or trade-off is
phrased as a question, not asserted as a defect.>
```

Examples:

```text
### F3 P1: Paginated file listing stops after page 1

`app/github_client.py:88-104`

`list_files()` reads only the first page, so a large PR can reach a clean
review decision with files that were never seen. Exhaust the pagination
before permitting a clean decision.
```

```text
### F2 P2: Sync and async retry paths decide eligibility separately

`app/retry.py:41-58`

`should_retry()` in the sync flow and the inline check in
`AsyncRunner.retry` already disagree on 429 handling. Move eligibility
into one helper that both paths call.
```

This is a re-voicing of the **same finding**, on the same terms as the
human inline rendering:

- follows the **Senior voice contract** above in full, including no
  dedicated praise slot and no first-person/hedging on a required fix;
- **severity stays visible first**, in the heading, next to `id` (e.g.
  `F2 P2: …`, never `[P2] …`);
- **`id` and `Location` stay their own line** — the body has no anchor to
  omit them in favor of, unlike the inline surface;
- the **mandatory What / Where / Evidence / Impact / Fix core** is fully
  present — carried by the prose for the last three, none dropped,
  softened, or replaced by generic language;
- an `evidence location`, `contextual evidence`, `runtime validation`, or
  `confidence` line that the structured full rendering would show is
  folded into the prose instead — the same fold-in treatment the inline
  rendering uses — rather than added as its own labelled line;
- a justified longer explanation folds into the prose as one extra short
  paragraph, on the same visibility terms as `Details` elsewhere, never
  re-introduced as a `Details:` label;
- **no meta-commentary about the review process** and **evidence-based**,
  per [`../policies/evidence.md`](../policies/evidence.md) — the same
  rules as the human inline rendering;
- the finding's **identity, severity, deduplication, canonical
  fix/action location, evidence/detection location, and the fact that it
  is published in the body rather than inline are exactly those of the
  structured full rendering** — structured and human full are two
  renderings of one semantic finding; rendering voice never moves it
  between the body and an inline comment (that is decided only by each
  Skill's placement policy, independent of voice);
- a **consolidated root-cause finding** keeps its `Affected locations`
  list (see "Affected locations on a consolidated finding" in
  [`finding.md`](finding.md)), either as its own line or folded into the
  prose, so no manifestation site is dropped.

When `human_review_output` is off — explicitly, or because nothing set
it — a body finding uses the structured full rendering in
[`finding-rendering.md`](finding-rendering.md), unchanged.

