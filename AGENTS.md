# AGENTS.md

This is the **canonical, runtime-neutral, repository-wide entrypoint** for
development of this repository. Every implementation task — regardless of
which runtime executes it — starts here, then follows the routing below
into the focused policy that owns the task's detailed rules.

This repository hosts **two portable Code Review Agent Skills** that
share one review standard:

- [`skills/local-code-review/SKILL.md`](skills/local-code-review/SKILL.md)
  — reviews local Git implementation state and returns findings;
- [`skills/github-pr-review/SKILL.md`](skills/github-pr-review/SKILL.md)
  — reviews GitHub Pull Requests and, when active, publishes findings and
  a final decision.

Both consume the same shared review rules in
[`shared/policies/`](shared/policies/) and
[`shared/templates/`](shared/templates/), so P0/P1/P2 review semantics
never diverge between them — see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for
the module map.

This file, and the [`policies/`](policies/) it routes to, govern
*development of this repository itself* (branching, commits, PRs, merges,
validation, documentation, and how the Skills are orchestrated). That is
distinct from how either Skill reviews an *external* repository — that
behavior is defined in each Skill's own `SKILL.md`.

---

## Core Vocabulary: Agent via Skill

```text
Agent
= stable software-engineering role
  (e.g. "Code Review Agent")
  defined by responsibility and scope, not by implementation

Skill
= portable operational definition of the Agent
  (instructions, policies, templates, runbooks)
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

Each Code Review Agent is defined by its own `SKILL.md`. Neither is
defined as a Claude-specific subagent, a Codex-specific agent, a
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
  `policies/`, `shared/`, and each Skill's own `SKILL.md` — must not
  depend on Claude-, Anthropic-, Codex-, or Cursor-specific tools,
  APIs, or subagent-orchestration syntax. Runtime adapters may exist
  separately but never fork these rules. Canonical:
  [`policies/skill-development-policy.md`](policies/skill-development-policy.md).
- **Dedicated task branch.** Every materially separate task runs on a
  freshly created task branch off synchronized `main`; never implement
  directly on `main` or continue on a previous task's branch, and never
  discard or blend unrelated local work to get there. Canonical:
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
- **Packaged Skills are independent of repository-level instructions.**
  No packaged Skill resource (`SKILL.md`, a packaged policy, runbook,
  template, or `shared/`-packaged resource) may depend on this
  repository's own `AGENTS.md` or `policies/`; a distributed archive
  never contains them. Canonical:
  [`policies/skill-development-policy.md`](policies/skill-development-policy.md).
- **Reviewer/author separation and opt-in local review.** An implementing
  Agent never invokes `github-pr-review` on the PR it just opened or
  updated, and `local-code-review` is never invoked automatically — every
  invocation needs fresh, explicit user approval. Canonical:
  [`policies/review-orchestration-policy.md`](policies/review-orchestration-policy.md).
- **Python Authoring.** Repository-owned Python (`scripts/**/*.py`,
  `tests/**/*.py`) follows
  [`policies/python_scripts_coding_policy.md`](policies/python_scripts_coding_policy.md):
  concise, intent-focused comments; durable explanation lives in `docs/`,
  `policies/`, or `shared/policies/`, not in module prose.
- **One canonical home per rule.** A normative rule has exactly one
  canonical location. Other files (this one included) summarize and link;
  they do not restate a rule in a way that can drift independently.

---

## Instruction precedence

When instructions overlap, the more specific and more authoritative
source wins, in this order:

1. **The user's / calling task's explicit instructions** for the task at
   hand.
2. **This file's Global invariants**, and the canonical `policies/` file
   the task routes to. Where a Global invariant above is only a summary,
   the routed policy's full text is authoritative.
3. **Shared and Skill-level canonical sources** — `shared/policies/`,
   `shared/templates/`, each `SKILL.md`, and each Skill's own
   `policies/`, `runbooks/`, and `templates/` — for Skill behavior.
4. **Explanatory documentation** — `README.md`, `docs/`, and each Skill's
   `README.md` — which explains, navigates, and models, but never
   overrides a canonical source.

**Canonical vs. explanatory.** `AGENTS.md`, everything under `policies/`
and `shared/policies/`, each `SKILL.md`, and each Skill's own
`policies/`, `runbooks/`, and `templates/` are **canonical** (they define
behavior). `README.md`, everything under `docs/`, and each Skill's
`README.md` are **explanatory** (they describe and navigate). An
explanatory file that appears to conflict with a canonical one is a
documentation bug to fix, not a competing rule.

**Runtime adapters** (e.g. `CLAUDE.md`) only bootstrap a runtime into
reading these canonical rules. They never duplicate or override them.

For precedence *between instruction files inside a repository being
reviewed* (a target repo's `AGENTS.md` vs. its `CLAUDE.md`), see
[`shared/policies/repository-instructions.md`](shared/policies/repository-instructions.md)
— that is packaged Skill behavior, not this section.

---

## Task routing

Read this file's Global invariants and Instruction precedence for **any**
task. Then read the one canonical policy that owns your task:

| Task / concern | Canonical instruction source |
| --- | --- |
| Any repository task | this file — **Global invariants** + **Instruction precedence** |
| Task-branch creation, base synchronization, dirty-tree / stash handling, branch naming, resuming a task branch | [`policies/repository-workflow.md`](policies/repository-workflow.md) |
| Commit, push, PR creation and assignment, merge strategy, merge safety, squash cleanup, destructive-Git prohibitions | [`policies/git-pr-merge-policy.md`](policies/git-pr-merge-policy.md) |
| Clean task end state, Python cache/bytecode cleanup, shell/PowerShell script parity, running repository validation & packaging | [`policies/validation-and-clean-exit.md`](policies/validation-and-clean-exit.md) |
| Repository documentation (`README.md`, `docs/`, Skill `README.md`) — structure and reading experience | [`policies/documentation-policy.md`](policies/documentation-policy.md) |
| Skill behavior, Skill packaging, runbook / policy / template ownership, runtime adapters, portability of packaged resources | [`policies/skill-development-policy.md`](policies/skill-development-policy.md) |
| Review orchestration — implementer/reviewer separation, the `local-code-review` approval gate, review ownership, Skill-consumer branch discipline, human-facing review publication | [`policies/review-orchestration-policy.md`](policies/review-orchestration-policy.md) |
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

A distributed Skill archive contains only `SKILL.md`, that Skill's
packaged `policies/`, `runbooks/`, `templates/`, `metadata/`, and its
`shared/`-packaged resources. If a rule must survive packaging, its
canonical portable form belongs inside one of those packaged resource
types — not in a repository-level `policies/` file introduced to keep
this file short. The full boundary, including target-repository
instruction discovery (which *is* valid packaged behavior), is owned by
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
shared/     (review policies/templates common to both Skills)
    ↓
skills/local-code-review/SKILL.md
skills/github-pr-review/SKILL.md
```

Runtime adapters bootstrap a specific runtime into these canonical rules.
They must never duplicate or override them. The detailed layering rule is
owned by
[`policies/skill-development-policy.md`](policies/skill-development-policy.md),
"Relationship to Runtime Adapters and the Skills."
