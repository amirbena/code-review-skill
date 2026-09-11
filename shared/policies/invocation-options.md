# Policy — Invocation Option Normalization

Both review Skills normalize explicit current-invocation wording into the
same canonical boolean options before review reasoning begins. Normalization
is deterministic and invocation-scoped; it is not general-purpose natural
language interpretation.

## Canonical options

- `include_fix_prompt` — local-only, default `false`; controls the optional
  coding-agent implementation prompt described in
  [`remediation-guidance.md`](remediation-guidance.md).
- `include_fix_guidance` — default `true`; controls optional remediation
  elaboration beyond the canonical finding's concise `Fix` field. It never
  removes or weakens that mandatory field.
- `include_finding_details` — controls presentation of a populated `Details`
  field. The local Skill defaults it to `true`; the GitHub Skill defaults it
  to `false`.
- `human_review_output` — default `false` for both Skills; selects a concise,
  senior-engineer-voice rendering of the **final human-facing review summary**
  in place of the default structured summary shape. The user-facing contract
  is natural language (see "Deterministic normalization"); there is no
  required CLI-style flag such as `--human-review-output`, though a forwarded
  canonical `human_review_output=true|false` assignment is still honored for
  mediation parity. It changes only the wording of the final summary — never
  the findings, their severity, deduplication, the mechanically derived
  verdict, the GitHub review state, the semantic content of inline comments,
  any machine-readable status, or the order in which a review's artifacts are
  published: in both modes `github-pr-review` keeps the final human-facing
  summary as the last review-owned publication of the run (its
  `review-output.md`, "Submission ordering"). By its companion option's
  derived default it also selects `human_inline_findings` (below), so
  enabling senior mode yields a coherent human-facing review end to end
  without a second request. For `github-pr-review` specifically, this option
  additionally selects the human-voiced rendering of any finding rendered in
  full **in the review body** rather than as an inline comment — passive
  review findings (passive has no inline surface), and an active-review
  finding with no valid inline anchor — via the **human full rendering** in
  [`../templates/finding-rendering.md`](../templates/finding-rendering.md),
  "Canonical human full rendering"; see that Skill's own
  `policies/review-output.md` for the exact wiring. This is a
  `github-pr-review`-specific extension of the option's effect, stated there,
  not a change to the option's shared default or its natural-language
  contract; `local-code-review` has no inline/body split and is unaffected.
- `human_inline_findings` — has **no fixed Skill default**: its value is
  derived as `explicit_value ?? human_review_output` (see
  "`human_inline_findings` derived default and phrasings"). It selects the
  same concise, senior-engineer-voice rendering for **GitHub inline review
  findings** that `human_review_output` selects for the final summary — a
  short heading that keeps the `P0` / `P1` / `P2` severity and names the
  finding, then compact prose in place of the `Evidence:` / `Impact:` /
  `Fix:` labelled block (see
  [`../templates/finding-rendering.md`](../templates/finding-rendering.md),
  "Canonical human inline rendering"). It acts only where a Skill publishes inline review
  comments — `github-pr-review`; `local-code-review` normalizes it for
  direct/mediated parity but has no inline-comment surface, so it has no
  effect on local output. Like the other options it is presentation only:
  it never changes finding detection, severity, identity, deduplication,
  evidence or remediation requirements, the mechanically derived verdict,
  the GitHub review state, the batched single submission, the canonical
  fix/action location, the evidence/detection location, the publication
  anchor (`github-pr-review`'s `finding-placement.md` is unchanged and
  remains authoritative for placement), or publication ordering — only the
  wording of an inline finding.

Options affect presentation only. They never change review scope, evidence,
finding identity, severity, deduplication, decision derivation, mutation
authority, approval, HEAD/SHA validation, or publication ordering.

## Deterministic normalization

For each allow-listed option, inspect only the caller's current invocation.
Recognize these explicit forms, case-insensitively, with spaces, hyphens, and
underscores treated as equivalent inside the option name:

- canonical assignment: `include_fix_prompt=true` or
  `include_fix_prompt=false`;
- an affirmative option name: `include_fix_prompt`, `include fix prompt`, or
  `include-fix-prompt`;
- an explicit affirmative request: `include fix prompt`, `give me a fix
  prompt`, `include fix guidance`, or `show finding details`;
- an explicit negative request: `do not include a fix prompt`, `no fix
  guidance`, or `hide finding details`.

The finite vocabulary is the four canonical option concepts: `fix prompt`,
`fix guidance`, `finding details`, and `human review output`. Ordinary
mentions, questions about an option, quoted examples, and vague requests such
as “make it helpful”, “be detailed”, or “make it nicer” are ambiguous and do
not set a flag. Do not use sentiment, urgency, severity, prior turns, or a
general NLP classifier to infer a value.

