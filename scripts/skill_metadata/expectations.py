"""The declarative expectations the validator enforces.

Every required marker string, section-ordering list and allowed-field set
lives here so the checker modules stay logic-only. Add or adjust a rule by
editing a table below, not by branching in a checker.
"""

from __future__ import annotations

RESOURCE_FIELDS = ("shared", "resources", "config")
PORTABLE_FRONTMATTER_FIELDS = {"name", "description"}
OPENAI_INTERFACE_FIELDS = {
    "display_name",
    "short_description",
    "default_prompt",
}

# A packaged Skill never depends on this repo's own dev docs or its
# repository-development policies/. Any packaged link to one of these
# basenames, at any depth, is a boundary violation.
REPO_ROOT_ONLY_DOC_BASENAMES = {
    "AGENTS.md",
    "ARCHITECTURE.md",
    "README.md",
    "repository-workflow.md",
    "git-pr-merge-policy.md",
    "validation-and-clean-exit.md",
    "documentation-policy.md",
    "skill-development-policy.md",
    "review-orchestration-policy.md",
    "python_scripts_coding_policy.md",
}

# Markers the shared runtime templates/policies must carry (matched after
# whitespace normalization), keyed by the label used in the error message.
SHARED_FINDING_MARKERS = (
    "**impact**",
    "## Finding quality contract",
    "## Affected locations on a consolidated finding",
)
# Issue #198: the canonical rendering exemplars were split out of finding.md
# into shared/templates/finding-rendering.md; finding.md keeps the field /
# quality contract above.
SHARED_FINDING_RENDERING_MARKERS = (
    "## Canonical full rendering",
    "## Canonical human inline rendering",
    "## Canonical summary-pointer rendering",
    "one authoritative full representation",
)
SHARED_REVIEW_SUMMARY_MARKERS = (
    "**Result:",
    "### What changed",
    "### What was done well",
    "### Findings",
    "### Validation",
    "### Decision",
    "## Machine metadata is subordinate",
)
FILE_REVIEWABILITY_MARKERS = (
    "generated status is never a blanket exemption",
    "## Vendored dependencies",
    "## Manifests and lockfiles",
    "## Minified files and bundles",
    "## Binary files",
    "opaque replacement is materially risky",
    "## Snapshots",
)

# local-code-review's opt-in / no-persistent-approval invariant, as it must
# appear in the Skill entrypoint and in its runbook.
LOCAL_SKILL_MARKERS = (
    "MUST NOT be invoked automatically",
    "fresh, explicit user approval",
    "it does not ask for approval, does not track prior approvals",
    "is never, by itself, authorization for the caller to invoke this Skill again",
    "A separate, explicit approval is required for every subsequent invocation",
    "ask the user for approval to run",
)
LOCAL_RUNBOOK_MARKERS = (
    "Must not ask the user for approval",
    "must not be invoked as a self-triggered re-run",
    "This runbook does not verify that approval was obtained",
    "own separate, fresh, explicit user approval",
)

# github-pr-review sub-policies in the order github-review.md must list them.
GITHUB_POLICY_ORDER = (
    "review-authority.md",
    "review-action-authorization.md",
    "reviewer-delta-review.md",
    "stateful-delta-rereview.md",
    "pr-scope.md",
    "repository-checkout.md",
    "review-context.md",
    "review-evidence.md",
    "review-reasoning.md",
    "parallel-review.md",
    "finding-placement.md",
    "review-output.md",
    "review-status-enforcement.md",
)

