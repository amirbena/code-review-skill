# Shared Template — Finding Renderings

The canonical rendering exemplars for a single finding, projected onto each
delivery surface. The **fields and the quality/conciseness contract** these
render are owned by [`finding.md`](finding.md); this file is one projection
of those fields and never changes the finding's identity, severity, evidence
bar, canonical location, or the decision derivation. Read
[`finding.md`](finding.md) first — it is the contract; this file is how that
contract is drawn.

## Canonical full rendering

Used wherever a finding needs its complete, standalone representation —
a local review report, or a GitHub review body when no valid inline
anchor exists. Compact and field-oriented:

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<path>:<line-or-range>`
- **Evidence:** <concrete evidence, concise>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
```

A finding that meets "When a longer explanation is justified" and whose
detail-visibility decision is true adds one `Details` field after `Fix`:

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<path>:<line-or-range>`
- **Evidence:** <concrete evidence, concise>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
- **Details:** <the cross-file / concurrency / security / invariant
  explanation supporting the finding — a short paragraph, not an essay>
```

When the evidence was observed somewhere other than the resolved
fix/action location, one `Evidence location` line is added directly after
`Location` (omitted when the two coincide):

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<fix/action path>:<line-or-range>`
- **Evidence location:** `<where the evidence was observed>`
- **Evidence:** <concrete evidence, concise>
- **Impact:** <concrete engineering consequence, concise>
- **Fix:** <concrete correction direction, not a patch>
```

