# Severity descriptions

## What it does

Expands `github-pr-review`'s severity code in every finding-headline
surface it owns — the summary-pointer line, the fallback full-rendering
heading, the structured inline `[<severity>]` form, and the human
inline/full headings — from the bare `P0` / `P1` / `P2` code to that code
plus a short, canonical parenthetical:

```text
P0 (Critical)
P1 (Blocking)
P2 (Non-Blocking)
```

**Compact (`P0` / `P1` / `P2`, no parenthetical) is the default.** The
parenthetical is opt-in. Either way, the complete headline — severity,
the description when enabled, and title — renders as one emphasized unit
on every surface: never a title emphasized separately from its severity.

## When it is useful

- You are new to this Skill's `P0`/`P1`/`P2` convention and want the
  meaning spelled out at a glance instead of looking it up.
- You are pasting a review body somewhere without the surrounding
  context that would otherwise make `P1` legible on its own.

## Which Skill(s)

`github-pr-review` only. `local-code-review` defines no severity legend
at all and renders the bare `[P0]` / `[P1]` / `[P2]` form regardless of
this option's value — it is normalized for cross-Skill parity only and
has no effect there.

## Default, conditional, or requested

**Explicitly requested, in natural language — there is no CLI flag.**
Normalized internally to the `include_severity_description` option
(default `false`):

- affirmative: *"include severity descriptions"*, *"show severity
  descriptions"*, *"show blocking/non-blocking labels"*;
- negative: *"keep severity compact"*, *"don't include severity
  descriptions"*, *"show only P0/P1/P2"*.

The complete authoritative phrase set lives in
[`shared/policies/invocation-options.md`](../../shared/policies/invocation-options.md),
"`include_severity_description` phrasings". Anything outside that
vocabulary is ambiguous and does **not** set it. A forwarded canonical
`include_severity_description=true|false` assignment is also honored.

## How to invoke it

```text
review PR #812 and show severity descriptions
review #812; keep severity compact
```

The option is normalized from the **current invocation only** — it never
carries over to a later review or re-review in the same conversation.

## Limitations & safety boundaries

- **Presentation only.** It controls **only** whether the parenthetical
  renders. It never affects whether severity itself is shown, whether
  the finding headline is emphasized, `P0`/`P1`/`P2` semantics, the
  blocking rule, or the mechanically derived verdict — all owned by
  [`shared/policies/severity.md`](../../shared/policies/severity.md) and
  unchanged in both modes.
- It composes independently with
  [human-style output](human-review-output.md): the parenthetical, when
  enabled, renders inside whichever surface `human_review_output` /
  `human_inline_findings` selects, with no other change to that surface's
  voice or shape.

## Canonical semantics

[`shared/policies/invocation-options.md`](../../shared/policies/invocation-options.md),
"`include_severity_description` phrasings" ·
[`skills/github-pr-review/policies/review-output.md`](../../skills/github-pr-review/policies/review-output.md),
"Reader-visible severity legend" and "Emphasized-headline contract, by
surface" ·
[`shared/templates/finding-rendering.md`](../../shared/templates/finding-rendering.md).
