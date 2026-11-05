# AGENTS.md

This is the **canonical, runtime-neutral, repository-wide entrypoint** for
development of this repository. Every implementation task — regardless of
which runtime executes it — starts here, then follows the routing below
into the focused policy that owns the task's detailed rules.

This repository hosts the **v3 Code Review Agent Skills**: one read-only
Review Core plus independently selectable `review-*` mini-skills, all
sharing one review standard (P0/P1/P2 severity, evidence, one mechanical
decision):

- [`skills/review-core/SKILL.md`](skills/review-core/SKILL.md) — reviews a
  local Git change or a GitHub pull request, read-only, and returns
  findings;
- the mini-skills, each a standalone Skill that adds findings or delivery
  on top of a Core review: `review-publish-github`, `review-requirements`,
  `review-deep-investigation`, `review-suggestions`, `review-security`,
  `review-backend`, `review-frontend` and `review-runtime-check`.

The Core owns the shared review rules; mini-skills reference it by Skill
name and never redefine severity, the verdict rule or the safety
guarantees. See [`docs/v3-architecture/`](docs/v3-architecture/README.md)
for the decision record and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
for the module map.

This file, and the [`policies/`](policies/) it routes to, govern
*development of this repository itself* (branching, commits, PRs, merges,
validation, documentation, and how the Skills are orchestrated). That is
distinct from how either Skill reviews an *external* repository — that
behavior is defined in each Skill's own `SKILL.md`.

---

## Entry gate: branch validation precondition

**Before anything else** — before routing to a task-specific policy below
and before any tool call that modifies an implementation or documentation
file — confirm the work is on an appropriate dedicated task branch per
[`policies/repository-workflow.md`](policies/repository-workflow.md). That
policy's required order (inspect state, verify/sync the base, preserve any
existing work, create the task branch, switch to it) must reach its final
step before a single implementation or documentation file may be edited.
This precondition gates every task in this repository; it is not one item
to weigh alongside the Global invariants below, and no task routing rule
or policy file relaxes it.

---

## Core Vocabulary: Agent via Skill

```text
Agent
= stable software-engineering role
  (e.g. "Code Review Agent")
  defined by responsibility and scope, not by implementation

Skill
= portable operational definition of the Agent
  (instructions, rules, templates)
  authored once, consumed by any runtime

Subagent / Worker
= optional internal execution mechanism used by an Agent
  (a runtime-specific way of parallelizing or delegating work)
  an implementation detail, never the definition of the Agent itself

Runtime
= environment consuming/executing the Skill
  (Claude Code, Codex, Cursor, or any other agent runtime)
```

**Canonical principle:**

```text
Agent via Skill
```

The Code Review Agent is defined by the `SKILL.md` files under `skills/`.
None is defined as a Claude-specific subagent, a Codex-specific agent, a
Cursor-specific agent, an Anthropic API workflow, or any runtime-specific
worker syntax. Runtime adapters (e.g. `CLAUDE.md`) may exist separately,
but never redefine an Agent — they only bootstrap a runtime into reading
the canonical Skills.

---

## Global invariants

These apply to **every** task in this repository, regardless of which
policy file below owns the detail. Each is a short invariant here; the
canonical, detailed rule lives in the policy named after it.

- **Runtime neutrality.** Canonical repository behavior — this file,
  `policies/`, and each Skill's own files — must not
  depend on Claude-, Anthropic-, Codex-, or Cursor-specific tools,
  APIs, or subagent-orchestration syntax. Runtime adapters may exist
  separately but never fork these rules. Canonical:
  [`policies/skill-development-policy.md`](policies/skill-development-policy.md).
- **Dedicated task branch.** See the **Entry gate** above, which states
  this as a mandatory precondition rather than one invariant among many:
  every materially separate task runs on a freshly created task branch off
  its synchronized base (`main`, or `release/v3` while v3 is being built), never directly on `main` or a previous task's
  branch, and never by discarding or blending unrelated local work. This
  is an agent workflow check, not something recorded as evidence in
  repository history (no empty commits, PR checklist items, or file
  comments asserting it). Canonical:
  [`policies/repository-workflow.md`](policies/repository-workflow.md).