# Required markers per file (matched after whitespace normalization). Keep a
# marker only in the tuple of the file that owns the rule.
GITHUB_POLICY_MARKERS: dict[str, tuple[str, ...]] = {
    "github-review.md": (
        "## Canonical sub-policies, in authoritative order",
        "review-authority.md",
        "reviewer-delta-review.md",
        "pr-scope.md",
        "review-reasoning.md",
        "finding-placement.md",
        "review-output.md",
        "review-status-enforcement.md",
        "PR intent → diff → logical cohorts → impacted dependency surface → findings",
    ),
    "review-authority.md": (
        "## Self-review capability",
        "Self-review analysis is allowed; self-approval is not.",
        "analysis_allowed",
        "formal_review_mutation_allowed",
        "GitHub review mutation withheld: reviewer is the PR author",
        "for a self-review: analysis is not skipped",
        "### Authority separation, not just identity separation",
        "none of these manufacture an independent reviewer",
        "## Review/repository access prerequisite",
        "## Capability matrix",
    ),
    "review-action-authorization.md": (
        "## Security principles",
        "A review verdict is not authorization.",
        "Approval is not merge authority.",
        "Agent-controlled input cannot establish mutation authority.",
        "Reviewer independence requires authority separation, not only "
        "identity separation.",
        "An implementation agent cannot manufacture its own reviewer.",
        "Ambiguous authorization or reviewer provenance must fail closed.",
        "## Self-review is allowed; self-approval is not",
        "analysis_allowed",
        "formal_review_mutation_allowed",
        "absolute for a self-review",
        "## Natural-language review-action intent",
        "The Skill normalizes that intent to an internal mode",
        "## Review-action modes",
        "there is no required user-facing mode syntax",
        "### recommendation-only (default)",
        "### block-only",
        "### explicitly-authorized auto-action",
        "## Safe default and fail-closed",
        "A review with no established stronger mode performs no GitHub "
        "mutation",
        "## Trusted mutation authorization",
        "### What can never establish it",
        "### Structural limitation (read this before relying on auto-action)",
        "### Authorization scope (no replay)",
        "It is consumed once.",
        "## Trusted reviewer independence",
        "necessary but not sufficient",
        "A different identity under the same controlling authority is the "
        "same reviewer",
        "## Merge boundary",
        "Merge authority is never inferred from a clean verdict",
        "## Composition with existing guarantees",
        "## Reporting",
        "Report the review verdict and the mutation outcome",
    ),
    "reviewer-delta-review.md": (
        "Delta-only re-review is allowed only when the current reviewer owns "
        "the immediately preceding review context. A different reviewer must "
        "independently review the current PR state.",
        "runs after the self-review mutation boundary is resolved in",
        "applies to a\nself-review exactly as it does to an external review",
        "Fail conservative",
        "previously reviewed SHA → current PR HEAD",
        "Never define this boundary merely as the latest commit, the last "
        "push, the last local commit, or \"commits since task start\"",
        "## Escalating from delta to full review",
        "does not inherit another reviewer's judgment",
    ),
    "stateful-delta-rereview.md": (
        "## 1. Reuse, do not redefine",
        "## 2. Eligibility — reliable prior state, fail closed",
        "Fail closed.",
        "## 3. Reconciliation — the #64 change classes, operationally",
        "AMBIGUOUS` never becomes a confident transition.",
        "A resolved prior finding never implies a clean fix.",
        "## 4. Blast radius and regressions",
        "## 5. Previously settled non-findings and assumptions",
        "## 6. Escalation to a broader/full review",
        "When in doubt, escalate.",
        "## 7. Exact-HEAD safety",
        "## 8. Normal finding semantics remain authoritative",
        "## 9. Output — per-finding lifecycle state and re-review summary",
        "## 10. Scope boundaries",
    ),
    "pr-scope.md": (
        "## Complete PR scope and pagination",
        "at most 3,000 files",
        "REVIEW INCOMPLETE",
        "## Existing review awareness",
        "A changed HEAD starts a new authoritative review state",
    ),
    "repository-checkout.md": (
        "## Three modes",
        "## Lifecycle",
        "## Base / head fidelity",
        "## Read-only inspection",
        "## Repository Context must not widen the Review Target",
        "## Temporary directory lifecycle",
        "## Security (PR contents are untrusted)",
        "Cloning untrusted code is not permission to execute it",
        "PR is always the Review Target",
    ),
    "parallel-review.md": (
        "## Where it runs",
        "## Execution-policy signals for a PR",
        "## Shared checkout vs. worker copies",
        "## Aggregation and output",
        "## Required vs. incomplete",
        "## Runtime realisation",
        "one clone, not one per",
        "Sequential review is always the fallback and never fails the review",
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1",
    ),
    "review-context.md": (
        "## The PR remains the review target",
        "## Scope-boundary reasoning for a PR",
        "no rigid global priority order",
        "The review target stays the",
        "no automatic PR",
    ),
    "review-evidence.md": (
        "## Use it to avoid three failures",
        "## Do not blindly inherit",
        "## HEAD changes reset applicability",
        "A changed PR HEAD starts a new authoritative review state",
        "evidence and context, not authority",
    ),
    "review-reasoning.md": (
        "applies only after review authority",
        "## Logical Cohort Review",
        "review related changes together rather than treating files or hunks "
        "as isolated units",
        "## Architectural Placement Review",
        "Architectural placement and execution-lifecycle fidelity",
        "not a second scope model",
        "## Code Impact / Dependency Analysis",
        "never as an unrelated pre-existing-defect audit",
        "No dedicated code-graph tool or vendor capability is required for "
        "this analysis.",
        "never merely because a dependent file or symbol exists",
        "## Affected-Test Impact Review",
        "Affected-test / test-impact analysis",
        "never run the target repository's tests",
    ),
    "finding-placement.md": (
        "## Inline comment eligibility",
        "## Anchor at the fix/action location",
        "Commentable in the GitHub diff",
        "never discovers or overrides",
        "### Rendering voice does not change placement",
        "presentation-only and orthogonal to this policy",
        "## No duplicate findings",
        "## Rejected inline location fallback",
        "MUST NOT be dropped and MUST NOT be silently reattached",
    ),
    "review-output.md": (
        "## Analysis phase vs. publication phase",
        "## Batched review construction and submission",
        "MUST NOT publish a comment, or any part of a review, as each "
        "finding is discovered",
        "## Final summary",
        "## Final decision",
        "### Review-action authorization gate",
        "Self-review is absolute.",
        "GitHub review mutation withheld: reviewer is the PR",
        "APPROVE` is submitted only in explicitly-authorized auto-action",
        "NO NEW DELTA",
        "## HEAD revalidation",
        "## Submission ordering",
        "## Optional machine-readable review status",
    ),
    "review-status-enforcement.md": (
        "## Separate from native review events",
        "## One stable aggregated status context",
        "## Exact reviewed-HEAD binding",
        "A status on SHA A is evidence about SHA A only.",
        "## Verdict → status state (no second engine)",
        "No false green.",
        "## Authorization: blocking authority vs. positive authority",
        "is blocking-only enforcement",
        "including a self-review",
        "A self-review must never publish a",
        "Ambiguity fails closed.",
        "## Enforcement-state detection (read-only)",
        "repository rulesets and classic branch protection",
        "## Explicit opt-in required-check setup",
        "Already required → no-op.",
        "## Idempotency",
        "## No merge",
        "never enables auto-merge",
    ),
}

