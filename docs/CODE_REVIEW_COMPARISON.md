# How These Code Review Skills Differ From Other Review Approaches

This document explains why [`local-code-review`](../skills/local-code-review/SKILL.md) and
[`github-pr-review`](../skills/github-pr-review/SKILL.md) exist as their own Skills, given that
Claude Code, GitHub-native reviewers, CodeRabbit-style third-party tools, Codex, Cursor, and other
code-review approaches already exist. It is permanent repository documentation, not a research
artifact — it does not track any single vendor's roadmap and should stay accurate as those
products evolve.

## At a glance

**Which review mode fits?**

| Situation | Mode |
|---|---|
| Local changes, no PR yet, before you push | `local-code-review` |
| …and you also want a coding-agent-ready fix prompt for the findings | `local-code-review` with `include_fix_prompt=true` |
| An existing GitHub PR you did not author — report only | `github-pr-review` (passive) |
| …that PR, with inline comments and an Approve / Request Changes decision | `github-pr-review` (active — needs review permission) |

**Core differences**

| Dimension | `local-code-review` | `github-pr-review` |
|---|---|---|
| Review target | local implementation delta (committed / staged / unstaged / untracked) | the GitHub Pull Request delta |
| Local vs. GitHub | runs against a local working tree | runs against GitHub PR state; optional isolated read-only checkout |
| Prior-review-history awareness | an optional associated PR's findings / decisions, reconciled | the PR's own prior reviews / comments, reconciled |
| Review Context | shared model — requirements / Jira / GitHub Issue / HLD / ADR / plan | shared model, identical |
| Repository instruction handling | root→specific `AGENTS.md` hierarchy shapes evaluation, never widens the target | same |
| Read-only behavior | always; never edits, commits, pushes, or touches GitHub | read-only on Git and code; the checkout is a throwaway clone |
| GitHub publication | never | active mode only, as one batched review |
| Approve / Request Changes | n/a — `REVIEW CLEAN` / `CHANGES REQUIRED` | active mode, when authorized; maximum positive action is Approve |
| Remediation guidance | concise direction; opt-in `include_fix_prompt=true` adds one full fix prompt per qualifying root-cause finding | concise reviewer-facing direction only; no full fix prompt |
| Finding detail presentation | `include_finding_details=true` by default | `include_finding_details=false` by default; per-finding override for materially useful technical context |
| Root-cause / model-completeness reasoning | shared `review-scope.md` pass | shared, identical |
| Intended use case | pre-PR implementation review | independent review of an existing PR |

**What each mode intentionally does *not* do**

- Neither edits, commits, pushes, merges, or manages branches.
- Neither runs the target repository's tests, linters, build, hooks, or any of its code.
- Neither creates a GitHub status check, required check, ruleset, or branch-protection state — a blocking P0/P1 result never enforces a merge block.
- `github-pr-review` never merges; its strongest action is **Approve**.
- `local-code-review` never publishes anything to GitHub, even when given a PR reference.

The rest of this document explains *why* this split exists and how it
compares to other reviewers. Full row-by-row detail is in §9
(`local-code-review` vs. `github-pr-review`); §10 lists what is planned but
not yet implemented.

## 1. Purpose

These Skills are not primarily trying to out-perform every native or third-party reviewer at
finding bugs. Bug-finding quality varies by engine, model, and vendor investment, and this
repository does not compete on that axis as its main value proposition.

Their durable value is a **portable Code Review governance protocol**, combined with a
**portable review fallback** — a self-contained reasoning path that works with no external review
service at all. The protocol defines who may review, what exact state was reviewed, whether
review authority is valid, what happens when the reviewed code changes mid-review, and how a
final decision is produced — independent of which engine or runtime finds the actual defects.

## 2. What Other Review Systems Commonly Provide

Native and third-party code-review tooling commonly provides capabilities such as:

- code/diff analysis against the changed lines;
- repository context beyond the raw diff;
- multi-file and cross-file reasoning;
- inline findings attached to specific lines;
- finding verification and deduplication;
- automated review execution triggered by a PR event or an explicit command.

This list is descriptive, not a scorecard — exactly which of these a given product provides, how
well, and under what conditions varies by vendor and changes over time. This document does not
make claims about the current state of any specific external product beyond what this
repository's own review-architecture research already established; it avoids becoming a feature
matrix that goes stale.

## 3. What This Repository Adds