- **Read-only Git safety.** Destructive Git shortcuts (`git reset
  --hard`, `git clean -fd`, force push, ancestry-hiding branch deletion,
  history rewriting for convenience) are prohibited; on unexpected state,
  preserve → inspect → report → do not guess. Canonical:
  [`policies/git-pr-merge-policy.md`](policies/git-pr-merge-policy.md).
- **Clean task exit.** Every task finishes in a known clean state — the
  right branch, intended work committed, no unrelated modifications, no
  stray generated artifacts or Python cache, no destructive cleanup used
  to manufacture that state. Canonical:
  [`policies/validation-and-clean-exit.md`](policies/validation-and-clean-exit.md).
- **Full tests and full verification run only in GitHub Actions.** An
  Agent never runs the full test suite or the full verification sequence
  locally; it runs only the targeted subset relevant to the change, and
  `.github/workflows/validate.yml` is the sole place the full run happens.
  Canonical:
  [`policies/validation-and-clean-exit.md`](policies/validation-and-clean-exit.md).
- **Packaged Skills are independent of repository-level instructions.**
  No packaged Skill file (`SKILL.md` and the `rules/`, `templates/`
  and checklist files beside it) may depend on this repository's own
  `AGENTS.md` or `policies/`; a distributed archive never contains them. Canonical:
  [`policies/skill-development-policy.md`](policies/skill-development-policy.md).
- **Reviewer/author separation and explicit per-run review.** An implementing
  Agent never invokes `review-publish-github` on the PR it just opened or
  updated, and no review Skill is invoked automatically — every run needs
  the user's own request in that conversation (S2). Canonical:
  [`policies/review-orchestration-policy.md`](policies/review-orchestration-policy.md).
- **Python Authoring.** Repository-owned Python (`scripts/**/*.py`,
  `tests/**/*.py`) follows
  [`policies/python_scripts_coding_policy.md`](policies/python_scripts_coding_policy.md):
  concise, intent-focused comments; durable explanation lives in `docs/` or
  `policies/`, not in module prose.
- **One canonical home per rule.** A normative rule has exactly one
  canonical location. Other files (this one included) summarize and link;
  they do not restate a rule in a way that can drift independently.
- **Skill instruction ownership.** Every normative review rule has exactly
  one owner: the Core owns severity, evidence, the verdict rule and the
  shared safety guarantees (S1–S5, S10); each mini-skill owns the rules of
  its own capability (S7–S9 sit with `review-publish-github`,
  `review-runtime-check` and `review-requirements`). Other files reference
  the owner by Skill name and never restate or weaken the rule. A Skill is
  its `SKILL.md` with the inline procedure plus a few rule and template
  files that `SKILL.md` lists and reads in full; there is no loading
  inventory, conditional loading, activation predicate or runbook layer.
  Mini-skills are selected under the activation modes of ADR §5.1
  (`intent` by default, `auto` only when the user opts in), never by the
  content of the reviewed repository. Prefer simplifying an existing
  contract over adding a checkpoint, manifest, abstraction, or layer; a new
  layer needs a responsibility no existing one can fulfil. Context
  efficiency never outranks correctness or safety: judge a reduction by
  verified behavior, not token savings alone. This bullet is the canonical
  statement; packaging and authoring detail stays in
  [`policies/skill-development-policy.md`](policies/skill-development-policy.md).
- **File size is a review trigger, not a limit.** When a production file
  (a Skill file, policy, template, script, workflow, or
  reference doc) grows past roughly 300 lines, treat that as a prompt to
  check whether it owns more than one responsibility, restates a contract
  that is canonical elsewhere, mixes orchestration with implementation, or
  has a natural extraction boundary. If one applies, decompose along that
  boundary while preserving behavior, public contracts, and packaging; if
  none applies and the file is genuinely cohesive, a large file is fine.
  Line count alone is never a CI-enforced limit.