When the fix/action location is unresolved, no `Evidence location` line
is added; `Location` instead carries the best-known coordinate with the
trailing unresolved annotation (see "Fix/action location, evidence
location, publication"):

```markdown
- **Location:** `<observed path>:<line-or-range>` _(evidence location; fix/action location unresolved)_
```

A **consolidated root-cause finding** adds an `Affected locations` list
directly after `Location` (see "Affected locations on a consolidated
finding"); `Location` is the shared cause:

```markdown
### <id> [<severity>] <short, concrete title>

- **Location:** `<shared-cause path>:<line-or-range>`
- **Affected locations:**
  - `<path>:<line-or-range>` — <how the shared cause reaches this site>
  - `<path>:<line-or-range>` — <how the shared cause reaches this site>
- **Evidence:** <the shared cause, concise>
- **Impact:** <combined engineering consequence across the affected sites>
- **Fix:** <one correction direction at the shared cause / canonical owner>
```

### Location source annotation

When a Skill appends its source-state classification, it goes after the
required `` `<path>:<line-or-range>` `` value on the `Location` line, as a
strict trailing addition — it never replaces, reorders, or hides that
value:

```markdown
- **Location:** `<path>:<line-or-range>` _(<annotation>)_
```

For example, `local-code-review` appends the repository-state category a
finding was attributed to (`(committed)`, `(staged)`, `(unstaged)`, or
`(untracked)`) — see that Skill's own `policies/repository-state.md`,
"Attribution in findings" (not linked from here: this shared template is
packaged standalone into every consuming Skill's own archive, and must
never depend on another Skill's directory existing alongside it). This
concept is specific to a local Git working tree and has no equivalent
for a GitHub Pull Request, whose findings are already anchored to a
specific commit/diff location by GitHub itself — `github-pr-review` is
not required to add one, and must not force repository-state categories
onto PR findings that don't have them. A Skill that has no such concept
simply renders the `Location` line without a trailing annotation.

The `_(evidence location; fix/action location unresolved)_` marker from
"Fix/action location, evidence location, publication" is a second
permitted strict trailing addition on this same line. When both apply,
render the source-state annotation first, then the unresolved marker;
neither replaces, reorders, or hides the `` `<path>:<line-or-range>` ``
value.

## Canonical inline rendering

Used for a GitHub inline review comment, where the platform supplies the
file/line anchor and the comment's own identity. `id` and `Location` are
omitted for that reason; severity stays first; fields stay concise:

```text
[<severity>] <short, concrete title>

Evidence: <concrete evidence — what the code actually does>

Impact: <concrete engineering consequence — why it matters>

Fix: <concrete correction direction, when useful>
```

A justified longer explanation adds a single `Details:` line after `Fix:`, on
the same visibility terms as the full rendering.

The inline anchor is the finding's canonical fix/action location, not the
evidence location and not a line chosen because the platform allows a
comment there (see "Fix/action location, evidence location, publication",
and each Skill's placement policy). When the evidence was observed
elsewhere, name that evidence/source location inside the `Evidence:`
prose — there is no separate `Evidence location:` line on this surface.

For a **consolidated root-cause finding**, name the affected call paths
inside the prose — the `Evidence:` block, or a short `Affected call paths:`
list after `Fix:` — so no manifestation site is dropped on this surface.
The anchor stays the shared cause (see "Affected locations on a
consolidated finding").

## Canonical human inline rendering

An **opt-in** projection of the same fields onto a GitHub inline comment,
selected by `human_inline_findings` (see
[`../policies/invocation-options.md`](../policies/invocation-options.md),
"`human_inline_findings` derived default and phrasings" — its default is
derived from `human_review_output`). Used only by `github-pr-review`, and
only for the inline surface: `local-code-review` has no inline comments,
and the full / summary-pointer renderings above are never affected.

It reads the way a strong senior engineer would leave the comment by
hand — a short heading that keeps the severity and names the concrete
finding, then compact prose:

```text
<severity>: <short, concrete finding — what is actually wrong>

<one to three short paragraphs that carry the concrete problem and the
evidence for it, the engineering consequence when it is material or
non-obvious, and an actionable correction direction when one is useful.
A genuine open question or trade-off is phrased as a question, not
asserted as a defect.>
```

Example:

```text
P2: Retry eligibility logic is duplicated

The same eligibility decision is implemented in both the sync and async
flows, so the behaviour can drift when one path changes and the other is
missed. I'd centralise it behind one policy/helper and have both flows
call that.
```

Rules — this is a re-voicing, not a weaker finding:

- **severity stays visible first**, in the heading, as `P0` / `P1` /
  `P2` (here `P2: …`, never `[P2] …`);
- the **mandatory core still holds** — What / Where / Evidence / Impact /
  Fix per "Finding quality contract". "Where" is the inline anchor the
  surface supplies (the canonical fix/action location, unchanged); the
  other four are carried by the prose instead of by labelled fields, and
  none may be dropped, softened to a vague gesture, or replaced by
  generic "consider improving this" language;
- **concise by default** per "Conciseness contract"; two paragraphs is
  not required and the length adapts to the finding;
- **evidence-based** per [`../policies/evidence.md`](../policies/evidence.md);
  genuine **uncertainty is preserved** as a question rather than asserted;
  **no praise** on an inline comment;
- a justified longer explanation ("When a longer explanation is
  justified") is folded into the prose as one extra short paragraph on
  the same visibility terms as `Details` elsewhere — never re-introduced
  as a `Details:` label;
- the finding's **identity, severity, deduplication, canonical
  fix/action location, evidence/detection location, and publication
  anchor are exactly those of the structured inline rendering above** —
  structured and human inline are two renderings of one semantic
  finding, and the choice of rendering never moves the comment off the
  canonical fix/action location or into the review body (that is decided
  only by each Skill's placement policy, independent of voice);
- a **consolidated root-cause finding** still names every affected call
  path in the prose — the re-voicing never drops a manifestation site.

## Canonical summary-pointer rendering

Used when the finding's full representation is published elsewhere (for
example, a GitHub inline comment) and the review body only needs to
reference it — never both in full. The `` `<path>:<line-or-range>` `` is
the canonical fix/action location (or the best-known coordinate with the
unresolved annotation when the fix/action location is unresolved):

```markdown
- **<severity> — <short title>**
  `<path>:<line-or-range>`
```

For a **consolidated root-cause finding** the pointer adds a one-line
affected-locations count or list so the reader still sees the finding
reaches several sites:

```markdown
- **<severity> — <short title>**
  `<shared-cause path>:<line-or-range>` — affects `<path:line>`, `<path:line>`, …
```

## Rules

These are the rendering-specific rules; the finding-field and
quality-contract rules are in [`finding.md`](finding.md), "Rules".

- the opt-in **human inline rendering** (`human_inline_findings`,
  `github-pr-review` inline surface only) re-voices an inline finding as
  senior-engineer prose without `Evidence:` / `Impact:` / `Fix:` labels;
  it keeps the severity in the heading, the full mandatory core, the
  evidence bar, and the finding's identity, severity, deduplication, and
  canonical location — a projection, never a weaker finding (see
  "Canonical human inline rendering");
- optional fields render only when populated — never as an empty or
  placeholder line (see [`finding.md`](finding.md), "Optional and
  surface-specific fields");
- a finding has exactly one authoritative full representation. If it is
  published in full at one location (e.g. inline), every other location
  uses the summary-pointer form instead of repeating the full finding.