The governance features below are this repository's differentiated, durable content:

- **Hard self-review prevention** — an implementing Agent must not review its own PR.
- **Defensive authenticated-user vs. PR-author guard** — `github-pr-review` independently
  compares the authenticated identity against the PR author before doing anything else, and
  terminates with `REVIEW SKIPPED` if they match, regardless of why it was invoked.
- **One reviewer owner per scope** — a given PR or local branch/review scope has exactly one
  owning Code Review Agent at a time.
- **Reviewer-aware, SHA-bound delta re-review** — a re-review may be scoped to just the delta
  since the last review only when the current reviewer is the same identity as the immediately
  preceding completed review, and that review's exact reviewed SHA can be established reliably.
  Any ambiguity defaults to a normal full review.
- **`NO NEW DELTA`** — when the same reviewer's previously reviewed SHA already equals the
  current HEAD, no redundant review is manufactured.
- **Exact reviewed HEAD tracking** — the reviewed commit is recorded explicitly, not inferred.
- **HEAD revalidation immediately before the final decision** — a changed HEAD is never approved
  as if it were the SHA that was actually reviewed.
- **Mutation boundary** — neither Skill edits implementation files, commits, pushes, merges, or
  manages branches; `github-pr-review`'s maximum positive action is Approve.
- **Explicit fresh approval per invocation for local review** — `local-code-review` requires a
  meaning-based, non-persistent, current-interaction approval before every single invocation,
  including every re-review after a fix.
- **A portable P0/P1/P2 severity model** with an explicit blocking rule, shared identically by
  both Skills.
- **Explicit Approve / Request Changes semantics** — `github-pr-review` can submit a formal
  GitHub review decision when authorized to, not merely a passive comment.
- **Passive and active review modes** — a report-only mode and a GitHub-publishing mode apply the
  same review standard, differing only in delivery.
- **Portable operation across runtimes** — both Skills are designed to run under Claude Code,
  Codex, Cursor, OpenCode, or any other Agent Skills-compatible runtime, rather than depending on
  one vendor's reviewer being present.

## 4. Governance vs. Review Intelligence

Two distinct concerns run through both Skills:

```text
Review intelligence
    finds and explains defects — reads a diff and surrounding code, reasons about
    correctness, and produces evidence-backed findings.

Review governance
    controls who may review, what exact state was reviewed, whether review
    authority is valid, what happens when the code changes during review, and
    how the final decision is produced.
```

This repository intentionally owns the second category as its durable core. The shared review
policies in [`shared/policies/`](../shared/policies/) — including
[`review-scope.md`](../shared/policies/review-scope.md)'s invariant that related changes are
reviewed together rather than file-by-file, and [`evidence.md`](../shared/policies/evidence.md)'s
invariant that findings outside the changed lines must be tied to what the reviewed change
actually affects — establish engine-neutral review-quality expectations, but they are
intentionally kept concise: a capable reviewing engine is expected to satisfy them without a
detailed, prescribed reasoning procedure. A small number of exceptions target recurring,
high-value failure modes that are otherwise easy for a capable reviewer to skip past even while
reading the diff carefully — [`review-scope.md`](../shared/policies/review-scope.md)'s "Existing
behavior ownership" (does this change duplicate an existing canonical implementation of the same
business/validation/state semantics rather than reusing it) and "Failure state, retry safety, and
recovery" (partial-failure state, retry/idempotency safety, evidenced recovery, and proportional
observability, as one signal-triggered reasoning move). These remain local-first and
signal-triggered, not a general checklist: each activates only when the diff's own shape gives
concrete reason to, and neither licenses a repository-wide audit — see those sections' own text.
The governance layer, by contrast, is specified in full detail, because it is not the kind of
thing any review engine is expected to reconstruct on its own.

## 5. Defense in Depth

Some invariants are enforced at two separate points, deliberately:

- **Orchestration prevention**, in repository-wide instructions (`AGENTS.md` and
  [`policies/review-orchestration-policy.md`](../policies/review-orchestration-policy.md)): the workflow
  calling these Skills must never invoke `github-pr-review` against a PR the same implementing
  Agent just opened or updated. This is a sequencing rule for whatever is doing the orchestrating.
- **Skill-level defensive enforcement**: `github-pr-review` independently verifies the
  authenticated identity against the PR author and returns `REVIEW SKIPPED` before any analysis,
  regardless of whether the orchestration rule above was honored.