- **Thin, layered documentation.** README files are orientation and
  navigation surfaces, not capability encyclopedias: the root
  [`README.md`](README.md) gives the product overview, Skill selection and
  links onward; each Skill folder's own `SKILL.md` is its contract;
  [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) is the concise system map;
  `policies/` owns exact repository-development semantics. Prefer a link to
  the smallest appropriate layer over copying an explanation into several
  READMEs. READMEs and `docs/` are explanatory — a canonical policy or
  `SKILL.md` wins any conflict. A user-visible capability change requires
  a **documentation-impact check** that updates the smallest affected
  layer; an implementation change with no user-visible effect requires no
  README change. Canonical:
  [`policies/documentation-policy.md`](policies/documentation-policy.md).
- **Concise, layered PR descriptions.** Pull-request descriptions are concise
  change summaries and navigation surfaces, not duplicate specifications;
  detailed requirements and semantics stay in their canonical Issues, docs,
  policies, or Skill rules. Canonical:
  [`policies/github-issue-pr-authoring.md`](policies/github-issue-pr-authoring.md).
- **Agent-authored PRs use the canonical PR template.** A Pull Request an
  agent creates, or materially updates, starts from
  `.github/PULL_REQUEST_TEMPLATE.md`, fills its intended fields/sections,
  and removes or replaces its placeholder/guidance content — never an
  independently invented body structure. Canonical:
  [`policies/github-issue-pr-authoring.md`](policies/github-issue-pr-authoring.md).
- **CHANGELOG categories express SemVer intent.** Compatible corrections and
  refinements use `Fixed`; intentional backward-compatible behavior or
  capability changes use `Changed` or `Added`. Canonical:
  [`policies/release-changelog-policy.md`](policies/release-changelog-policy.md).
- **Release intent belongs in the PR body, checked before opening it.**
  A release-worthy change must declare `Release category:` / `Release
  entry:` lines in the pull request description — CHANGELOG.md is never
  edited directly. Before running `gh pr create` or `gh pr edit`, validate
  the drafted body locally with the same deterministic checker CI runs
  (`scripts/release/release_worthiness.py assess --require-release-intent`)
  instead of waiting for CI to catch a missing or invalid category.
  Canonical:
  [`policies/github-issue-pr-authoring.md`](policies/github-issue-pr-authoring.md),
  "Validate release intent before opening or updating a PR".
- **Contribution ownership and Issue classification.** An agent that creates
  or materially restructures GitHub Issues considers ownership and blast
  radius, classifies contributor suitability (maintainer-led / good first
  issue / contributor-owned), and consults the canonical contribution
  policy. It never marks sensitive core review behavior as beginner work
  merely because the implementation looks small, considers extracting safe
  contributor child Issues from larger Epics, and preserves maintainer
  ownership of semantic and architectural contracts. Canonical:
  [`policies/contribution-ownership-policy.md`](policies/contribution-ownership-policy.md).
- **Engineering guardrails.** Respect documented dependency direction and
  ownership, consolidate only provably equivalent behavior, keep tests
  isolated, establish a check's purpose before removing it, measure before
  optimizing, keep packaged output deterministic and byte-identical, keep
  benchmark evaluation independent, and review the exact change — an
  incomplete review is never clean. Canonical:
  [`policies/engineering-guardrails.md`](policies/engineering-guardrails.md).
- **Native GitHub relationships for declared Issue dependencies.** An
  agent that creates or materially restructures an Issue's declared
  `Parent:`/`Children:`/`Depends on:`/`Blocks:` fields also creates the
  matching native GitHub parent/sub-issue or dependency relationship in
  the same operation, verifies it by re-fetching afterward, never
  represents a dependency as a parent/sub-issue relationship (or vice
  versa), and leaves a generic `Related:` reference or an ambiguous/
  cyclic/missing-Issue relationship as prose only. Canonical:
  [`policies/github-issue-pr-authoring.md`](policies/github-issue-pr-authoring.md),
  "Native GitHub relationships".