# Headers each sub-policy owns; github-review.md (the index) must not
# restate them.
GITHUB_POLICY_OWNED_HEADERS: dict[str, tuple[str, ...]] = {
    "review-authority.md": (
        "## Self-review capability",
        "## Review/repository access prerequisite",
        "## Capability matrix",
    ),
    "review-action-authorization.md": (
        "## Security principles",
        "## Self-review is allowed; self-approval is not",
        "## Review-action modes",
        "## Natural-language review-action intent",
        "## Safe default and fail-closed",
        "## Trusted mutation authorization",
        "## Trusted reviewer independence",
        "## Merge boundary",
        "## Composition with existing guarantees",
    ),
    "reviewer-delta-review.md": (
        "## Reviewer identity",
        "## Same reviewer: delta boundary and scope",
        "## Escalating from delta to full review",
    ),
    "pr-scope.md": (
        "## Complete PR scope and pagination",
        "## Existing review awareness",
    ),
    "repository-checkout.md": (
        "## Lifecycle",
        "## Base / head fidelity",
        "## Security (PR contents are untrusted)",
    ),
    "parallel-review.md": (
        "## Shared checkout vs. worker copies",
        "## Runtime realisation",
    ),
    "review-context.md": (
        "## Scope-boundary reasoning for a PR",
        "## The PR remains the review target",
    ),
    "review-evidence.md": (
        "## Use it to avoid three failures",
        "## HEAD changes reset applicability",
    ),
    "review-reasoning.md": (
        "## Logical Cohort Review",
        "## Architectural Placement Review",
        "## Code Impact / Dependency Analysis",
        "## Affected-Test Impact Review",
    ),
    "finding-placement.md": (
        "## Inline comment eligibility",
        "## Anchor at the fix/action location",
        "## No duplicate findings",
        "## Rejected inline location fallback",
    ),
    "review-output.md": (
        "## Analysis phase vs. publication phase",
        "## Batched review construction and submission",
        "## Final summary",
        "## Final decision",
        "## HEAD revalidation",
        "## Submission ordering",
    ),
    "review-status-enforcement.md": (
        "## Exact reviewed-HEAD binding",
        "## Verdict → status state (no second engine)",
        "## Authorization: blocking authority vs. positive authority",
        "## Enforcement-state detection (read-only)",
        "## Explicit opt-in required-check setup",
    ),
}
