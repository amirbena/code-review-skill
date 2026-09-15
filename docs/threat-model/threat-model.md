# Threat Model

Repository-development design record for **[#300](https://github.com/amirbena/code-review-skill/issues/300)**.
Not packaged; explanatory. This is the canonical home for `code-review-skill`'s
trust domains, adversary/failure models, security assumptions, and
capability-boundary architecture. The operative, machine-checkable artifact is
[`catalog/`](catalog/) — this document explains the architecture the catalog
implements; it does not restate every scenario. See [`README.md`](README.md)
for the document map.

## 1. Problem and goal

`code-review-skill` runs two Code Review Agents (`local-code-review`,
`github-pr-review`) against **untrusted repository and PR content** — a
malicious or compromised contributor's diff, filenames, comments, tests,
fixtures, task definitions, and instruction files. The review agent itself
may also be non-cooperative: incorrect, prompt-injected, or (via a spawned
child, a nested tool call, or an alternate identity) attempting to acquire
authority it was not granted.

Enforcement and regression coverage for this can become reactive: a runtime
can prove that individual controls work — a sandbox denies network access,
a mutation gate rejects an unauthorized patch — without ever proving that
the *important attacker paths* are covered end to end. This document, and
the canonical catalog it introduces, close that gap: they state what is
untrusted, what an adversary may control, which boundaries must hold, and
which concrete scenarios the runtime-enforcement issues
([#301](https://github.com/amirbena/code-review-skill/issues/301),
[#302](https://github.com/amirbena/code-review-skill/issues/302),
[#303](https://github.com/amirbena/code-review-skill/issues/303)) must
withstand — in a form
[#305](https://github.com/amirbena/code-review-skill/issues/305)/[#306](https://github.com/amirbena/code-review-skill/issues/306)/[#307](https://github.com/amirbena/code-review-skill/issues/307)
(benchmarks), [#299](https://github.com/amirbena/code-review-skill/issues/299)
(security-event taxonomy),
[#308](https://github.com/amirbena/code-review-skill/issues/308) (event
benchmark), and
[#310](https://github.com/amirbena/code-review-skill/issues/310)
(traceability) can all mechanically consume.

## 2. Design constraint: capabilities, not cooperation

Per #300's own design constraint, this model **must remain useful even if
the reviewing model is fully non-cooperative**. Every scenario in the
catalog is therefore expressed as:

```text
threat
  → attacker-controlled inputs/capabilities
    → protected boundary
      → expected enforcement point
        → expected safe outcome
          → expected security event (when applicable)
            → benchmark coverage
              → implementation/regression evidence
```

never as "the model should not...". A rule phrased only in terms of model
behavior is not enforceable against a non-cooperative or compromised agent;
a rule phrased in terms of a capability the runtime does or does not grant,
a boundary the runtime does or does not check, and an outcome that is
observable regardless of what the model was instructed to do, is. This is
the same discipline
[#302](https://github.com/amirbena/code-review-skill/issues/302)'s own
scope already states: *"The success condition is runtime denial /
termination / containment. Tests must fail if the hostile operation
succeeds regardless of what the reviewer/model was instructed to do."*
This threat model generalizes that discipline to every boundary, not only
the sandbox.

## 3. Trust domains

```text
┌───────────────────────────────────────────────────────────────────────┐
│  TRUSTED                                                               │
│  ┌─────────────────────┐   ┌───────────────────────────────────────┐  │
│  │ user / maintainer     │   │ authorization capability source       │  │
│  │ intent                │   │ (trusted runtime channel only)        │  │
│  └─────────────────────┘   └───────────────────────────────────────┘  │
│                                                                          │
│  CONTEXTUAL (trusted identity, untrusted content)                       │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │ review-performing agent  ──▶  nested / parallel agents          │    │
│  │            │                          │                          │   │
│  │            ▼                          ▼                          │   │
│  │   agent-spawn / delegation runtime (bounded, non-transferable)   │   │
│  └───────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  UNTRUSTED (adversarial by default)                                     │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │ repository & PR contents  │ repository instruction files        │   │
│  │ (diff, filenames, comments,│ (AGENTS.md, CLAUDE.md, contribution │   │
│  │  tests, fixtures)          │ docs, task definitions)             │   │
│  ├───────────────────────────┴─────────────────────────────────────┤  │
│  │ repository-defined executable code and validation commands       │  │
│  └───────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  BOUNDED EXECUTION SURFACES                                             │
│  ┌───────────────────┐ ┌───────────────────┐ ┌────────────────────┐  │
│  │ checkout / working  │ │ runtime-validation  │ │ GitHub integration │  │
│  │ copy (disposable,   │ │ sandbox (disposable,│ │ & mutation surface │  │
│  │ ownership-marked)   │ │ credential-free,    │ │ (capability-gated) │  │
│  │                     │ │ network-denied)     │ │                     │  │
│  └───────────────────┘ └───────────────────┘ └────────────────────┘  │
│                                                                          │
│  MUTATION AUTHORITY (separate from review reasoning and proposal)       │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │ remediation proposal (PROPOSE_PATCH, advisory only)              │   │
│  │        │                                                         │   │
│  │        ▼  requires a fresh, trusted, single-use authorization     │  │
│  │  mutation executor (APPLY_PATCH → COMMIT → PUSH, independently   │   │
│  │  authorized, never inherited or replayed)                        │   │
│  └───────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ALWAYS OFF-LIMITS                                                      │
│  ┌───────────────────────────────────────────────────────────────┐    │
│  │ host filesystem / credentials / network  │  external services    │  │
│  └───────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────┘
```

| Trust domain | Trusted? | Notes |
| --- | --- | --- |
| User / maintainer intent | Trusted | The only source that can grant `APPLY_PATCH`/`COMMIT`/`PUSH` authorization or a formal GitHub review action. |
| Authorization capability source | Trusted, narrow | A dedicated trusted runtime channel, never repository text, PR text, findings, flags, generated metadata, or a nested agent (see `AUTH-003`, `AUTH-004`). |
| Review-performing agent | Trusted identity, untrusted output | The agent's own reasoning may be wrong or compromised (`compromised_agent` model); capability checks must not assume good faith. |
| Nested / parallel agents | Trusted identity, bounded and non-transferable authority | A child never automatically inherits a parent's mutation or review-action authorization (`AUTH-013`, `DELEG-007`). |
| Agent-spawn / delegation runtime | Trusted mechanism, must enforce bounds | Owns depth/count budgets and capability-subset delegation (`#303`). |
| GitHub integration & mutation surface | Capability-gated | `github-pr-review` never receives `APPLY_PATCH`/`COMMIT`/`PUSH` (local mutation is `#132`'s domain only); formal review actions are separately gated by the existing self-review boundary (`AUTH-014`). |
| Repository and PR contents | **Untrusted** | Diff, filenames, comments, tests, fixtures — all attacker-controlled under the `malicious_contributor` model. |
| Repository instruction files | **Untrusted** | `AGENTS.md`, `CLAUDE.md`, contribution docs, task definitions — read as Repository Context, never as an authority source (`INJECT-001`). |
| Repository-defined executable code and validation commands | **Untrusted**, execution bounded | Runs only inside the `#302` sandbox, never against the host. |
| Checkout / working copy | Bounded execution surface | Disposable, ownership-marked, path-escape-checked (`GIT-007`–`GIT-009`). |
| Remediation proposal vs. mutation executor | Structurally separate | `PROPOSE_PATCH` cannot mutate; `APPLY_PATCH` is a distinct, narrowly authorized capability (`#301`). |
| User-issued mutation authorization | Trusted, single-use | Bound to an exact patch digest, target, base state, and invocation; never replayable (`AUTH-006`–`AUTH-012`). |
| Runtime-validation sandbox | Bounded execution surface | Network-denied, credential-free, filesystem-bounded, resource-budgeted (`#302`). |
| Host filesystem / credentials / network | **Always off-limits** | Never exposed to the review agent or the sandbox by design, not merely by policy. |
| External services | **Always off-limits** | No outbound access except the GitHub integration's own narrow, capability-gated calls. |

## 4. Adversary / failure models

Every scenario in the catalog is tagged with exactly one of these six
`attacker_model` values — the full, closed set; a scenario the model
doesn't fit is a sign the taxonomy needs an issue-tracked extension, not an
ad hoc seventh value invented per scenario:

1. **`malicious_contributor`** — controls the PR diff, filenames,
   repository text, test code, task definitions, and instruction files
   reachable through the review scope. This is the baseline adversary:
   every other model assumes at least this level of content control.
2. **`prompt_injected_context`** — repository or PR text attempts to
   redefine authority, disable safety policy, request secrets, trigger
   mutations, widen scope, or override system/runtime constraints. A
   specialization of `malicious_contributor` called out separately
   because its *mechanism* (natural-language instruction embedded in
   otherwise-inert content) is structurally different from a code-level
   exploit and needs its own scenario family (`INJECT-###`).
3. **`compromised_agent`** — the review agent itself reasons incorrectly,
   ignores policy, attempts an unavailable capability, over-expands its
   task, attempts to mutate while read-only, or attempts to spawn/delegate
   beyond its granted authority. This model is why every boundary in this
   document is a capability check, never a request the agent is merely
   asked not to make.
4. **`confused_deputy`** — one agent, identity, bot, token, subprocess, or
   tool tries to obtain stronger authority by delegating to another actor,
   by recursively spawning agents to evade a per-agent constraint, or by
   transferring a non-transferable capability to a child. Distinct from
   plain `compromised_agent` because the exploit routes *through* a
   second, otherwise-legitimate actor.
5. **`runtime_misconfiguration`** — a capability is accidentally exposed,
   network is unexpectedly available, credentials are mounted, a sandbox
   boundary is incomplete, a stale HEAD or stale patch approval is
   accepted, spawn limits are not enforced, child authority is widened, or
   a cleanup assumption fails. No attacker intent required — this model
   covers the runtime failing its own contract.
6. **`resource_abuse`** — huge or cyclic repository structures,
   pathological diffs, unbounded generated output, subprocess forks,
   recursive agent spawning, excessive parallel workers, decompression
   bombs, or intentionally expensive validation paths. Distinguished from
   the others because the goal is denial of service, not privilege
   escalation or data exfiltration.

## 5. Security assumptions

These are the load-bearing assumptions every scenario in the catalog
relies on. If one of these stops holding, the corresponding scenarios'
`expected_safe_outcome` no longer applies and the catalog needs revision,
not silent reinterpretation.

- **The trusted authorization channel is genuinely out of reach of
  repository/PR content.** If the same channel that carries user
  authorization can be reached by repository text (e.g. a shared prompt
  context with no structural separation), `AUTH-003`/`AUTH-004`/`INJECT-003`
  degrade to unenforceable.
- **Capability checks happen in a layer the reviewed content cannot
  execute code in.** If capability gating is itself implemented as
  instructions the LLM reads rather than a structural check outside the
  model's own token stream, every `compromised_agent` and
  `prompt_injected_context` scenario degrades to "the model should not,"
  which #300 explicitly rules out as a sufficient control.
- **A spawned child starts with the empty capability set by default.**
  Every `DELEG-###` and `AUTH-013` scenario assumes non-transferability is
  the default, not an opt-out.
- **The sandbox's isolation primitives are either real or the runtime
  fails closed.** `SBOX-013` names this explicitly: a missing isolation
  primitive must report `unavailable`, never silently fall back to host
  execution.
- **Post-mutation and post-execution verification actually runs.** Several
  `AUTH-###`/`SBOX-###` outcomes ("unexpected change is detected") depend
  on a verification step executing after every mutation/validation, not
  only on the gate before it.
- **A denial, a failure, or incomplete evidence is never silently upgraded
  to a clean result.** `SCOPE-004` and `SCOPE-005` name this as the single
  highest-leverage assumption in the catalog: every other boundary's
  safety depends on this one holding.

## 6. Capability-boundary architecture

The catalog groups scenarios into seven threat domains, each with a
stable ID-namespace prefix and one enforcement owner (an open issue, or an
`existing:`-cited control already implemented in this repository):

| Prefix | Domain | Enforcement owner | Benchmark family |
| --- | --- | --- | --- |
| `AUTH-###` | Mutation / authority: `READ_ONLY → PROPOSE_PATCH → USER_APPROVES → APPLY_PATCH → VERIFY`, with `COMMIT`/`PUSH` independently authorized | [#301](https://github.com/amirbena/code-review-skill/issues/301) | `mutation/#305` |
| `SBOX-###` | Sandbox / runtime validation: network, credentials, filesystem, GitHub API, process/resource budgets, fail-closed on unavailable primitives | [#302](https://github.com/amirbena/code-review-skill/issues/302) | `sandbox/#306` |
| `DELEG-###` | Agent spawning / delegation: capability grants, depth/count budgets, non-transferable authority, confused-deputy resistance | [#303](https://github.com/amirbena/code-review-skill/issues/303) | `delegation/#307` |
| `INJECT-###` | Repository / prompt injection: instruction files, embedded tool-call text, scope-widening text, secret/network requests, fabricated evidence | mixed — see §7 | mostly `none` (reasoning-discipline; downstream capability crossings are covered by `AUTH`/`SBOX`/`DELEG`) |
| `GIT-###` | Checkout / Git safety: hooks, filters/textconv, pager, fsmonitor, submodules, config, symlink/path escape, cleanup ownership | mixed — see §7 | `sandbox/#306` where broader than the existing checkout control |
| `SCOPE-###` | Scope / evidence integrity: Review Target widening, stale HEAD/base, fabricated settled evidence, failure-to-clean-verdict conversion | mixed — see §7 | mostly `none` (decision-semantics correctness, not a runtime capability) |
| `DOS-###` | Resource abuse: huge/cyclic repositories, pathological diffs, output bombs, unbounded process/agent trees, excessive parallelism | `#302` / `#303` (shared with `SBOX`/`DELEG`) | `sandbox/#306`, `delegation/#307` |

`INJECT-###`, `GIT-###`, and `SCOPE-###` are "mixed" because several of
their scenarios already have a real, existing owner in this repository
(e.g. `GIT-001`'s hooks-disabled control in
`tests/reference/review/pr_checkout.py`, or `INJECT-001`'s instruction
precedence rule in `shared/policies/repository-instructions.md`) rather
than an open `#298`-family issue — see §7.

## 7. Existing coverage vs. genuine gaps

A repository that already ships two Code Review Skills is not starting
from zero. Before assuming every scenario is a `#298`-family gap, this
catalog was built by first inspecting what real, tested controls already
exist:

- **Checkout safety is real and tested today.** `tests/reference/review/pr_checkout.py`
  disables hooks (`core.hooksPath=/dev/null`) and fsmonitor
  (`core.fsmonitor=false`) on every Git invocation, refuses cleanup outside
  the scratch parent or without the ownership marker (`_safe_rmtree`,
  `_OWNERSHIP_MARKER`), and rejects a resolved read outside the checkout
  root (`_require_inside`). `GIT-001`, `GIT-006`, `GIT-008`, and `GIT-009`
  cite this as `enforcement_owner: existing:` with real
  `regression_evidence`, not `COVERAGE_GAP`.
- **The self-review mutation boundary is real and tested today.**
  `skills/github-pr-review/policies/review-authority.md` and
  `review-action-authorization.md`, backed by
  `tests/unit/review/test_review_action_authorization.py`, already prevent
  a self-review from submitting a formal `APPROVE`/`REQUEST_CHANGES`
  action, including through a controlled alternate identity. `AUTH-014`
  cites this directly. This is a different authority domain from
  `#301`'s source/Git mutation capability model — the catalog keeps them
  as separate scenarios rather than conflating them.
- **Instruction-file trust precedence is real, but only at the reasoning
  layer.** `shared/policies/repository-instructions.md`, "Instruction
  precedence," already states that target-repository instructions must
  never override core reviewer safety boundaries, and
  `tests/unit/review/repository_intelligence/test_repository_instructions.py::test_symlink_escaping_repository_root_is_rejected`
  proves the path-safety half of that structurally. `INJECT-001` and
  `GIT-007` cite these. But this is LLM-reasoning discipline for the
  *instruction itself* — it is not a capability gate on what the
  instruction could trigger. The corresponding `AUTH`/`SBOX`/`DELEG`
  scenario is what actually gates the downstream action.
- **`#301`'s source/Git mutation capability model is now real and
  tested.** `shared/policies/mutation-authority.md` defines the
  read-only-by-default `READ_ONLY` → `PROPOSE_PATCH` →
  `USER_APPROVES_EXACT_PATCH` → `APPLY_PATCH` → `VERIFY_MUTATION`
  pipeline, with `COMMIT` and `PUSH` as separate, independently
  authorized capabilities, a dedicated mutation executor, and
  digest/base/invocation-bound, single-use, non-transferable,
  non-inheritable authorization. `tests/reference/review/mutation_authority.py`
  is the executable reference model and
  `tests/unit/security/test_mutation_authority.py` proves each
  `AUTH-001`..`AUTH-016` (excluding `AUTH-014`) denial structurally, over
  real Git repositories. `AUTH-013`'s spawn-boundary half and its
  `DELEG-007` counterpart split ownership: `#301` covers non-inheritance
  of authorization across a spawn boundary; spawn depth, budget, and
  process isolation stay `#303`'s genuine gap.
- **`#302`/`#303` themselves still own a genuine, currently-unimplemented
  gap.** No real sandbox isolation exists yet (the existing
  `shared/policies/runtime-validation.md` reference tests are explicitly
  described by `#302`'s own problem statement as "fake processes/
  repositories" that "do not prove host isolation"), and no agent-spawn
  budget/delegation model exists in this repository yet. These scenarios
  stay `enforcement_point: COVERAGE_GAP` and `regression_evidence:
  COVERAGE_GAP` — not because the catalog is incomplete, but because the
  runtime genuinely does not enforce them yet.

This distinction — real existing control vs. genuine `#298`-family gap —
is itself part of what makes the catalog useful: it prevents `#301`/`#302`/
`#303` from re-implementing something that already works, and prevents
anyone from assuming a documented policy is a proven boundary.

## 8. Denied-capability event taxonomy (`#299`, landed)

`#299` (`docs/security-events/security-event-model.md`) is the real,
authoritative security-event taxonomy. Every scenario whose
`expected_safe_outcome` is a runtime denial names one of a small, fixed
set of event-class names (for example, `DENIED_MUTATION_UNAUTHORIZED`,
`DENIED_SANDBOX_NETWORK_ACCESS`, `DENIED_SPAWN_BUDGET_EXCEEDED`) — see
[`scripts/security/validate_threat_model.py`](../../scripts/security/validate_threat_model.py),
`PROVISIONAL_EVENT_CLASSES`, for the exact closed set the validator
enforces (the constant keeps its pre-#299 name; #299 chose not to rename
it — see the catalog README's "Event taxonomy" section). A scenario whose
outcome is not itself a capability denial (a reasoning-discipline
scenario, a decision-semantics correctness property, or a genuine
platform-unavailability outcome) uses `NOT_APPLICABLE` instead — the
outcome the catalog considers safe simply is not "a capability was
denied." `#299` did not need to rename, split, or merge any pre-existing
entry from this catalog's own domains (`AUTH`/`SBOX`/`DELEG`); it added
three new names (`DENIED_REVIEW_ACTION_SELF_REVIEW`,
`DENIED_REVIEW_ACTION_UNAUTHORIZED`, `DENIED_REVIEW_ACTION_STALE_HEAD`)
for the GitHub review-action-mutation domain, which this catalog does not
itself model (`AUTH-014` is the one exception — see its updated
`expected_security_event`), plus a deterministic
`expected_denial` / `boundary_violation_attempt` classification that this
catalog does not carry per-scenario.

## 9. Threat-scenario severity is not review-finding severity

`shared/policies/severity.md` defines P0/P1/P2 for review findings — a
different concept entirely (how blocking a code-review observation is).
This catalog introduces a separate, closed four-value scale —
`CRITICAL`/`HIGH`/`MEDIUM`/`LOW` — for how severe a *threat scenario*
is if the corresponding boundary fails, and the validator rejects any
scenario whose `threat_severity` collides with a `P0`/`P1`/`P2` token.
The two scales are never compared or converted between each other.

## 10. How the catalog is used

```text
docs/threat-model/catalog/*.yaml   (this issue, #300 — canonical)
        │
        ├─▶ #301 / #302 / #303   select their category's AUTH/SBOX/DELEG
        │                        scenarios as the required regression set
        │                        for the runtime capability they build
        │
        ├─▶ #305 / #306 / #307   select the same scenarios as required
        │                        benchmark cases (`benchmark_family`)
        │
        ├─▶ #299                 confirms each scenario's
        │                        `expected_security_event` as a real,
        │                        stable, final event class
        │
        ├─▶ #308                 benchmarks that the mapped event actually
        │                        fires for every applicable scenario
        │
        └─▶ #310                 mechanically answers, per scenario id:
                                  enforcement owner? regression proof?
                                  benchmark case? mapped event? any layer
                                  missing?
```

Every field a downstream issue needs for this is already structural, not
prose: `category` (namespace), `enforcement_owner`, `enforcement_point`,
`expected_security_event`, `benchmark_family`, `benchmark_reference`, and
`regression_evidence` are each either the literal `COVERAGE_GAP` /
`NOT_APPLICABLE` token or a real, syntactically-checked reference — see
[`catalog/README.md`](catalog/README.md) for the full schema and
[`scripts/security/validate_threat_model.py`](../../scripts/security/validate_threat_model.py)
for the validator every scenario is checked against.