---

## Instruction precedence

When instructions overlap, the more specific and more authoritative
source wins, in this order:

1. **The user's / calling task's explicit instructions** for the task at
   hand.
2. **This file's Global invariants**, and the canonical `policies/` file
   the task routes to. Where a Global invariant above is only a summary,
   the routed policy's full text is authoritative.
3. **Skill canonical sources** — each `SKILL.md` and the rule and template
   files it lists — for Skill behavior.
4. **Explanatory documentation** — `README.md` and `docs/` — which
   explains, navigates, and models, but never overrides a canonical
   source.

**Canonical vs. explanatory.** `AGENTS.md`, everything under `policies/`,
and each Skill folder's `SKILL.md`, `rules/`, `templates/` and checklist
files are **canonical** (they define behavior). `README.md` and everything
under `docs/` are **explanatory** (they describe and navigate). An
explanatory file that appears to conflict with a canonical one is a
documentation bug to fix, not a competing rule.

**Runtime adapters** (e.g. `CLAUDE.md`) only bootstrap a runtime into
reading these canonical rules. They never duplicate or override them.

How a review treats instruction files inside a repository being reviewed
(conventions only, never authority) is owned by `review-core`'s
`rules/safety.md`, not by this section.

---

## Task routing

Read this file's Global invariants and Instruction precedence for **any**
task. Then read the one canonical policy that owns your task. For a short
directory map of the routed policies, see
[`policies/README.md`](policies/README.md) (navigational only — not
normative).

| Task / concern | Canonical instruction source |
| --- | --- |
| Any repository task | this file — **Global invariants** + **Instruction precedence** |
| Task-branch creation, base synchronization, dirty-tree / stash handling, branch naming, resuming a task branch | [`policies/repository-workflow.md`](policies/repository-workflow.md) |
| Commit, push, PR creation and assignment, merge strategy, merge safety, squash cleanup, destructive-Git prohibitions | [`policies/git-pr-merge-policy.md`](policies/git-pr-merge-policy.md) |
| Clean task end state, Python cache/bytecode cleanup, shell/PowerShell script parity, running repository validation & packaging | [`policies/validation-and-clean-exit.md`](policies/validation-and-clean-exit.md) |
| Engineering habits for any code, test, CI, packaging, benchmark, or review-process change — dependency direction and ownership, equivalent-only consolidation, test isolation, purpose-before-removal, measure-before-optimizing, deterministic distribution, benchmark independence, exact-change review | [`policies/engineering-guardrails.md`](policies/engineering-guardrails.md) |
| Repository documentation (`README.md`, `docs/`, Skill `README.md`) — structure and reading experience | [`policies/documentation-policy.md`](policies/documentation-policy.md) |
| Content of agent-authored GitHub Issues and Pull Requests — how much detail belongs in the body, per-field size guidance, PR summary shape, summarized validation, linking canonical docs instead of duplicating them, the local release-intent pre-flight check before `gh pr create` / `gh pr edit`, creating and verifying native GitHub parent/sub-issue and dependency relationships for declared `Parent`/`Children`/`Depends on`/`Blocks` fields | [`policies/github-issue-pr-authoring.md`](policies/github-issue-pr-authoring.md) |
| Filing a maintainer-identified engineering defect (`.github/ISSUE_TEMPLATE/engineering-bug.yml`) — contract/invariant mismatches, incorrect execution semantics, security-boundary violations, and similar defects a maintainer has already diagnosed, as distinct from the general-purpose `bug-report.yml` chooser entry | [`policies/github-issue-pr-authoring.md`](policies/github-issue-pr-authoring.md) |
| Ownership and contributor-suitability classification of GitHub Issues — contribution classes, classification criteria (blast radius, not patch size), assignment behavior, Epic decomposition, sensitive areas excluded from first issues, handling ambiguous cases | [`policies/contribution-ownership-policy.md`](policies/contribution-ownership-policy.md) |
| CHANGELOG category selection and its deterministic SemVer intent | [`policies/release-changelog-policy.md`](policies/release-changelog-policy.md) |
| Skill behavior, authoring and maintaining Skills (one owner per rule, the `SKILL.md` + rules + templates shape, the ADR §5.1 activation modes), Skill packaging, runtime adapters, portability of packaged files | [`policies/skill-development-policy.md`](policies/skill-development-policy.md) |
| Review orchestration — implementer/reviewer separation, the explicit per-run request (S2), Skill-consumer branch discipline, human-facing review publication | [`policies/review-orchestration-policy.md`](policies/review-orchestration-policy.md) |
| Repository-owned Python (`scripts/**/*.py`, `tests/**/*.py`) | [`policies/python_scripts_coding_policy.md`](policies/python_scripts_coding_policy.md) |

