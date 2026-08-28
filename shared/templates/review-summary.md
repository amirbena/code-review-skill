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

<one or two sentences: scope reviewed, e.g. files/commit or PR HEAD>

### What changed
<concise, concrete summary of what the change implements and its intent>

### What was done well
- **<theme>:** <concrete, evidence-backed strength>
- **<theme>:** <concrete, evidence-backed strength>

### Findings
<one of:>
- "No P0, P1, or P2 findings."
- for each finding: either its full rendering (per
  [`finding.md`](finding.md), "Canonical full rendering") when this is
  its one authoritative location, or its summary-pointer rendering (per
  [`finding.md`](finding.md), "Canonical summary-pointer rendering") when
  its full form was already published at another location (e.g. a GitHub
  inline comment) — never both. Findings use the compact, field-oriented
  contract in [`finding.md`](finding.md) — a scannable block per finding,
  not a multi-paragraph essay; a longer `Details` field only for the
  cases [`finding.md`](finding.md), "When a longer explanation is
  justified" allows.

### Validation
- <validation actually observed, or explicitly noted as not executed>

### Decision
**<decision label>**

<one-sentence rationale tied to the findings above>
```

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
- **What changed** — a concrete implementation summary, not a diff dump.
- **What was done well** — only concrete, evidence-backed strengths.
  Omit the section (or keep it to one line) rather than invent generic
  praise when nothing specific stands out.
- **Findings** — the aggregate view. Every P0/P1/P2 finding is
  represented exactly once, in exactly one authoritative form (full or
  summary-pointer — never both), per
  [`finding.md`](finding.md), "Rules," and rendered with the compact,
  field-oriented finding contract in [`finding.md`](finding.md) so the
  per-finding shape and this summary read as one coherent contract. This
  section does not repeat implementation detail already covered under
  "What changed."
- **Validation** — reports only what was actually observed (tests run,
  packaging performed, links checked, etc.). When something could not be
  executed, say so explicitly rather than implying it passed.
- **Decision** — an unambiguous label plus one sentence tying it to the
  findings. Never leave the reader to compute the outcome from raw P0/P1/P2
  counts. The decision itself is derived mechanically from blocking
  severities per [`severity.md`](../policies/severity.md), "Decision
  derivation (mechanical)" — it is never an independent judgment call
  that can contradict that derivation, and a non-blocking finding (P2)
  never produces a blocking decision no matter how strongly it is
  recommended.

## Machine metadata is subordinate

Internal/orchestration state (reviewed HEAD or base/head SHAs, raw
P0/P1/P2 counts, a normalized machine decision code, internal finding
identifiers, or other automation state) is never part of the primary
human-facing body above. Where publishing it is genuinely useful to a
caller or automation, append it after the human-facing body, clearly
subordinate — always last, always visually secondary to the Result →
... → Decision body above it.

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
re-review, audit). If nothing needs it, omit the section entirely rather
than padding the review with unused state.
