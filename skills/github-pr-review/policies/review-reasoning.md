# Policy — Review Reasoning

Governs how `github-pr-review` reasons about a PR's changes once scope is
established: grouping related changes into logical cohorts and
inspecting the relevant dependency surface beyond the raw diff. Canonical
index: [`github-review.md`](github-review.md). This reasoning applies
only after review authority
([`review-authority.md`](review-authority.md)) and reviewer-mode
resolution ([`reviewer-delta-review.md`](reviewer-delta-review.md)) have
already run — it never determines whether or how much of the PR is in
scope, only how that already-established scope is analyzed.

## Logical Cohort Review

For a PR containing multiple related changes, group related changed
files and hunks into logical cohorts when useful, rather than reviewing
each file independently — file-by-file review is not the primary
reasoning model. A logical cohort is a set of changes that together
implement one behavioral or architectural concern — for example: API
contract + DTO/schema + controller changes; domain/service logic +
supporting utilities; persistence model + repository/query + migration;
producer + consumer + event/schema changes; implementation +
corresponding tests; configuration + deployment/runtime changes.

Reason about each identified cohort as a single change unit:

- identify the main logical cohorts represented by the diff;
- associate related files and hunks even when they live in different
  directories;
- review cross-file behavior within the cohort;
- detect inconsistencies between files participating in the same change;
- avoid treating file boundaries as architectural boundaries.

Logical cohorts are a reasoning aid, not a mandatory reporting
structure. Do not label output `Cohort 1`, `Cohort 2`, etc. unless
exposing the grouping materially improves the clarity of the review. A
small or single-purpose change needs only one cohort and no added
ceremony.

## Code Impact / Dependency Analysis

Changed lines are the starting point of review, not necessarily its
complete boundary. For a meaningful code change, inspect relevant
dependency paths beyond the raw diff to determine the realistic blast
radius: who depends on the changed symbol, contract, schema, or
behavior, and whether this PR preserved the assumptions those dependents
make.

Relevant impact relationships may include: callers of changed functions
or methods; callees whose contracts the changed code relies on;
interface implementations; interface or abstract-type consumers;
subclasses or overridden behavior; event producers and consumers; API
clients and server-side contracts; schema/model consumers; persistence
mappings and migrations; configuration consumers; tests covering the
affected behavior; shared utilities or libraries used by multiple
components.

For each changed symbol, contract, schema, or behavior meaningfully
affected by the PR, ask:

1. Who depends on this?
2. What assumptions do those dependents make?
3. Did this PR preserve those assumptions?
4. Are there downstream paths not represented directly in the diff?
5. Do existing tests cover the impacted behavior?

Use repository search, language-aware references, imports,
implementations, call sites, tests, and surrounding code to answer these
questions; use dedicated symbol/reference-search tooling where the
repository or runtime provides it, but no dedicated code-graph tool or
vendor is required for this analysis.

### Impact exploration boundaries

Dependency analysis is bounded, not exhaustive. Stop exploring once the
realistic blast radius is sufficiently understood to evaluate the
correctness of the PR. Do not recursively traverse dependencies merely
because more references exist — each additional dependency hop must have
a concrete review-relevant reason, for example: does this caller rely on
the old return shape? does this consumer assume the previous event
schema? does this implementation still satisfy the changed interface?
does this migration preserve the assumptions made by existing queries?
Prefer these targeted questions over exhaustive repository traversal.

### Unchanged code as evidence, not automatic scope

Reading unchanged dependent code is allowed and encouraged when needed
to establish context, assumptions, and impact. Unchanged code is an
evidence source, not automatic scope expansion — impact analysis must
not become an unrelated audit of pre-existing defects. A finding outside
the changed lines is valid only when the PR:

- introduces the defect;
- activates an existing latent defect;
- violates an existing dependent contract;
- creates a concrete regression through the changed behavior; or
- exposes a missing protection directly relevant to the changed path.

Do not report unrelated legacy problems merely because they were
encountered while following dependencies.

### Findings still require concrete evidence

Impact analysis exists to improve finding quality, not to increase
speculative comments. A dependency becomes relevant to a finding only
when it provides evidence of a concrete defect, regression, contract
violation, missing validation, incorrect assumption, compatibility
break, or other actionable issue under the existing finding contract in
[`evidence.md`](../../../shared/policies/evidence.md) and
[`../../../shared/templates/finding.md`](../../../shared/templates/finding.md).
Do not create a finding merely because another dependent file or symbol
exists. Findings phrased only as "consider checking…", "this might
possibly…", "there could be…", or "you may want to…" are not sufficient
on their own — they must still satisfy the existing actionable-finding
requirements. Existing noise-suppression and deduplication rules (see
[`pr-scope.md`](pr-scope.md), "Existing review awareness") remain
authoritative.

### Small and isolated changes

Do not force heavy cohort or dependency analysis onto a small, obviously
isolated PR — trivial/single-purpose PRs are not forced into unnecessary
cohort or graph-analysis ceremony. One logical cohort, minimal
surrounding-context inspection, and lightweight dependency exploration
are sufficient; review overhead should not materially increase for
trivial changes. This reasoning model scales with the complexity and
blast radius of the PR, not a fixed procedure applied uniformly.
