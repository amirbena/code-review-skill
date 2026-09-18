"""Test-only reference fixtures for the private Reviewer Brief benchmark
(Issue #309, depends on #304:
skills/github-pr-review/policies/reviewer-brief.md and
skills/github-pr-review/templates/reviewer-brief.md).

Unlike the domain corpora under docs/benchmark/corpus/, the Reviewer
Brief has no representation in the `benchmark-case/v2` schema
(runtime_platform/benchmark/fixture-format.md): that schema's `expected` block is
findings/decision-shaped and has no field for a private prose artifact or
for a second, GitHub-bound output surface to compare it against. Rather
than extend that closed schema for a single caller-facing artifact (or
build a second, parallel fixture framework), this module follows the same
pattern as `benchmark_fixture.py` and friends in this directory: a
test-only, hand-authored reference model, documented in
docs/benchmark/corpus/reviewer-brief/README.md.

Each `ReviewerBriefCase` models one correct Reviewer Brief a real
`github-pr-review` invocation must be able to produce, *and* the
GitHub-bound artifact (review body + inline comments) the same invocation
would publish, so isolation between the two can be asserted directly
against both sides in one place -- never against the caller-facing object
alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ReviewerBriefCase:
    case_id: str
    covers: frozenset[str]
    mode: Literal["active", "passive"]
    human_review_output: bool
    decision: Literal["clean", "changes-required"]
    user_focus_input: str | None
    what_changed: str
    user_provided_focus_field: str
    manual_review_focus: tuple[str, ...]
    open_questions: tuple[str, ...] | None
    independent_focus_present: bool
    references_finalized_finding: bool
    forbidden_terms: tuple[str, ...] = field(default_factory=tuple)
    required_keywords: tuple[str, ...] | None = None
    pair_id: str | None = None
    github_review_body: str = ""
    github_inline_comments: tuple[str, ...] = field(default_factory=tuple)

    def brief_field_strings(self) -> tuple[str, ...]:
        """Every individually-renderable Reviewer Brief field value, for
        publication-isolation checks that must inspect fields, not just a
        vague full-text substring."""
        parts = [self.what_changed, self.user_provided_focus_field]
        parts.extend(self.manual_review_focus)
        if self.open_questions:
            parts.extend(self.open_questions)
        return tuple(parts)

    def full_brief_text(self) -> str:
        return "\n".join(self.brief_field_strings())


# --- 1. Clean PR, no user focus -------------------------------------------
CLEAN_NO_FOCUS = ReviewerBriefCase(
    case_id="clean-pr-no-user-focus",
    covers=frozenset(
        {
            "clean-pr-no-focus-what-changed",
            "clean-pr-no-focus-independent-manual-focus",
            "passive-review-brief-returned",
            "clean-review-useful-not-collapsed",
        }
    ),
    mode="passive",
    human_review_output=False,
    decision="clean",
    user_focus_input=None,
    what_changed=(
        "Adds a read-only `/healthz` endpoint that reports DB and cache "
        "connectivity and wires it into the existing readiness probe path."
    ),
    user_provided_focus_field="none provided",
    manual_review_focus=(
        "Confirm the probe's timeout budget matches the orchestrator's own "
        "liveness-check timeout so a slow dependency degrades gracefully "
        "instead of flapping the pod.",
        "Skim the new dependency check's error handling to ensure it "
        "classifies a transient timeout as degraded, not down.",
    ),
    open_questions=None,
    independent_focus_present=True,
    references_finalized_finding=False,
    github_review_body="REVIEW CLEAN\n\nNo findings.",
    github_inline_comments=(),
)

# --- 2. Trusted user focus, active review, findings present ---------------
TRUSTED_FOCUS_ACTIVE = ReviewerBriefCase(
    case_id="trusted-focus-active-review",
    covers=frozenset(
        {
            "trusted-focus-represented",
            "trusted-focus-plus-independent-focus",
            "active-review-brief-available",
            "active-review-no-leak",
            "findings-inform-focus-no-duplication",
        }
    ),
    mode="active",
    human_review_output=False,
    decision="changes-required",
    user_focus_input="Focus on backward compatibility and DynamoDB access patterns.",
    what_changed=(
        "Adds a new payment-instruction lookup path and changes retry "
        "eligibility before dispatch."
    ),
    user_provided_focus_field="Focus on backward compatibility and DynamoDB access patterns.",
    manual_review_focus=(
        "Confirm the new lookup preserves legacy ordering/visibility semantics.",
        "Inspect the query/index access pattern for partition concentration "
        "and pagination behavior.",
        "Re-check retry idempotency around the newly introduced state transition.",
    ),
    open_questions=None,
    independent_focus_present=True,
    references_finalized_finding=False,
    pair_id="payment-lookup-pair",
    required_keywords=(
        "legacy ordering",
        "query/index access pattern",
        "retry idempotency",
    ),
    github_review_body=(
        "## Summary\nChanges required.\n\n"
        "### F1 [P1] Retry eligibility check races with the new dispatch path\n"
        "- **Evidence:** `dispatch()` reads `retry_eligible` before the new "
        "lookup's write completes.\n"
        "- **Impact:** A retried payment can dispatch twice under load.\n"
        "- **Fix:** Read `retry_eligible` after the lookup's write is durable."
    ),
    github_inline_comments=(
        "F1 [P1] Retry eligibility check races with the new dispatch path "
        "-- read `retry_eligible` after the lookup's write is durable.",
    ),
)

# --- 3. Misleading / irrelevant user focus ---------------------------------
MISLEADING_FOCUS = ReviewerBriefCase(
    case_id="misleading-user-focus",
    covers=frozenset(
        {
            "misleading-focus-grounded",
            "misleading-focus-no-invented-finding",
            "findings-inform-focus-no-duplication",
        }
    ),
    mode="active",
    human_review_output=False,
    decision="changes-required",
    user_focus_input="Please focus your review on the CSS styling changes in this PR.",
    what_changed=(
        "Rewrites the session-token verification middleware to read the "
        "bearer token from a new header, replacing the previous "
        "cookie-based lookup."
    ),
    user_provided_focus_field="Please focus your review on the CSS styling changes in this PR.",
    manual_review_focus=(
        "Confirm the new header-based token lookup rejects a request when "
        "the header is absent, matching the previous cookie path's "
        "must-be-present behavior.",
        "Check that a client still sending only the legacy cookie is not "
        "silently authenticated without the new header during rollout.",
    ),
    open_questions=None,
    independent_focus_present=True,
    references_finalized_finding=False,
    forbidden_terms=("CSS", "styling"),
    github_review_body=(
        "## Summary\nChanges required.\n\n"
        "### F1 [P1] Legacy cookie path still authenticates without the new header\n"
        "- **Evidence:** `verify_session()` falls back to the cookie lookup "
        "whenever the new header is missing.\n"
        "- **Impact:** A pre-rollout client bypasses the new header "
        "requirement entirely.\n"
        "- **Fix:** Remove the cookie fallback once the header rollout "
        "completes, or require both during the transition."
    ),
    github_inline_comments=(
        "F1 [P1] Legacy cookie path still authenticates without the new "
        "header -- remove the fallback or require both during rollout.",
    ),
)

# --- 4. User focus conflicts with repository evidence ----------------------
CONFLICTING_FOCUS = ReviewerBriefCase(
    case_id="conflicting-user-focus",
    covers=frozenset({"conflicting-focus-repo-wins"}),
    mode="active",
    human_review_output=False,
    decision="changes-required",
    user_focus_input=(
        "This is a fully backward-compatible additive change; no existing "
        "API consumers are affected."
    ),
    what_changed=(
        "Removes the previously public `legacy_id` field from the "
        "`/v2/orders` response schema and replaces it with `order_ref`."
    ),
    user_provided_focus_field=(
        "This is a fully backward-compatible additive change; no existing "
        "API consumers are affected."
    ),
    manual_review_focus=(
        "Verify no existing consumer still reads `legacy_id` -- removing it "
        "is a breaking change regardless of how the change is described.",
        "Confirm a deprecation or migration path for `order_ref` is "
        "documented for API consumers.",
    ),
    open_questions=None,
    independent_focus_present=True,
    references_finalized_finding=False,
    forbidden_terms=("is a fully backward-compatible", "no existing API consumers are affected"),
    github_review_body=(
        "## Summary\nChanges required.\n\n"
        "### F1 [P1] Removing `legacy_id` is a breaking API change without a migration path\n"
        "- **Evidence:** `/v2/orders` no longer serializes `legacy_id`.\n"
        "- **Impact:** Existing consumers reading `legacy_id` will break.\n"
        "- **Fix:** Keep `legacy_id` for a deprecation window or document a "
        "migration path to `order_ref`."
    ),
    github_inline_comments=(
        "F1 [P1] Removing `legacy_id` is a breaking API change -- keep it "
        "for a deprecation window or document a migration path.",
    ),
)

# --- 5. Delta re-review: effective delta only ------------------------------
DELTA_RE_REVIEW = ReviewerBriefCase(
    case_id="delta-re-review-scope",
    covers=frozenset({"delta-review-effective-delta-only"}),
    mode="active",
    human_review_output=False,
    decision="clean",
    user_focus_input=None,
    what_changed=(
        "This delta fixes the retry-idempotency gap the previous review "
        "flagged and adds a regression test for it; no other files changed "
        "since the last review."
    ),
    user_provided_focus_field="none provided",
    manual_review_focus=(
        "Confirm the new regression test actually exercises the "
        "double-submit path the prior review's finding described, not "
        "just the happy path.",
        "Skim the idempotency-key check itself for the same off-by-one the "
        "prior review found, to confirm it is fully closed and not just "
        "narrowed.",
    ),
    open_questions=None,
    independent_focus_present=True,
    references_finalized_finding=False,
    # Concrete file paths touched only in earlier, out-of-scope review
    # rounds -- the literal artifacts a naive full-history re-synthesis
    # would plausibly name, not an arbitrary invented sentence. See
    # out_of_scope_terms_present() and its negative-canary coverage in
    # test_reviewer_brief_structural.py.
    forbidden_terms=(
        "auth/middleware.py",
        "db/schema_migration_003.py",
    ),
    github_review_body="REVIEW CLEAN\n\nNo findings in this delta.",
    github_inline_comments=(),
)

# --- 6. Stacked PR: effective owned layer only -----------------------------
STACKED_PR = ReviewerBriefCase(
    case_id="stacked-pr-effective-layer",
    covers=frozenset({"stacked-pr-effective-layer-only"}),
    mode="active",
    human_review_output=False,
    decision="changes-required",
    user_focus_input=None,
    what_changed=(
        "Layer 2 of 2 in the detected stack (`main -> #41 -> #52`) adds the "
        "client-side retry wrapper around the API introduced in #41; this "
        "brief covers only #52's owned delta against #41."
    ),
    user_provided_focus_field="none provided",
    manual_review_focus=(
        "Confirm the retry wrapper's backoff policy matches the rate-limit "
        "behavior #41 introduced in the underlying API.",
        "Spot-check that the wrapper's error classification does not retry "
        "a non-idempotent call introduced lower in the stack.",
    ),
    open_questions=None,
    independent_focus_present=True,
    references_finalized_finding=False,
    # Concrete identifiers from #41's own implementation -- the literal
    # artifacts a naive full-stack re-analysis would plausibly surface,
    # not an arbitrary invented sentence. See out_of_scope_terms_present()
    # and its negative-canary coverage in test_reviewer_brief_structural.py.
    forbidden_terms=(
        "RateLimiter.acquire",
        "#41's own diff",
    ),
    github_review_body=(
        "## Summary\nChanges required.\n\n"
        "### F1 [P2] Retry wrapper does not check idempotency before retrying\n"
        "- **Evidence:** `with_retry()` retries any raised exception.\n"
        "- **Impact:** A non-idempotent call from #41's API can be retried "
        "and double-applied.\n"
        "- **Fix:** Restrict retries to calls #41 marks idempotent."
    ),
    github_inline_comments=(
        "F1 [P2] Retry wrapper does not check idempotency before retrying.",
    ),
)

# --- 7. Large / partitioned PR: final aggregate only -----------------------
PARTITIONED_PR = ReviewerBriefCase(
    case_id="large-pr-partitioned-aggregate",
    covers=frozenset({"large-pr-aggregate-not-partition-notes"}),
    mode="active",
    human_review_output=False,
    decision="changes-required",
    user_focus_input=None,
    what_changed=(
        "A repository-wide rename of the `LegacyClient` interface to "
        "`PlatformClient`, touching call sites across the API, worker, "
        "and CLI packages, plus the corresponding config schema update."
    ),
    user_provided_focus_field="none provided",
    manual_review_focus=(
        "Spot-check that every call site's error-handling branch still "
        "compiles against the renamed interface's slightly different "
        "exception type.",
        "Confirm the config schema migration ships alongside the rename so "
        "a partially-deployed cluster doesn't read the old field name.",
    ),
    open_questions=None,
    independent_focus_present=True,
    references_finalized_finding=False,
    forbidden_terms=("Partition 1", "Partition 2", "Partition 3", "partition-internal note"),
    github_review_body=(
        "## Summary\nChanges required.\n\n"
        "### F1 [P2] Config schema migration not included in this PR\n"
        "- **Evidence:** `PlatformClient` reads `platform_client_url`; the "
        "config schema still only defines `legacy_client_url`.\n"
        "- **Impact:** A partially-deployed cluster reads the stale field "
        "and fails to connect.\n"
        "- **Fix:** Ship the config schema migration in this PR or gate the "
        "rollout on it."
    ),
    github_inline_comments=(
        "F1 [P2] Config schema migration not included in this PR.",
    ),
)

# --- 8/9. human_review_output on/off pair (wording-only invariance) -------
HUMAN_REVIEW_OUTPUT_OFF = ReviewerBriefCase(
    case_id="human-review-output-off",
    covers=frozenset({"human-review-output-equivalence"}),
    mode="active",
    human_review_output=False,
    decision="changes-required",
    user_focus_input="Backward compatibility and DynamoDB access patterns.",
    what_changed=(
        "Adds a new payment-instruction lookup path and changes retry "
        "eligibility before dispatch."
    ),
    user_provided_focus_field="Backward compatibility and DynamoDB access patterns.",
    manual_review_focus=(
        "Confirm the new lookup preserves legacy ordering/visibility semantics.",
        "Inspect the query/index access pattern for partition concentration "
        "and pagination behavior.",
        "Re-check retry idempotency around the newly introduced state transition.",
    ),
    open_questions=None,
    independent_focus_present=True,
    references_finalized_finding=False,
    pair_id="human-review-output-pair",
    required_keywords=(
        "legacy ordering",
        "query/index access pattern",
        "retry idempotency",
        "backward compatibility",
        "dynamodb",
    ),
    github_review_body="## Summary\nChanges required.",
    github_inline_comments=(),
)

HUMAN_REVIEW_OUTPUT_ON = ReviewerBriefCase(
    case_id="human-review-output-on",
    covers=frozenset({"human-review-output-equivalence"}),
    mode="active",
    human_review_output=True,
    decision="changes-required",
    user_focus_input="Backward compatibility and DynamoDB access patterns.",
    what_changed=(
        "A new payment-instruction lookup path, plus a change to retry "
        "eligibility before dispatch."
    ),
    user_provided_focus_field="Backward compatibility and DynamoDB access patterns.",
    manual_review_focus=(
        "Confirm the new lookup keeps legacy ordering/visibility semantics.",
        "Look at the query/index access pattern for partition concentration.",
        "Re-check retry idempotency around the new state transition.",
    ),
    open_questions=None,
    independent_focus_present=True,
    references_finalized_finding=False,
    pair_id="human-review-output-pair",
    required_keywords=(
        "legacy ordering",
        "query/index access pattern",
        "retry idempotency",
        "backward compatibility",
        "dynamodb",
    ),
    github_review_body="## Summary\nChanges required.",
    github_inline_comments=(),
)

ALL_CASES: tuple[ReviewerBriefCase, ...] = (
    CLEAN_NO_FOCUS,
    TRUSTED_FOCUS_ACTIVE,
    MISLEADING_FOCUS,
    CONFLICTING_FOCUS,
    DELTA_RE_REVIEW,
    STACKED_PR,
    PARTITIONED_PR,
    HUMAN_REVIEW_OUTPUT_OFF,
    HUMAN_REVIEW_OUTPUT_ON,
)

REQUIRED_COVERAGE_TAGS: frozenset[str] = frozenset(
    {
        "clean-pr-no-focus-what-changed",
        "clean-pr-no-focus-independent-manual-focus",
        "trusted-focus-represented",
        "trusted-focus-plus-independent-focus",
        "misleading-focus-grounded",
        "misleading-focus-no-invented-finding",
        "conflicting-focus-repo-wins",
        "active-review-brief-available",
        "active-review-no-leak",
        "passive-review-brief-returned",
        "human-review-output-equivalence",
        "clean-review-useful-not-collapsed",
        "delta-review-effective-delta-only",
        "stacked-pr-effective-layer-only",
        "large-pr-aggregate-not-partition-notes",
        "findings-inform-focus-no-duplication",
    }
)


def out_of_scope_terms_present(case: ReviewerBriefCase) -> tuple[str, ...]:
    """Which of a case's declared `forbidden_terms` actually appear in its
    brief text. Empty means the case stays within its declared scope
    (delta / stacked-layer / partition-aggregate). Shared by the real
    corpus assertions and the negative-canary tests that prove this check
    has genuine detection power -- mirroring
    brief_leaked_into_github()'s role for publication isolation."""
    text = case.full_brief_text()
    return tuple(term for term in case.forbidden_terms if term in text)


def cases_covering(tag: str) -> tuple[ReviewerBriefCase, ...]:
    return tuple(case for case in ALL_CASES if tag in case.covers)


def pair(pair_id: str) -> tuple[ReviewerBriefCase, ...]:
    matched = tuple(case for case in ALL_CASES if case.pair_id == pair_id)
    return matched