These are not the same rule enforced twice — they intervene at two different points in the
causal chain. The orchestration rule tries to prevent the invocation from happening at all; the
Skill-level guard is a self-contained fallback that still holds even if that prevention failed, in
any runtime. Neither is a substitute for the other, and the Skill-level guard is never weakened
by the orchestration rule's existence.

## 6. Portability

Canonical Skill behavior — `SKILL.md` plus each Skill's own packaged policies, runbooks, and
templates, plus the resources shared under `shared/` — must remain runtime- and vendor-neutral. It
must not require a specific model, a specific hosted service, or a specific tool name to function
correctly, and must remain fully correct with only the packaged archive present, with no
dependency on this source repository's own `AGENTS.md`, its `policies/`, `docs/ARCHITECTURE.md`, or `README.md`.

A vendor-native reviewer may, in the future, become an optional execution enhancement for the
finding-generation portion of a review. It must never become a requirement for either Skill to
function: both Skills are designed to perform their own complete review reasoning with no external
review service at all, and that fallback path is treated as permanent, not as a placeholder for a
pluggable-engine architecture. No such pluggable-engine implementation exists in this repository
today, and this document does not describe one as though it did.

## 7. Comparison Summary

| Capability | Typical native/third-party reviewer | These Skills |
|---|---|---|
| Bug finding | Yes | Yes |
| Repository-context reasoning | Often | Yes |
| Self-review prevention | Varies by product | Explicit |
| Reviewer ownership | Varies by product | Explicit |
| SHA-bound delta re-review | Varies by product | Explicit |
| HEAD TOCTOU protection | Varies by product | Explicit |
| Per-invocation local approval | Rare | Explicit |
| Mutation prohibition | Varies by product | Explicit |
| Runtime portability | Usually vendor-specific | Core requirement |
| Final repository-defined decision semantics | Varies by product | Explicit |

This is a conceptual comparison, not a claim that every external reviewer lacks every governance
feature listed — capability varies by product and changes over time. "Explicit" means the
behavior is a specified, normative part of this repository's Skills, not that no other product can
ever exhibit similar behavior.

## 8. Non-goals

This repository is not trying to:

