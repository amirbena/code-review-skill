---
name: review-suggestions
description: Adds a few non-blocking P2 suggestions on maintainability, design and hygiene. Never P0 or P1. Use when you want improvement ideas beyond blocking defects.
---

# review-suggestions

Adds a short list of non-blocking suggestions to a `review-core` review. It
emits P2 only, so it can never change the decision: `review-core`'s decision
rule counts P0 and P1, and P2 never blocks. It never lowers, removes or
re-rates an existing P0 or P1, never clears a `REVIEW INCOMPLETE` trigger, and
never turns a blocking or incomplete decision into a clean one.
It never changes severity, the decision rule, the `REVIEW INCOMPLETE`
triggers or S1–S5 and S10; those are `review-core`'s.

## Entry contract

- Runs only after `review-core` has run on the same target in this run, and
  only when selected under `review-core`'s "Mode" (S6, stated there).
- Needs no input beyond the target and the Core's findings.
- Read-only, by `review-core`'s S1 and S10.

## Procedure

1. **Look for suggestions** in the changed code, after the Core's review:
   - *maintainability* — duplication the change introduces, a function or
     file that now does several jobs, unclear naming, dead code the change
     leaves behind;
   - *design* — a localized weakness: a responsibility in the wrong place, a
     leaky abstraction, a fragile coupling the change adds;
   - *hygiene* — a lower-risk test gap, misleading documentation or
     comments, an inconsistency with the repository's own conventions.
2. **Keep only the most valuable few: at most five.** Prefer a suggestion
   that removes a future defect or a real cost. Drop style, formatting,
   naming taste and anything a linter or formatter owns. Drop anything that
   is already a Core finding or a pre-existing issue the change does not
   touch.
3. **Add each as a finding** in `review-core`'s shape (`location`,
   `evidence`, `impact`, `fix` included), always severity **P2**, numbered
   after the Core's findings and the other mini-skills'. The evidence rule
   is the Core's: cite only what you read (S4).
4. **Never emit P0 or P1.** When a candidate looks serious enough for one,
   do not raise it here: report it as a finding under the Core's bar when
   it meets it, else drop it.

When nothing meets the bar, add nothing and say so in "Additional
expertise". Silence is a valid result.
