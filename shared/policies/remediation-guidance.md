# Policy — Remediation Guidance

Applies to evidence-backed findings from both Code Review Skills. Guidance is
advisory output: it does not change finding identity, severity, deduplication,
Existing Review Evidence reconciliation, or the mechanically derived verdict.
It grants no ability to edit, patch, commit, push, branch, merge, or otherwise
mutate source or repository state.

## Evidence-grounded direction

When useful, give a concise recommended direction that addresses the evidenced
cause. This is the content of a finding's **Fix** field in
[`../templates/finding.md`](../templates/finding.md); the shorter field label
does not change what this policy governs. Prefer the canonical owner of an
invariant over patches at each symptom.
The root-cause and model-completeness rules in
[`review-scope.md`](review-scope.md) govern grouping: one structural finding
gets one coherent remediation direction, not one instruction per manifestation.

For an external package, distinguish local misuse from an upstream defect. Fix
local misuse locally. Recommend an upgrade only when a fixed version or range is
verified, including evidenced compatibility or migration validation. When no
fixed version is verified, say to verify upstream availability or apply a
justified mitigation if upgrading is blocked; never invent a version.

## Skill-specific detail

This policy permits different delivery detail. `local-code-review` may, only by
the explicit `include_fix_prompt` opt-in, append a coding-agent-ready implementation prompt to an
existing actionable finding. `github-pr-review` remains reviewer-facing and
uses concise recommended directions; it does not emit the local full prompt.
Neither form may introduce unsupported architecture or arbitrary implementation
requirements.
