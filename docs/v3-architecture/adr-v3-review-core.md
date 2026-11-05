# ADR: v3 Review Core and mini-skill boundaries

- **Status:** Accepted
- **Issue:** [#842](https://github.com/amirbena/code-review-skill/issues/842)
- **Epic:** [#841](https://github.com/amirbena/code-review-skill/issues/841)
- **Supersedes:** the v2 architecture described in
  [`../ARCHITECTURE.md`](../ARCHITECTURE.md), at the v3.0.0 cutover only.

This record is explanatory. Until each child Issue lands, the v2 canonical
sources (`AGENTS.md`, `policies/`, `shared/`, `skills/`) keep governing
behavior on `main`. The per-file mapping is in
[`packaged-file-disposition.md`](packaged-file-disposition.md).

## 1. Context

v2.0.0 still carries the v1 architecture, and every ordinary review pays for
all of it. The measurements below were taken for #842 on v2.0.0
(`0369f40`):

- **Load cost before the diff is read.**
  `context_size_report.py`
  reports that Local loads 13 files (~42k est. tokens) before step 1 and
  GitHub loads 24 files (~76k). About 23k lines of packaged instructions sit
  across 2 Skills, 51 `shared/` files and 19 `capabilities/` manifests.
- **Fail-closed conditional loading is the root cause.** "Unknown
  applicability means load" needs a §2 inventory, a mandatory-loading
  checkpoint, a pre-verdict recheck and resumable loading. A
  `policy-loading` replay corpus and five recent fixes (#782, #784, #806,
  #812, #831/#834/#837) followed from it.
- **Automatic depth orchestration.** Change-risk depth, expansion rings,
  large-PR partitioning, stopping-criteria pass families, specialist-depth
  predicates and the reasoning checkpoint all decide depth. None of them
  detects a defect.
- **Tests pin prose rather than behavior.** `tests/policy/` (~24.7k lines)
  and `tests/reference/review/` (~12k lines of shadow models) are ~65% of
  ~95k test lines. No CI test runs a Skill on a diff.

## 2. Decision

Replace the two-Skill + shared-policy + capability-manifest architecture
with **one small Review Core** and **independently selectable
mini-skills**. Depth comes from what the user asks for, in their own
words, never from routing predicates. The model reads the request and
picks mini-skills by judgment, using each mini-skill's short description
(§5).

```text
user's natural-language review request
        │
        ▼
review-core: resolve target, review, and select mini-skills
  intent (default)  only what the request justifies; ask before going further
  auto (opt-in)     may also add analysis depth when evidence justifies it
        │
        ├── no depth selected ──────────► Core report (+ JSON on request)
        └── mini-skills selected ───────► each adds findings or delivery
                                          under the Core contract
```

A plain "review this" runs the Core with no optional depth. Users never
need to know a Skill name, though naming one still works.

## 3. Final Skill names

The `review-` prefix groups the set and avoids the common runtime built-ins
`/code-review`, `/security-review` and `/review`. These names are final for
v3.0.0.

| Skill | Kind | Responsibility | Implemented by |
| --- | --- | --- | --- |
| `review-core` | Core | Read-only review of a local Git change or a GitHub PR | [#843](https://github.com/amirbena/code-review-skill/issues/843) |
| `review-publish-github` | mini-skill (delivery) | Publish the Core result to a PR: inline comments, summary, one batched review | [#844](https://github.com/amirbena/code-review-skill/issues/844) |
| `review-requirements` | mini-skill (depth) | Requirement / acceptance-criteria verification from a Jira key, GitHub Issue or pasted AC, with per-requirement status | [#845](https://github.com/amirbena/code-review-skill/issues/845) |
| `review-deep-investigation` | mini-skill (depth) | Lifts the Core investigation bound: wider tracing, root-cause and model completeness, affected tests, failure/retry, null-absence, architectural placement | [#845](https://github.com/amirbena/code-review-skill/issues/845) |
| `review-suggestions` | mini-skill (depth) | Additional non-blocking P2 maintainability, design and hygiene suggestions | [#845](https://github.com/amirbena/code-review-skill/issues/845) |
| `review-security` | mini-skill (domain) | Security deepening and dependency / supply chain | [#846](https://github.com/amirbena/code-review-skill/issues/846) |
| `review-backend` | mini-skill (domain) | APIs and contracts, DB and migrations, concurrency and distributed systems, performance, deployment and config | [#846](https://github.com/amirbena/code-review-skill/issues/846) |
| `review-frontend` | mini-skill (domain) | UI behavior, state, accessibility, rendered inspection, design reference | [#846](https://github.com/amirbena/code-review-skill/issues/846) |
| `review-runtime-check` | mini-skill (execution) | Run targeted tests or a minimal reproduction to confirm a finding, sandboxed by default | [#847](https://github.com/amirbena/code-review-skill/issues/847) |

## 4. Review Core boundary

`review-core` reviews **either** a local Git change **or** a GitHub PR,
always read-only. The target is resolved from the input; a PR is one more
diff source, read via `gh`, with an optional isolated checkout. The Core
owns exactly these six things:

1. **Target resolution.**
   - Local: committed vs base, staged, unstaged and untracked, each reported
     separately.
   - PR: the full PR diff at a recorded HEAD.
   - Base: the user-specified base, else the merge-base with upstream or
     the default branch. The report states which.
2. **Review reasoning.** What changed and what behavior changes; a short
   implication checklist (callers, contracts, data, security, failure
   paths, tests); the credible-defect bar; candidate validation; root-cause
   dedup; and **bounded investigation** (from #840): name the suspicion,
   follow its execution path and direct dependencies, stop on confirm or
   dismiss.
3. **Findings and verdict.** P0/P1/P2 semantics; the evidence rule; a
   minimal finding shape of severity, title, location, evidence, impact and
   fix, where `fix` is focused, actionable guidance for that finding; the
   mechanical decision: any P0/P1 → `CHANGES REQUIRED`, else
   `REVIEW CLEAN`, with `REVIEW INCOMPLETE` overriding both.
4. **`REVIEW INCOMPLETE` triggers** — a closed set of four:
   - the target or diff cannot be fully read;
   - a changed text file cannot be read;
   - the PR HEAD moved during the review;
   - a selected mini-skill could not complete its required input.
5. **Safety:** S1–S5 and S10 (§7).
6. **Output.** One concise human report in one senior voice, and one
   machine-readable JSON result on request. The JSON is kept because
   [`benchmark_review_adapter.py`](../../runtime_platform/benchmark/scripts/benchmark_review_adapter.py)
   depends on it. There are no other presentation options.

**Target shape:** `SKILL.md` with the procedure inline, about three rule
files and one report template. There is no runbook, no §2 loading
inventory and no loading checkpoint: the Core is small, so it is read in
full on every run.

## 5. Mini-skill contract

Every mini-skill follows these rules:

- It is a standalone Skill folder. It **adds findings or delivery**, using
  the Core's finding shape and severity scale.
- The Core always runs first; a selected mini-skill then runs on the
  Core's result and target.
- It never redefines severity, the verdict rule, the `REVIEW INCOMPLETE`
  set, or S1–S5/S10.
- If it cannot obtain its required input, the run ends `REVIEW
  INCOMPLETE` under Core trigger 4. It never silently degrades to a clean
  result.
- A mini-skill references the Core contract by Skill name, not by a
  relative path into another Skill's folder. How the Core contract is
  made available at packaging time is decided in #843 and #851.
- Its frontmatter `description` is short and says what it adds and when
  it helps. That description is the whole selection surface.

### 5.1 Activation modes

The mode is set only by the user's request for this run. `intent` and
`auto` are internal names: the user never needs to know them or any
mini-skill name.

| Mode | Who selects | What may be selected |
| --- | --- | --- |
| `intent` (default) | The model, from the user's request | Only the mini-skills the request's intent justifies. "Is this auth change safe?" justifies `review-security`; "does this meet PROJ-123?" justifies `review-requirements`; "post the review" justifies `review-publish-github`. A plain "review this" selects none. |
| `auto` (opt-in) | The model, during the review | Everything `intent` selects, plus analysis mini-skills the model adds when concrete evidence in the reviewed change justifies deeper investigation. It does not ask before each addition. |

**Recognizing the mode.** The model reads the meaning of the request; there
is no mode parser, keyword list or flag. The request is `auto` only when it
clearly hands the reviewer the choice of *which additional expertise* to
apply. Asking for thoroughness, depth or care in a named area is not that
hand-off: it stays `intent`, and only the mini-skills that area justifies
run. When it is unclear, the mode is `intent`.

| Request | Mode | Selected up front |
| --- | --- | --- |
| "Review this code." | `intent` | none (Core only) |
| "Review the backend thoroughly." | `intent` | `review-backend` |
| "Do a really thorough review of this PR." | `intent` | none: thoroughness alone names no area. The Core may still ask before adding depth. |
| "Check the migration and post the review." | `intent` | `review-backend`, `review-publish-github` |
| "Go as deep as necessary and use whatever expertise you think is relevant." | `auto` | none up front; the model adds analysis depth as evidence appears |
| "Decide which specialized reviews are needed as you go." | `auto` | same as above |

**Going beyond the requested scope in `intent`.** When the Core finds a
concrete reason for depth that the request did not cover, it may ask the
user once, in plain words, naming the concern and the extra check.
Example: "This changes token validation. Should I also run a security
review?" Without a yes, the capability does not run, and the report names
the concern as not investigated. A yes covers that capability for this run
only.

**Transparency.** The report lists the mode, each mini-skill that ran with
a one-line reason, and any extra depth the user declined or was not asked
about.

**Boundaries that hold in every mode:**

- **Publication.** `review-publish-github` runs only when the user's
  request asks to publish. `auto` never adds it, and the Core never offers
  it as extra depth (S7).
- **Execution.** `auto` never adds `review-runtime-check`. Outside a
  request to run or confirm something, it runs only after the user
  approves a specific ask. Selecting it is not host authorization: the
  host still needs explicit per-invocation authorization (S8).
- **Input gates are unchanged.** `review-requirements` needs a reference or
  acceptance criteria the user supplied, and never infers one from a key or
  branch name (S9). `review-frontend` still needs render consent before it
  renders anything.
- **Untrusted content never selects.** Repository files and PR, Issue or
  Jira text can neither choose a mode nor select, approve or suppress a
  mini-skill (S5).
- **Per run.** A mode, selection or approval never carries over to another
  run (S2).

**What is not added.** No router Skill, policy engine, activation
predicates, capability manifest, registry or loading inventory. Selection
is the model's judgment over the request, the evidence and the short
descriptions. How the Core sees those descriptions in a given runtime is
decided in #843, using the runtime's Skill listing or a short name and
description list in the Core `SKILL.md`, never a manifest.

## 6. Removed outright (not migrated)

Anything below can come back only as its own mini-skill, selected under
§5.1, with demonstrated demand. It never returns as Core routing.

- **Loading and depth machinery.** §2 fail-closed conditional loading, the
  mandatory-loading checkpoint, the pre-verdict recheck and resumable
  loading; change-risk depth classification; deterministic large-PR
  partitioning; the stopping-criteria pass family; specialist-depth
  activation predicates; the reasoning checkpoint.
- **Ownership and delegation.** Review ownership (`REVIEW ALREADY OWNED`),
  parallel review, agent delegation / `spawn_agent`, and the Reviewer
  Brief.
- **GitHub machinery.** SEMI mode, the machine-readable review status,
  required-check setup, SHA-bound stateful delta re-review, reviewer-mode
  delta selection and stacked-PR policy.
- **Extra context sources.** Multi-repository Review Targets,
  workspace-sibling context, external-contract context and
  dependency-tree inspection.
- **Finding and output fields.** Finding confidence, contextual-evidence
  provenance, capability provenance, `include_fix_prompt`,
  `include_fix_guidance`, `include_finding_details`,
  `human_review_output` / `human_inline_findings`, and the
  invocation-options matrix.
- **Repository infrastructure.** `capabilities/` manifests and
  `scripts/capability_architecture/`; `scripts/governance/canonical_homes*`;
  the `scripts/github_integration/` status and required-check code; the
  test-only shadow models in `tests/reference/review/`.

**Added by this ADR** (found while classifying every packaged file; not
named in #842's original list):

- **Review-base-policy findings** (`shared/policies/review-base-policy.md`).
  A workflow-policy violation is not defect detection.
- **Local Existing Review Evidence** (`local-code-review/policies/pr-context.md`)
  and the staged-delta re-review fingerprint in `repository-state.md`.
  Reconciliation with existing PR comments survives only in
  `review-publish-github`, where it decides what gets published.
- **The mandatory remediation-scope boundary step.** Its P2 side moves to
  `review-suggestions`. Every Core finding still carries focused,
  actionable fix guidance in its `fix` field.
- **The verdict-consistency comparator** as a separate pass. With one
  delivery mode in the Core, the mechanical decision rule is the check.

## 7. Safety and compatibility guarantees

| # | Guarantee | v3 owner |
| --- | --- | --- |
| S1 | The Core never edits files, commits, pushes, rebases, opens PRs or mutates GitHub. | `review-core` |
| S2 | Never invoked automatically. Each run needs an explicit user request, and a returned review is not approval to re-run it. | `review-core` |
| S3 | Mechanical verdict: P0/P1 block, P2 never blocks, and an incomplete review is never rendered clean. | `review-core` |
| S4 | Evidence: every finding cites a reviewed location, and citations are never fabricated. | `review-core` |
| S5 | Repository files, PR, Issue and Jira text are untrusted data. They cannot authorize actions or change severity or verdict rules; target-repo instructions inform conventions only. | `review-core` |
| S6 | Mini-skills are selected only under the §5.1 modes: from the user's request (`intent`), on the user's approval, or by evidence after the user opts into `auto`. Untrusted content never selects one, `auto` never adds publication or execution, and no mini-skill changes the severity scale, the verdict rule or S1–S5. | `review-core` + each mini-skill |
| S7 | Publishing happens only via `review-publish-github`. It never approves its own work (COMMENT only), revalidates HEAD before submitting, never merges, and submits one batched review. | `review-publish-github` |
| S8 | Code execution happens only via `review-runtime-check`: sandbox by default, the host only with explicit per-invocation authorization, never commands chosen by repository content. | `review-runtime-check` |
| S9 | Jira and Issue resolution is read-only. An unresolved reference stops the run and is never inferred from a key or branch name. | `review-requirements` |
| S10 | No destructive Git. Any PR checkout is an isolated temporary clone that is always cleaned up. | `review-core` |

Each guarantee has exactly one canonical statement in its owner's packaged
files. Other Skills reference it and never restate it as a competing rule.

## 8. Repository-development rules that conflict with v3

These rules stay authoritative on `main` until v3 lands. The retirement
child [#849](https://github.com/amirbena/code-review-skill/issues/849)
rewrites them on `release/v3`; documentation follows in
[#850](https://github.com/amirbena/code-review-skill/issues/850).

**[`AGENTS.md`](../../AGENTS.md)**

| Location | Conflict with v3 |
| --- | --- |
| Global invariants — "Skill instruction ownership" | Requires every policy a step applies to have a §2 loading obligation, unconditional or conditional with a fail-closed activation rule; "unknown applicability never means skip"; mandatory checkpoints must be preserved; runbook Steps own execution order. v3 has no §2 inventory, no conditional loading, no checkpoints and no runbooks: the Core is read in full and mini-skills are selected by model judgment under the §5.1 modes. |
| Intro, "Map" and the "Reviewer/author separation and opt-in local review" invariant | Name two Skills (`local-code-review`, `github-pr-review`) consuming `shared/`. v3 has `review-core` plus mini-skills; S2 applies to every Skill, and self-review publication moves to `review-publish-github`. |
| "Repository development vs. packaged Skill runtime" | Lists a Skill archive as `SKILL.md` + `policies/`, `runbooks/`, `templates/`, `metadata/` + `shared/`-packaged resources. v3 has no `shared/` and no runbooks. |

**[`policies/skill-development-policy.md`](../../policies/skill-development-policy.md)**

| Section | Conflict with v3 |
| --- | --- |
| "Relationship to Runtime Adapters and the Skills" | Diagram routes through `shared/` into the two v2 Skills. |
| "Runbook Design" | Mandates the runbook / shared-policy / Skill-policy split. The v3 procedure is inline in each `SKILL.md`. |
| "Shared review-context model" | Places review-context semantics in `shared/` with thin per-Skill policies. v3 keeps a minimal target model in the Core and the deep form in `review-requirements`. |
| "Authoring and Maintaining Skill Policies" — "Mandatory vs. conditional", "Evidence-based activation", "Defined completion" | Require a §2 loading obligation, fail-closed loading on unknown applicability, and activated-but-not-produced passes as coverage gaps. v3 replaces these with the §5.1 activation modes and Core `REVIEW INCOMPLETE` trigger 4. |

**[`policies/review-orchestration-policy.md`](../../policies/review-orchestration-policy.md)**

| Section | Conflict with v3 |
| --- | --- |
| "Review Ownership" | Points to `shared/policies/review-ownership.md`, which v3 removes. |
| "Implementation Workflow Termination and Reviewer/Author Separation" | Is written for `github-pr-review` with `review-authority.md` / `review-action-authorization.md` and allows self-review with no formal decision. v3 states it once for `review-publish-github` (S7: COMMENT only, never self-approve). |
| "Explicit User Approval Required for `local-code-review` Invocation" | Scoped to one Skill and owned by `invocation-approval.md`. In v3, S2 covers `review-core` and every mini-skill. |
| "Skill Consumer Branch Policy" and "Human-Facing Review Publication" | Reference the v2 runbooks and two-Skill publication. In v3 the Core returns a report; only `review-publish-github` publishes. |

**Also affected (smaller edits, same child):**
[`policies/documentation-policy.md`](../../policies/documentation-policy.md)
(feature catalog keyed by "which Skill supports it") and
[`docs/ARCHITECTURE.md`](../ARCHITECTURE.md) (the v2 module map).

## 9. Delivery strategy: build alongside, cut over once

[`release_lib/classification.py`](../../scripts/release/release_lib/classification.py)
makes any `skills/` change release-worthy, and a release is cut
automatically on merge to `main`. So v3 is not built on `main`:

1. This ADR merges into `main` through the normal PR workflow (docs-only,
   `Release category: none`).
2. [#852](https://github.com/amirbena/code-review-skill/issues/852)
   creates the long-lived integration branch `release/v3` from the updated
   `main`, with its CI and a main-only release lock.
3. `release/v3` is kept current by **merging** `main` into it, never by
   rebasing.
4. Every v3 implementation PR (#843–#850, and #851's packaging work)
   targets `release/v3`.
5. One cutover PR, [#851](https://github.com/amirbena/code-review-skill/issues/851),
   merges `release/v3` into `main` and produces a single `Breaking` release:
   v3.0.0. v2.x remains the published line until then.

## 10. Consequences

- **Smaller default load.** One Core read in full replaces the 13- and
  24-file pre-step-1 load sets.
- **No v2 depth by default.** Specialist depth that v2 activated by
  predicate now runs when the user's request implies it, when the user
  approves a Core ask, or in `auto` mode. A plain "review this" stays
  Core-only. The benchmark is re-based on this
  split in [#848](https://github.com/amirbena/code-review-skill/issues/848):
  a Core floor plus a per-mini-skill uplift.
- **Breaking for consumers.** The Skill names, invocation options and
  output fields of v2 change. The migration guide is
  [#850](https://github.com/amirbena/code-review-skill/issues/850).
- **Tests move to behavior.** Prose-pinning `tests/policy/` and the
  `tests/reference/review/` shadow models retire with v2 (#849). Tooling
  and safety tests (packaging, release, sandbox, GitHub integration,
  benchmark harness) are kept.

## 11. Skill versioning

Every v3 Skill (`review-core` and every mini-skill) reports one version: the
`X.Y.Z` of the official release tag `vX.Y.Z` it ships in. The tag `v3.0.0`
means `review-core`, `review-backend` and every other v3 Skill are `3.0.0`.
All Skills in a release share that version. There is no per-Skill SemVer
and no separate counter: v2's independently maintained `version` in
`metadata/skill.yaml` is not carried into v3.

This reuses the existing release flow ([`../RELEASE.md`](../RELEASE.md),
"Skill archive version"). No new versioning mechanism is added:

- **Authority.** The release run writes the `## vX.Y.Z` CHANGELOG heading
  and creates the annotated `vX.Y.Z` tag on the same release commit, and
  release verification checks that the tag points at that commit.
  Packaging reads the heading, never Git, so builds stay offline and
  byte-reproducible. A packaged Skill carries its version as data and
  needs no Git at runtime.
- **Representation.** Unchanged from v2. The source `SKILL.md` keeps a
  top-level `version:` mirror line, which the release run stamps. The
  built tree and archive carry it as `metadata.version` (#507). The
  `{{version}}` in `distribution/portable/plugin.json` and
  `distribution/claude/marketplace.json` gets the same value.
- **Before the cutover.** A v3 Skill has never been released, so it must
  not report the current v2.x version. On `release/v3`, v3 `SKILL.md`
  files carry **no** `version:` line, and a non-release build emits no
  `metadata.version` for them. It does not borrow the newest v2.x heading
  the way a v2 Skill's local or PR build does. Today, packaging fails when
  a manifest Skill has no `version:` line.
- **At the cutover.** The release run's stamp step writes `version: 3.0.0`
  into every packaged Skill, inserting the line where it is missing.
  Archive verification then requires exactly `3.0.0` in every archive, as
  it does today for v2. After that, v3 behaves like v2: the committed line
  is a mirror that nobody edits by hand.
- **Owner.** [#851](https://github.com/amirbena/code-review-skill/issues/851)
  implements the packaging and release changes (manifest, the
  pre-release no-version rule, insert-on-stamp) and their tests. The other
  children add no `version:` line and no version field of their own.

## 12. Compatibility entrypoints

v2 users invoke `local-code-review` and `github-pr-review`. v3 keeps those
two names, exactly as published in v2.0.0, as thin wrappers over
`review-core`, and still ships `review-core` and the eight mini-skills under
their own names. Backward compatibility is for the invocation names, not for
v2 behavior or machinery.

- A wrapper is one short `SKILL.md` that delegates to `review-core`. It
  restates no Core policy, severity rule or review logic, and carries no v2
  loading inventory.
- `github-pr-review` never publishes on its own: publication stays an
  explicit request handled by `review-publish-github` (S7).
- There is no router, dispatcher or orchestration layer. The wrappers are
  ordinary Skills.
- [#851](https://github.com/amirbena/code-review-skill/issues/851) packages,
  distributes and validates them. #849 only removes the v2 implementation.
