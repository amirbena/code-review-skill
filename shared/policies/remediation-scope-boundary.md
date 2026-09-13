# Shared Policy — Remediation-Scope Boundary

Applies identically to `local-code-review` and `github-pr-review`, in every
invocation mode. It owns the mandatory reasoning step that separates a
finding's validity/severity from *how much remediation the current
task/PR boundary must absorb*: the trigger, the three-part reasoning
sequence, the never-widens/never-shrinks-severity rule, and the worked
examples.

This is the remediation-scope sub-domain of
[`review-scope.md`](review-scope.md), which owns base review scope and
routes here. It builds on [`severity.md`](severity.md)'s mechanical
blocking derivation and feeds
[`remediation-guidance.md`](remediation-guidance.md)'s `Fix` direction. It
introduces no second scope model, no second evidence standard, and no
change to finding identity, deduplication, or the decision derivation
owned by [`root-cause-consolidation.md`](root-cause-consolidation.md) and
[`severity.md`](severity.md).

## The gap this closes

A reviewer can correctly identify a real risk and then over-expand the
requested remediation, pulling later-phase concerns — runtime
provisioning, CI orchestration, a broader architecture change — into the
current change's required fix. Depth of review reasoning must not
automatically imply depth of required implementation scope. The inverse
failure is just as real: suppressing a legitimate finding, or quietly
downgrading its severity, merely because its full remediation feels too
large for the current change. Neither is correct; this policy makes the
judgment explicit and mechanical instead of reviewer-by-reviewer.

## Three-part reasoning (mandatory, per material finding)

For every material finding — one that has already cleared the evidence
bar in [`evidence.md`](evidence.md) and is being reported — reason through
these three questions independently, in order:

1. **Validity and severity.** Is the finding valid, and what severity does
   it deserve? Unchanged, and owned solely by [`severity.md`](severity.md).
   This policy adds nothing to and removes nothing from that derivation.
2. **Is remediation required for the current change?** A finding can be
   valid and still not require a code change in the current change — for
   example, a documented, evidenced pre-existing limitation the current
   change does not worsen. When severity's mechanical blocking rule
   already requires a fix (P0/P1), remediation is required; this step
   never overrides that rule.
3. **How much of that remediation belongs inside the current task/PR
   boundary, versus should be surfaced as separate follow-up work?** This
   is the step this policy adds. Reason about it independently of
   severity: severity says how bad the finding is, not how much rewrite
   the current change owes it.

## Resolving question 3

Three outcomes are possible, and evidence — not preference for a smaller
diff or discomfort with a large one — decides which applies:

- **Bounded local fix is sufficient.** The current contract can be made
  correct with a fix scoped to the current change. Request that bounded
  fix as the finding's `Fix`. A broader design improvement may still be
  worth naming, but it is not required here.
- **Valid concern, broader remediation is separate follow-up.** The
  finding is real and evidenced, but making it fully "right" requires
  work outside the current change's realistic blast radius (runtime
  provisioning, cross-team coordination, a broader architecture change,
  work already tracked elsewhere). The `Fix` states the smallest
  correction that restores the current contract or, when even that is not
  applicable in-change, states that no in-change action is required; the
  broader concern is named as an explicit recommended follow-up per
  [`remediation-guidance.md`](remediation-guidance.md), never folded into
  `Fix` as if it were required now. This outcome never changes the
  finding's severity or the mechanical blocking decision: a P0/P1 still
  blocks on its bounded fix even when a related broader concern exists.
- **Broader work is genuinely required.** The current contract cannot be
  satisfied without the wider boundary change — there is no bounded local
  fix that actually resolves the finding. Here the broader work *is* the
  required remediation; do not defer it to a follow-up merely to keep the
  current change small, and do not understate it in `Fix` to make it look
  bounded when it is not.

Getting question 3 wrong in either direction is a defect: inflating `Fix`
into unrequested redesign is scope creep the same way an unrelated
refactor recommendation would be; deferring a fix the current contract
cannot do without is a false-clean signal.

## Worked examples

- **Blocking local defect + broader future concern.** An entrypoint
  violates an explicit failure contract (e.g., swallows a fatal
  initialization error instead of failing fast) — P1, blocking, fixed with
  a bounded correction in the entrypoint. Production-grade runtime
  provisioning for that same subsystem would further improve resilience,
  but nothing in the current change requires it — a valid P2, reported as
  a recommended follow-up, not folded into the P1's `Fix` and not a reason
  to withhold or soften the P1.
- **Architectural finding whose minimal fix is sufficient.** A reviewer
  identifies a broader design weakness (a helper that should eventually
  become a shared service), but the current task's contract is fully
  satisfied by a bounded local correction. The finding requests that
  bounded fix and separately surfaces the larger redesign as a follow-up
  recommendation — it does not require the redesign to close the finding.
- **Broader work genuinely required.** The current change cannot satisfy
  its own contract without a wider boundary change (e.g., a new
  capability requires a schema/interface change that the current change's
  narrower attempt cannot express correctly). The reviewer states that
  wider change as the required `Fix` and does not defer it to a follow-up
  merely to keep the current change smaller — doing so would be a false
  claim that the narrower fix resolves the finding.

## Non-goals and ownership boundary

- This policy never changes severity definitions, the mechanical blocking
  derivation, or finding identity/deduplication — those remain solely
  owned by [`severity.md`](severity.md) and the finding-identity/lifecycle
  model.
- This policy does not duplicate
  [`root-cause-consolidation.md`](root-cause-consolidation.md): that policy
  decides whether several observed failures are one finding or several;
  this policy decides, for one already-identified finding, how much of its
  remediation the current change must absorb. Apply root-cause
  consolidation first when it applies, then apply this reasoning to the
  resulting finding set.
- No new user-facing invocation flag. The distinction is inferred from the
  finding's own evidence, the current task/PR boundary, and repository
  context — the same way other review-scope judgments already are.
- Presentation options (`human_review_output` / `senior_mode` and related
  flags) may change how the required fix and its follow-up recommendation
  are worded; they own none of this reasoning and never change which
  outcome applies, per [`invocation-options.md`](invocation-options.md).