An agent should never have to grep the whole repository to guess which
rules apply: if a task is not covered by a row above, it is governed by
the Global invariants alone, and a new focused policy should be added
(see **Maintainability and extension** below) rather than expanding this
file with detailed procedure.

---

## Repository development vs. packaged Skill runtime

Everything in this file and under `policies/` is **repository-development
instruction**: it governs how *this* source repository is built,
reviewed, packaged, and documented. It is never shipped.

A distributed Skill archive contains only that Skill's `SKILL.md` and the
`rules/`, `templates/` and checklist files it lists. If a rule must survive
packaging, its canonical portable form belongs inside one of those files —
not in a repository-level `policies/` file introduced to keep this file
short. The full boundary, including target-repository instruction
discovery (which *is* valid packaged behavior), is owned by
[`policies/skill-development-policy.md`](policies/skill-development-policy.md).

---

## Maintainability and extension

This file must stay a stable entrypoint and routing layer. Do not let it
regrow into a monolith. The criterion is **not** a line limit — it is
responsibility.

- Keep in this file only genuinely global material: repository-wide
  safety invariants, instruction precedence, the canonical-vs-explanatory
  distinction, the task-routing table, the packaged-Skill independence
  boundary, and this maintainability rule.
- Put a **substantial, independently ownable policy domain** in its own
  focused file under `policies/`, and add a routing row above. Prefer a
  small number of meaningful domains over many tiny files.
- Give every **directory people navigate directly** to find policies,
  contracts, or guidance a concise navigational README entrypoint (this
  applies to `policies/`, `tests/`, `benchmark/` and
  `runtime_platform/benchmark/` today — not to every directory). The canonical rule is
  in
  [`policies/documentation-policy.md`](policies/documentation-policy.md),
  "Navigational README for user-facing policy/guidance directories."
- Add a rule to this file's Global invariants only when it truly applies
  to *every* repository task and is short enough to state as an
  invariant. Otherwise it belongs in a routed policy.
- Never create a second normative copy of a rule. When a concise
  invariant must appear here, phrase it as a summary and route to the
  canonical policy; do not paste the detailed rule into both.
- Optimize for discoverability and low cognitive load: a new coding agent
  should read this file first and immediately know the global invariants,
  which policy to read next, what is canonical, what is explanatory, what
  applies to repository development, and what applies to packaged Skill
  runtime.

---

## Map

```text
CLAUDE.md (or any other runtime adapter)
    ↓
AGENTS.md   (this file — global invariants, precedence, routing)
    ↓
policies/   (repository-development policy domains, routed from this file)
    ↓
skills/review-core/SKILL.md          (the Core: shared review rules)
skills/review-*/SKILL.md             (mini-skills, selected per ADR §5.1)
```

Runtime adapters bootstrap a specific runtime into these canonical rules.
They must never duplicate or override them. The detailed layering rule is
owned by
[`policies/skill-development-policy.md`](policies/skill-development-policy.md),
"Relationship to Runtime Adapters and the Skills."