### `human_review_output` phrasings

Because this option is normally requested conversationally rather than by
name, it additionally recognizes a small, fixed set of explicit phrasings
(case-insensitively, whitespace-flexible), alongside the canonical
`human_review_output=true|false` assignment and the bare option name
(`human_review_output`, `human review output`, `human-review-output`):

- affirmative: `shorter and more human`, `more human and shorter`, `like a
  senior engineer`, `as a senior engineer`, `concise review comments`,
  `concise review comment`, `senior review`, `senior code review`,
  `senior pr review`, `review this as a senior`;
- negative: `keep the full summary`, `keep the default summary`, `do not
  shorten the review`, `don't shorten the review`, `structured format`,
  `structured review`.

This phrase set is exhaustive: it is the whole vocabulary for this option.
Anything outside it — “make it nicer”, “be brief”, “tighten it up”, a bare
`as a senior` with no `review this` / `senior review` framing, a question
about the option — is ambiguous and does not set the flag. When both
an affirmative and a negative phrasing appear, the values conflict and the
option falls through to the Skill default, exactly like the other options.

### `human_inline_findings` derived default and phrasings

`human_inline_findings` has no fixed Skill default of its own. After every
other option is resolved for the current invocation, it is set to:

```text
human_inline_findings = explicit_value ?? human_review_output
```

— the explicitly resolved value when this invocation set one, otherwise the
already-resolved value of `human_review_output`. So enabling senior mode
("review it like a senior engineer") gives a coherent human-facing review —
summary *and* inline findings — with no second request, and the sub-option
is only stated explicitly to opt **out**, or to opt in on its own.

An explicit value always wins over the derived default, in either direction
and independently of `human_review_output`:

- `human_review_output=false` + `human_inline_findings=true` → structured
  summary, human-rendered inline findings;
- `human_review_output=true` + `human_inline_findings=false` → human
  summary, structured `[<severity>] / Evidence / Impact / Fix` inline
  findings.

Recognized explicit forms (case-insensitively, whitespace-flexible),
alongside the canonical `human_inline_findings=true|false` assignment and
the bare option name (`human_inline_findings`, `human inline findings`,
`human-inline-findings`):

- affirmative: `human inline findings`, `human inline comments`;
- negative: `keep the structured inline comments`, `keep the structured
  inline findings`, `keep the inline comment template`.

This phrase set is exhaustive for this option. Anything outside it is
ambiguous and does not set it; the derived default then applies. When both
an affirmative and a negative phrasing appear, the values conflict and the
option falls through to the derived default, exactly like the other options
fall through to their Skill default.

Resolve each option independently with this precedence:

```text
explicit canonical false
> explicit canonical true
> one unambiguous natural-language value
> Skill default
```

For `human_inline_findings` the last rung is the derived default
(`human_review_output`'s resolved value), applied after every other option
is resolved. Conflicting natural-language values are ambiguous and fall
through to that last rung. A canonical value resolves only its own option;
text about one option never changes another (the `human_inline_findings`
derived default is not "another option changing it" — it is this option's
defined default, used only when this invocation set no explicit value).

## Invocation isolation and mediation parity

Start every invocation from the receiving Skill's defaults and normalize only
the current invocation. Never reuse normalized values from an earlier review,
including a re-review in the same conversation.

A caller or orchestrating agent may forward the user's current-turn text or
already-normalized canonical assignments. Both routes apply this same policy
and must produce identical option values. An agent's paraphrase is not a new
source of intent and must not broaden or persist the user's request.

**Offering, never applying, a prior value.** A Skill may surface an earlier
invocation's resolved `human_review_output` value as a *recommended choice*
when asking the user an explicit presentation question (for example,
`github-pr-review`'s "publish a previously produced passive review" case in
its own `policies/review-output.md`). This is not "reusing" a normalized
value in the sense this section forbids: nothing is set from it until the
user answers, and the answer itself is current-invocation text normalized
like any other. Silently applying the prior value without asking remains
forbidden.

## Finding-detail precedence

`include_finding_details` controls whether an already-populated, justified
`Details` field is rendered. It never creates details and never removes any
canonical field. Resolve visibility per finding:

```text
finding-level decision > invocation option > Skill default
```

The GitHub reviewer may set a finding-level decision to `true` when expanded
technical detail is materially needed to understand or verify concurrency,
security, cross-file behavior, a subtle invariant, or evidence requiring brief
context. It may set `false` when the detail would only repeat the concise
problem, impact, or fix. The local reviewer may use the same per-finding
decision, but normally relies on its `true` default. A finding-level override
is presentation metadata, not a new canonical finding field.
