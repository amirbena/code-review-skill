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
  verdict, the GitHub review state, inline comments, any machine-readable
  status, or the order in which a review's artifacts are published: in both
  modes `github-pr-review` keeps the final human-facing summary as the last
  review-owned publication of the run (its `review-output.md`, "Submission
  ordering").

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
  `concise review comment`;
- negative: `keep the full summary`, `keep the default summary`, `do not
  shorten the review`, `don't shorten the review`.

This phrase set is exhaustive: it is the whole vocabulary for this option.
Anything outside it — “make it nicer”, “be brief”, “tighten it up”, a
question about the option — is ambiguous and does not set the flag. When both
an affirmative and a negative phrasing appear, the values conflict and the
option falls through to the Skill default, exactly like the other options.

Resolve each option independently with this precedence:

```text
explicit canonical false
> explicit canonical true
> one unambiguous natural-language value
> Skill default
```

Conflicting natural-language values are ambiguous and fall through to the
Skill default. A canonical value resolves only its own option; text about one
option never changes another.

## Invocation isolation and mediation parity

Start every invocation from the receiving Skill's defaults and normalize only
the current invocation. Never reuse normalized values from an earlier review,
including a re-review in the same conversation.

A caller or orchestrating agent may forward the user's current-turn text or
already-normalized canonical assignments. Both routes apply this same policy
and must produce identical option values. An agent's paraphrase is not a new
source of intent and must not broaden or persist the user's request.

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