- reproduce every vendor-specific reviewer feature;
- hard-code Claude Code (or any other single runtime's) behavior into the canonical Skills;
- require a managed review service for either Skill to function;
- replace static analysis, linting, or security-scanning tooling;
- perform implementation work while reviewing — neither Skill edits, commits, or pushes code;
- create multiple competing reviewers for the same review scope.

## 9. `local-code-review` vs. `github-pr-review`

The two Skills are distinct entry points that share one review standard. They
differ in *what* they review and *how* they deliver; they do **not** differ in
severity semantics, decision derivation, or read-only reasoning. Everything
marked "shared" below is one file under [`shared/policies/`](../shared/policies/)
consumed identically by both.

| Capability | `local-code-review` | `github-pr-review` |
|---|---|---|
| **Review target** | the local implementation delta | the GitHub Pull Request delta |
| **Local repository access** | required | API-only by default; optional or required isolated temporary checkout is supported |
| **GitHub PR access** | read-only, only when an optional PR reference is supplied | required for PR state; write only in active mode |
| **Committed / staged / unstaged / untracked scope** | all four, detected separately ([`repository-state.md`](../skills/local-code-review/policies/repository-state.md)) | n/a — the PR diff (full, or a bounded delta re-review) |
| **Review context** (optional) | shared model ([`review-context.md`](../shared/policies/review-context.md)); local application maps context onto the local delta | shared model; thin PR application ([`review-context.md`](../skills/github-pr-review/policies/review-context.md)) — the PR stays the target |
| — generic / free-form textual context | consumed directly, no resolution step | consumed directly, no resolution step |
| — Jira **reference** support | accepted (ticket key or URL) — a pointer to context, not the context itself | accepted, same |
| — Jira context **resolution** | reference → the shared policy's explicit numbered **"Resolution procedure"** (identify an available Jira MCP / connector / runtime Jira read tool → read-only fetch the issue → fetch relevant comments/linked context when supported → normalize → continue only on success), run **before** review reasoning; **precondition** — any failure (no integration / auth / authz / not found / malformed / connector or MCP error or timeout) yields `JIRA CONTEXT UNRESOLVED` with no key/branch/PR-title/copied-metadata inference, never a graded review; read-only, no Jira mutation | same shared contract; unresolvable → `JIRA CONTEXT UNRESOLVED` reasoning result, no Approve/Request Changes for a Jira scope never established |
| — pasted Jira text | consumed directly as free-form context (no resolution needed) | same |
| — GitHub Issue context | reference → read-only GitHub retrieval, **or** pasted text; explicit only, **no automatic PR↔Issue discovery** | same, explicit only |
| — HLD / ADR / implementation-plan context | yes (text or excerpt) | yes |
| — PR description as intent context | via a supplied PR reference / free-form text | always available for the PR under review |
| — Jira is mandatory? | no — supplying none yields a normal unscoped review | no — same |
| **Existing Review Evidence** | prior findings / comments / settled decisions from an optional associated PR ([`pr-context.md`](../skills/local-code-review/policies/pr-context.md)) | the PR's own prior reviews / review comments / issue comments ([`review-evidence.md`](../skills/github-pr-review/policies/review-evidence.md)) |
| — classification | shared: still-relevant / resolved / stale / duplicate / settled decision / speculative discussion — never blindly inherited | shared, same |
| — retrieval | targeted to the local delta; `gh api` reviews/comments + GraphQL `reviewThreads` example, filtered before use ([`pr-context.md`](../skills/local-code-review/policies/pr-context.md), "Retrieval") | all pages of reviews (+ `APPROVED` / `CHANGES_REQUESTED` / `COMMENTED` state), inline comments, issue comments, thread `isResolved`; `gh api` + GraphQL example ([`pr-scope.md`](../skills/github-pr-review/policies/pr-scope.md), "Retrieving prior review activity"); integration-agnostic, not bound to `gh` |
| — current-target interpretation | shared: reconciled against the current local delta; a resolved thread is evidence, not proof — a reintroduced defect is a fresh finding | shared: reconciled against the current PR HEAD; a changed HEAD re-classifies every prior human finding; old approval never authorizes the new HEAD |
| — authorship authority | shared ([`review-evidence.md`](../shared/policies/review-evidence.md), "Comment authorship"): human/maintainer discussion can settle a decision; automation/bot output contributes observations only, never settles one alone — no reputation scoring, no allowlists | shared, same |
| **Repository context** | shared: deterministic root→specific per-file `AGENTS.md` hierarchy, surrounding code, invariants; instructions shape evaluation without widening the target | shared, same semantics; repository-backed mode reads from the verified temporary snapshot |
| **Scope-boundary reasoning** | shared ([`review-context.md`](../shared/policies/review-context.md), "Scope-boundary reasoning") — missing behavior, contradicted acceptance criteria, unrelated scope expansion, valid-but-out-of-scope findings, repo-policy violations regardless of ticket scope | shared, same, applied to the PR |
| **Severity model** | shared P0 / P1 / P2 ([`severity.md`](../shared/policies/severity.md)) | shared, identical |
| **Final decision semantics** | `REVIEW CLEAN` / `CHANGES REQUIRED`, derived mechanically from blocking (P0/P1) severities | `Approve` / `Request Changes`, same mechanical derivation |
| **Opt-in behavior** | every invocation needs fresh explicit user approval ([`invocation-approval.md`](../skills/local-code-review/policies/invocation-approval.md)) | selection boundary + defensive self-review guard ([`review-authority.md`](../skills/github-pr-review/policies/review-authority.md)); no per-run approval gate |
| **Re-review behavior** | stateless; fresh approval each run; staged-delta fingerprint short-circuit | SHA-bound reviewer-owned delta re-review; `NO NEW DELTA`; escalation to full review |
| **Publishing behavior** | returns one structured report to the caller; never publishes | passive: returns a report; active: one batched GitHub review (inline comments + body + Approve/Request Changes) |
| **Remediation guidance** | concise `Fix` direction by default; explicit `include_fix_prompt=true` may add one coding-agent-ready prompt per qualifying root-cause finding; output-only and still read-only | concise reviewer-facing `Fix` direction only; no local-style full implementation prompt; severity, verdict, and mutation boundaries unchanged |
| **Repository-access modes** | n/a — existing local working tree | API-only; optional repository-backed enrichment (visible API-only degradation on failure); required repository-backed review (failure → ungraded `REVIEW INCOMPLETE`, no workers) ([`repository-checkout.md`](../skills/github-pr-review/policies/repository-checkout.md)) |
| **Repository-backed inspection** | n/a — already has the local working tree | Available as optional enrichment or an explicit requirement; default remains API-only |
| — temporary checkout | n/a | `mkdtemp` → blobless clone (`--no-checkout --no-tags --filter=blob:none`) → fetch base/head (SHA fallback) → detached checkout at `head_sha`; one clone shared by all workers, not one per worker |
| — base/head fidelity | committed/staged/unstaged/untracked vs. resolved base | resolves repo identity + base ref/SHA + head ref/SHA + merge-base from a `NormalizedPrSource`; prefers immutable SHAs; PR delta = `merge-base(base,head)..head`, correct even when base advanced after branch-off; verifies the fetched head matches `head_sha` |
| — cleanup | n/a | one lifecycle, guarded delete (inside scratch parent, not the parent, ownership marker present) on **every** exit path — success, failure, interruption |
| — read-only repository inspection | inherent | reads files and safe Git commands only; target-repo tests/builds/linters/hooks/scripts are **never** run; surrounding files never become independent review targets |
| — private-repo auth | runtime Git identity | runtime's existing Git/GitHub credentials; no token in generated files, no secret in logs/output, no credential persisted; auth failure degrades only in optional mode and is incomplete in required mode |
| **Parallel review capability** | not wired (would apply equally) | execution optimization selected only with reliable runtime capability plus at least two materially independent dimensions and expected latency benefit; never by file count alone ([`parallel-review.md`](../shared/policies/parallel-review.md)) |
| — sequential default | always sequential today | default and fast path for simple, dependent, mechanically broad, uncertain, or unsupported reviews |
| — sequential fallback | always sequential today | always valid; missing or uncertain parallel capability never fails the review |
| — centralized aggregation | single reviewer | one aggregator: normalize → deduplicate → reconcile → canonical severity → one decision; worker completion order never matters; workers derive nothing final; missing **required** dimension → `REVIEW INCOMPLETE`, never `REVIEW CLEAN` |
| — runtime portability | n/a | capability *names* only in policy; per-runtime facts (Claude Code Agent Teams + `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, Cursor subagents, Codex concurrent agents) isolated in `docs/runtime-parallelism.md`; the Skill never mutates user config |
| — simulated PR testing | n/a | a deterministic local bare-repo + branches + `refs/pull/123/head` harness (`tests/support/pr_simulation.py`) exercises the checkout with real Git; a live GitHub PR is not required for coverage |
| **Mutation / read-only boundaries** | read-only; never edits, commits, pushes, or performs any GitHub mutation — even with a PR reference | read-only on Git and implementation; the repository-backed checkout is an isolated throwaway clone, never the target repo, and read-only; GitHub mutation only in active mode; max positive action is **Approve**; never merges; never executes target-repo code |
| **Delegated Agent / Sub-Agent execution** | mechanics never transfer the approval decision — the user owns it | reviewer/author separation required; parallel workers are read-only and non-authoritative; orchestration external |

## 10. Planned / not yet implemented

These are future phases. No code, policy, or runbook in this repository
implements them today, and this document does not claim they are supported:

- **GitHub blocking status checks / merge enforcement** — required checks,
  rulesets, branch-protection changes, or any GitHub-side merge blocking. A
  blocking P0/P1 result never enforces a merge block; `github-pr-review`'s
  maximum positive action stays **Approve**.
- **Automatic execution of PR code** — running the target repository's tests,
  linters, build, hooks, or arbitrary commands, in any mode including
  repository-backed. Cloning untrusted PR code is not permission to run it.

## See also

- [`AGENTS.md`](../AGENTS.md) + [`policies/review-orchestration-policy.md`](../policies/review-orchestration-policy.md)
  — repository-wide orchestration rules, including the implementer/reviewer separation and the
  local-review approval gate summarized in §5 above.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — module map and the orchestration/reasoning/delivery
  boundary these Skills are built on.
- [`runtime-parallelism.md`](runtime-parallelism.md) — the isolated per-runtime facts
  (Claude Code / Cursor / Codex) behind the portable parallel-review contract.
- [`skills/github-pr-review/SKILL.md`](../skills/github-pr-review/SKILL.md) and
  [`skills/local-code-review/SKILL.md`](../skills/local-code-review/SKILL.md) — the complete,
  normative Skill definitions this document summarizes.
